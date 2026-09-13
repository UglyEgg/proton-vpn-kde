// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#include "BackendIdentity.h"
#include "UnsafeBackendEnvironment.generated.h"

#include <QFile>
#include <QDBusConnection>
#include <QDBusMessage>
#include <QDBusVirtualObject>
#include <QTimer>
#include <QScopeGuard>
#include <QTemporaryDir>
#include <QTest>
#include <memory>

class DelayedProperties final : public QDBusVirtualObject
{
public:
    QDBusMessage pending;
    QString introspect(const QString &) const override { return {}; }
    bool handleMessage(const QDBusMessage &message, const QDBusConnection &) override
    {
        pending = message;
        message.setDelayedReply(true);
        return true;
    }
};

class BackendIdentityTest : public QObject
{
    Q_OBJECT

private Q_SLOTS:
    void discoversAnExistingOwnerWithOrWithoutActivation()
    {
        auto bus = QDBusConnection::sessionBus();
        const QString service = QStringLiteral("test.ExistingBackend");
        QVERIFY(bus.registerService(service));
        for (const bool activate : {false, true}) {
            bool completed = false;
            bool present = false;
            ProtonVpnKde::discoverBackendService(bus, service, activate, this,
                [&](bool found) { present = found; completed = true; });
            QTRY_VERIFY_WITH_TIMEOUT(completed, 6000);
            QVERIFY(present);
        }
        QVERIFY(bus.unregisterService(service));
    }

    void delayedIdentityIsResponsiveBoundedAndContextOwned_data()
    {
        QTest::addColumn<QString>("finish");
        QTest::newRow("error") << QStringLiteral("error");
        QTest::newRow("deadline") << QStringLiteral("deadline");
        QTest::newRow("destroyed-owner") << QStringLiteral("destroyed-owner");
    }

    void delayedIdentityIsResponsiveBoundedAndContextOwned()
    {
        QFETCH(QString, finish);
        auto bus = QDBusConnection::sessionBus();
        QVERIFY(bus.isConnected()); // CTest provides a disposable session bus.
        auto serverBus = QDBusConnection::connectToBus(QDBusConnection::SessionBus,
                                                       QStringLiteral("identity-test-server"));
        const auto cleanup = qScopeGuard([] {
            QDBusConnection::disconnectFromBus(QStringLiteral("identity-test-server"));
        });
        const QString service = QStringLiteral("test.PlasmaIdentity");
        const QString systemd = QStringLiteral("org.freedesktop.systemd1");
        const QString path = QStringLiteral(
            "/org/freedesktop/systemd1/unit/proton_2dvpn_2dkde_2dbackend_2eservice");
        QVERIFY(serverBus.registerService(service));
        QVERIFY(serverBus.registerService(systemd));
        DelayedProperties properties;
        QVERIFY(serverBus.registerVirtualObject(path, &properties));
        auto context = std::make_unique<QObject>();
        bool completed = false;
        bool trusted = false;
        int ticks = 0;
        QTimer heartbeat;
        connect(&heartbeat, &QTimer::timeout, this, [&ticks] { ++ticks; });
        heartbeat.start(5);
        ProtonVpnKde::verifyBackendIdentity(bus, service, context.get(),
            [&](const ProtonVpnKde::BackendIdentityResult &result) {
                completed = true;
                trusted = result.trusted;
            });
        QVERIFY(!completed);
        QTRY_COMPARE_WITH_TIMEOUT(properties.pending.type(), QDBusMessage::MethodCallMessage, 2000);
        QTRY_VERIFY(ticks >= 3);
        QVERIFY(!completed);
        if (finish == QStringLiteral("destroyed-owner")) {
            context.reset();
        }
        if (finish != QStringLiteral("deadline")) {
            QVERIFY(serverBus.send(properties.pending.createErrorReply(
                QStringLiteral("org.freedesktop.DBus.Error.Failed"), QStringLiteral("Test response"))));
        }
        if (context) {
            QTRY_VERIFY_WITH_TIMEOUT(completed, 6000);
        } else {
            QTest::qWait(50);
            QVERIFY(!completed);
        }
        QVERIFY(!trusted);
        serverBus.unregisterObject(path);
        QVERIFY(serverBus.unregisterService(systemd));
        QVERIFY(serverBus.unregisterService(service));
    }

    void ordinaryEnvironmentIsTrusted()
    {
        QByteArray environment("HOME=/home/test");
        environment.append('\0');
        environment.append(
            "DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus");
        environment.append('\0');
        environment.append("OPENSSL_CONFUSION=/tmp/ordinary");

        QVERIFY(ProtonVpnKde::isBackendEnvironmentSafe(environment));
    }

    void everyUnsafeEnvironmentNameIsRejected()
    {
        for (const std::string_view prefix :
             ProtonVpnKde::kUnsafeBackendEnvironmentPrefixes) {
            for (const QByteArray &value : {QByteArray{},
                                            QByteArray{"/tmp/attacker"}}) {
                QByteArray environment("HOME=/home/test");
                environment.append('\0');
                environment.append(prefix.data(),
                                   static_cast<qsizetype>(prefix.size()));
                environment.append(value);
                QVERIFY2(!ProtonVpnKde::isBackendEnvironmentSafe(environment),
                         prefix.data());
            }
        }
    }

    void emptyDropInListIsTrusted()
    {
        QVERIFY(ProtonVpnKde::areRootOwnedImmutableFiles({}));
    }

    void rootOwnedImmutableDropInIsTrusted()
    {
        const QString systemdDropIn = QStringLiteral(
            "/usr/lib/systemd/user/service.d/10-timeout-abort.conf");
        if (!QFile::exists(systemdDropIn)) {
            QSKIP("Fedora's systemd user-service drop-in is not installed");
        }

        if (!ProtonVpnKde::isRootOwnedImmutableFile(systemdDropIn)) {
            QSKIP("Host ownership is remapped in this test environment");
        }
        QVERIFY(ProtonVpnKde::areRootOwnedImmutableFiles({systemdDropIn}));
    }

    void userOwnedDropInIsRejected()
    {
        QTemporaryDir directory;
        QVERIFY(directory.isValid());
        const QString path = directory.filePath(QStringLiteral("override.conf"));
        QFile file(path);
        QVERIFY(file.open(QIODevice::WriteOnly));
        QVERIFY(file.write("[Service]\nExecStart=/tmp/impostor\n") > 0);
        file.close();

        QVERIFY(!ProtonVpnKde::isRootOwnedImmutableFile(path));
        QVERIFY(!ProtonVpnKde::areRootOwnedImmutableFiles({path}));
    }

    void mixedDropInListIsRejected()
    {
        const QString systemdDropIn = QStringLiteral(
            "/usr/lib/systemd/user/service.d/10-timeout-abort.conf");
        if (!QFile::exists(systemdDropIn)) {
            QSKIP("Fedora's systemd user-service drop-in is not installed");
        }

        QTemporaryDir directory;
        QVERIFY(directory.isValid());
        const QString userDropIn = directory.filePath(QStringLiteral("override.conf"));
        QFile file(userDropIn);
        QVERIFY(file.open(QIODevice::WriteOnly));
        file.close();

        QVERIFY(!ProtonVpnKde::areRootOwnedImmutableFiles(
            {systemdDropIn, userDropIn}));
    }
};

QTEST_GUILESS_MAIN(BackendIdentityTest)

#include "BackendIdentityTest.moc"
