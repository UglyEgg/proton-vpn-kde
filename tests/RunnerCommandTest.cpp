// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#include "RunnerCommand.h"

#include <QTest>

class RunnerCommandTest final : public QObject
{
    Q_OBJECT

private slots:
    void rejectsUnrelatedQueries();
    void offersPrimaryActions();
    void parsesFastestAndDisconnect();
    void parsesCountryTargets();
    void parsesServerTargets();
    void rejectsMalformedTargets();
};

void RunnerCommandTest::rejectsUnrelatedQueries()
{
    QVERIFY(parseRunnerQuery(QStringLiteral("connect vpn")).isEmpty());
    QVERIFY(parseRunnerQuery(QStringLiteral("vpnish")).isEmpty());
}

void RunnerCommandTest::offersPrimaryActions()
{
    const QList<RunnerCommand> commands = parseRunnerQuery(QStringLiteral("vpn"));
    QCOMPARE(commands.size(), 3);
    QCOMPARE(commands.at(0).action, RunnerAction::Open);
    QCOMPARE(commands.at(1).action, RunnerAction::ConnectFastest);
    QCOMPARE(commands.at(2).action, RunnerAction::Disconnect);
}

void RunnerCommandTest::parsesFastestAndDisconnect()
{
    QCOMPARE(parseRunnerQuery(QStringLiteral("Proton VPN connect fastest")).at(0).action,
             RunnerAction::ConnectFastest);
    QCOMPARE(parseRunnerQuery(QStringLiteral("vpn disconnect")).at(0).action,
             RunnerAction::Disconnect);
}

void RunnerCommandTest::parsesCountryTargets()
{
    const RunnerCommand command =
        parseRunnerQuery(QStringLiteral("vpn connect ch")).at(0);
    QCOMPARE(command.action, RunnerAction::ConnectCountry);
    QCOMPARE(command.argument, QStringLiteral("CH"));
}

void RunnerCommandTest::parsesServerTargets()
{
    const RunnerCommand command =
        parseRunnerQuery(QStringLiteral("vpn server us-ca#18")).at(0);
    QCOMPARE(command.action, RunnerAction::ConnectServer);
    QCOMPARE(command.argument, QStringLiteral("US-CA#18"));
}

void RunnerCommandTest::rejectsMalformedTargets()
{
    QVERIFY(parseRunnerQuery(QStringLiteral("vpn country Switzerland")).isEmpty());
    QVERIFY(parseRunnerQuery(QStringLiteral("vpn server ../bad")).isEmpty());
    QVERIFY(parseRunnerQuery(QStringLiteral("vpn connect US;shutdown")).isEmpty());
}

QTEST_GUILESS_MAIN(RunnerCommandTest)

#include "RunnerCommandTest.moc"
