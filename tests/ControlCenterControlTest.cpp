// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#include "AgentControl.h"
#include "InstalledExecutablePaths.h"

#include <QFile>
#include <QElapsedTimer>
#include <QScopeGuard>
#include <QDBusConnection>
#include <QDBusError>
#include <QDBusMessage>
#include <QTimer>
#include <QSignalSpy>
#include <QStandardPaths>
#include <QTest>
#include <QTemporaryDir>

class FakeAgentActivation final : public QObject, protected QDBusContext
{
    Q_OBJECT
    Q_CLASSINFO("D-Bus Interface", PROTON_VPN_KDE_DBUS_AGENT_INTERFACE)
public:
    bool reject = false;
    bool withhold = false;
public slots:
    Q_SCRIPTABLE void EnsureRunning()
    {
        setDelayedReply(true);
        if (!withhold) {
            const auto reply = reject
                ? message().createErrorReply(QDBusError::Failed, QStringLiteral("Synthetic activation failure"))
                : message().createReply();
            const auto bus = connection();
            QTimer::singleShot(25, this, [bus, reply] { bus.send(reply); });
        }
    }
};

class ControlCenterControlTest final : public QObject
{
    Q_OBJECT

private slots:
    void acceptsOnlyValidatedRunnerActions_data();
    void acceptsOnlyValidatedRunnerActions();
    void rejectsBroadBackendAuthority_data();
    void rejectsBroadBackendAuthority();
    void installedLaunchPathsIgnoreHostilePath();
    void agentActivationSettlesBeforeLauncherExit_data();
    void agentActivationSettlesBeforeLauncherExit();
};

void ControlCenterControlTest::agentActivationSettlesBeforeLauncherExit_data()
{
    QTest::addColumn<bool>("reject");
    QTest::addColumn<bool>("withhold");
    QTest::addColumn<bool>("fallbackWorks");
    QTest::newRow("delayed-success") << false << false << true;
    QTest::newRow("rejected-fallback") << true << false << true;
    QTest::newRow("timeout-fallback") << false << true << true;
    QTest::newRow("total-failure") << true << false << false;
}

void ControlCenterControlTest::agentActivationSettlesBeforeLauncherExit()
{
    QFETCH(bool, reject);
    QFETCH(bool, withhold);
    QFETCH(bool, fallbackWorks);
    namespace Agent = ProtonVpnKde::DBusContract::Agent;
    const auto name = QStringLiteral("activation-test-server");
    auto bus = QDBusConnection::connectToBus(QDBusConnection::SessionBus, name);
    const auto disconnect = qScopeGuard([&] { QDBusConnection::disconnectFromBus(name); });
    QVERIFY(bus.isConnected()); // CTest supplies a private bus, never the desktop.
    FakeAgentActivation agent;
    agent.reject = reject;
    agent.withhold = withhold;
    QVERIFY(bus.registerService(QString::fromLatin1(Agent::serviceName)));
    QVERIFY(bus.registerObject(QString::fromLatin1(Agent::objectPath), &agent,
                               QDBusConnection::ExportScriptableSlots));
    int fallbacks = 0;
    int completions = 0;
    bool started = false;
    QElapsedTimer elapsed;
    elapsed.start();
    ProtonVpnKde::ensureAgentRunning([&](bool success) {
        started = success;
        ++completions;
    }, [&] { ++fallbacks; return fallbackWorks; });
    QCOMPARE(completions, 0);
    QTRY_COMPARE_WITH_TIMEOUT(completions, 1, 5000);
    QCOMPARE(fallbacks, reject || withhold ? 1 : 0);
    QCOMPARE(started, (!reject && !withhold) || fallbackWorks);
    if (withhold) {
        QVERIFY(elapsed.elapsed() >= 2500); // Exercise the real pending-call deadline.
    }
    bus.unregisterObject(QString::fromLatin1(Agent::objectPath));
    bus.unregisterService(QString::fromLatin1(Agent::serviceName));
}

