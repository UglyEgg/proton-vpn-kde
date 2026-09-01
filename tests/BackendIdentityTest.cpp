// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#include "BackendIdentity.h"
#include "UnsafeBackendEnvironment.generated.h"

#include <QFile>
#include <QTemporaryDir>
#include <QTest>

class BackendIdentityTest : public QObject
{
    Q_OBJECT

private Q_SLOTS:
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
