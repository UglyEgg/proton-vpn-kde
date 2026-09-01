// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#include "AgentControl.h"
#include "InstalledExecutablePaths.h"

#include <QFile>
#include <QSignalSpy>
#include <QStandardPaths>
#include <QTest>
#include <QTemporaryDir>

class ControlCenterControlTest final : public QObject
{
    Q_OBJECT

private slots:
    void acceptsOnlyValidatedRunnerActions_data();
    void acceptsOnlyValidatedRunnerActions();
    void rejectsBroadBackendAuthority_data();
    void rejectsBroadBackendAuthority();
    void installedLaunchPathsIgnoreHostilePath();
};

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
