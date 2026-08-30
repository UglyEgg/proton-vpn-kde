// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#include "AgentControl.h"

#include <QSignalSpy>
#include <QTest>

class ControlCenterControlTest final : public QObject
{
    Q_OBJECT

private slots:
    void acceptsOnlyValidatedRunnerActions_data();
    void acceptsOnlyValidatedRunnerActions();
    void rejectsBroadBackendAuthority_data();
    void rejectsBroadBackendAuthority();
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

QTEST_GUILESS_MAIN(ControlCenterControlTest)

#include "ControlCenterControlTest.moc"