void ControlCenterControlTest::acceptsOnlyValidatedRunnerActions_data()
{
    QTest::addColumn<QString>("action");
    QTest::addColumn<QString>("argument");

    QTest::newRow("fastest") << QStringLiteral("fastest") << QString();
    QTest::newRow("disconnect") << QStringLiteral("disconnect") << QString();
    QTest::newRow("country")
        << QStringLiteral("country") << QStringLiteral("CH");
    QTest::newRow("server")
        << QStringLiteral("server") << QStringLiteral("US-CA#18");
    QTest::newRow("group")
        << QStringLiteral("group")
        << QStringLiteral(
               R"json({"countryCode":"CH","kind":"location","name":"Zurich"})json");
}

void ControlCenterControlTest::acceptsOnlyValidatedRunnerActions()
{
    QFETCH(QString, action);
    QFETCH(QString, argument);
    ControlCenterControl control;
    QSignalSpy spy(&control, &ControlCenterControl::runnerActionRequested);

    QVERIFY(control.RequestRunnerAction(action, argument));
    QCOMPARE(spy.count(), 1);
    QCOMPARE(spy.constFirst().at(0).toString(), action);
    QCOMPARE(spy.constFirst().at(1).toString(), argument);
}

void ControlCenterControlTest::rejectsBroadBackendAuthority_data()
{
    QTest::addColumn<QString>("action");
    QTest::addColumn<QString>("argument");

    QTest::newRow("settings")
        << QStringLiteral("UpdateSettings") << QStringLiteral("{}");
    QTest::newRow("capture")
        << QStringLiteral("StartPacketCapture") << QStringLiteral("/tmp");
    QTest::newRow("logout") << QStringLiteral("Logout") << QString();
    QTest::newRow("kill switch")
        << QStringLiteral("DisableKillSwitchForLogin") << QString();
    QTest::newRow("invalid target")
        << QStringLiteral("server") << QStringLiteral("../US#1");
}

void ControlCenterControlTest::rejectsBroadBackendAuthority()
{
    QFETCH(QString, action);
    QFETCH(QString, argument);
    ControlCenterControl control;
    QSignalSpy spy(&control, &ControlCenterControl::runnerActionRequested);

    QVERIFY(!control.RequestRunnerAction(action, argument));
    QCOMPARE(spy.count(), 0);
}

void ControlCenterControlTest::installedLaunchPathsIgnoreHostilePath()
{
    const QByteArray originalPath = qgetenv("PATH");
    QTemporaryDir hostileDirectory;
    QVERIFY(hostileDirectory.isValid());
    const QString hostileExecutable = hostileDirectory.filePath(
        QStringLiteral("proton-vpn-kde"));
    QFile shim(hostileExecutable);
    QVERIFY(shim.open(QIODevice::WriteOnly));
    QCOMPARE(shim.write("#!/usr/bin/bash\nexit 0\n"), 23);
    shim.close();
    QVERIFY(shim.setPermissions(QFileDevice::ReadOwner
                                | QFileDevice::WriteOwner
                                | QFileDevice::ExeOwner));
    QVERIFY(qputenv("PATH", hostileDirectory.path().toUtf8()));

    QCOMPARE(ProtonVpnKde::controlCenterExecutablePath(),
             QStringLiteral("/usr/bin/proton-vpn-kde"));
    QCOMPARE(ProtonVpnKde::agentExecutablePath(),
             QStringLiteral("/usr/bin/proton-vpn-kde-agent"));
    QCOMPARE(ProtonVpnKde::systemSettingsExecutablePath(),
             QStringLiteral("/usr/bin/systemsettings"));
    QCOMPARE(QStandardPaths::findExecutable(QStringLiteral("proton-vpn-kde")),
             hostileExecutable);

    QVERIFY(qputenv("PATH", originalPath));
}

QTEST_GUILESS_MAIN(ControlCenterControlTest)

#include "ControlCenterControlTest.moc"
