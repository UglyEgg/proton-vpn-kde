// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#include "ConnectionAction.h"

#include <QTest>

class ConnectionActionTest final : public QObject
{
    Q_OBJECT

private slots:
    void disconnectsProtectiveAndActiveStates();
    void connectsOnlyFromInactiveStates();
    void admissionMatrix_data();
    void admissionMatrix();
    void invalidAndUnauthenticatedStatesNeverAuthorizeConnect();
};

void ConnectionActionTest::disconnectsProtectiveAndActiveStates()
{
    QVERIFY(ProtonVpnKde::primaryActionDisconnects(u"connected"));
    QVERIFY(ProtonVpnKde::primaryActionDisconnects(u"connecting"));
    QVERIFY(ProtonVpnKde::primaryActionDisconnects(u"disconnecting"));
    QVERIFY(ProtonVpnKde::primaryActionDisconnects(u"error"));
}

void ConnectionActionTest::connectsOnlyFromInactiveStates()
{
    QVERIFY(!ProtonVpnKde::primaryActionDisconnects(u"disconnected"));
    QVERIFY(!ProtonVpnKde::primaryActionDisconnects(u"unavailable"));
    QVERIFY(!ProtonVpnKde::primaryActionDisconnects(u""));
}

void ConnectionActionTest::admissionMatrix_data()
{
    QTest::addColumn<QString>("state");
    QTest::addColumn<bool>("busy");
    QTest::addColumn<bool>("loggedIn");
    QTest::addColumn<QString>("authState");
    QTest::addColumn<bool>("connectAllowed");
    QTest::addColumn<bool>("disconnectAllowed");
    QTest::newRow("idle") << QStringLiteral("disconnected") << false << true
        << QStringLiteral("signed_in") << true << false;
    QTest::newRow("before-first-connecting-snapshot") << QStringLiteral("disconnected")
        << true << true << QStringLiteral("signed_in") << false << true;
    QTest::newRow("connecting-busy") << QStringLiteral("connecting") << true << true
        << QStringLiteral("signed_in") << false << true;
    QTest::newRow("connecting-idle") << QStringLiteral("connecting") << false << true
        << QStringLiteral("signed_in") << false << true;
    QTest::newRow("connected-busy") << QStringLiteral("connected") << true << true
        << QStringLiteral("signed_in") << false << true;
    QTest::newRow("connected-switch-target") << QStringLiteral("connected") << false << true
        << QStringLiteral("signed_in") << true << true;
    QTest::newRow("disconnecting") << QStringLiteral("disconnecting") << true << true
        << QStringLiteral("signed_in") << false << false;
    QTest::newRow("error-recovery") << QStringLiteral("error") << false << true
        << QStringLiteral("signed_in") << true << true;
    QTest::newRow("expired-tunnel") << QStringLiteral("connected") << false << false
        << QStringLiteral("expired") << false << true;
    QTest::newRow("signed-out") << QStringLiteral("disconnected") << false << false
        << QStringLiteral("signed_out") << false << false;
    QTest::newRow("unknown-account") << QStringLiteral("connected") << false << true
        << QStringLiteral("authentication_unknown") << false << true;
    QTest::newRow("degraded-updates") << QStringLiteral("disconnected") << false << true
        << QStringLiteral("signed_in_degraded") << true << false;
    QTest::newRow("unknown-state") << QStringLiteral("future-state") << false << true
        << QStringLiteral("signed_in") << false << false;
}

void ConnectionActionTest::admissionMatrix()
{
    QFETCH(QString, state);
    QFETCH(bool, busy);
    QFETCH(bool, loggedIn);
    QFETCH(QString, authState);
    QFETCH(bool, connectAllowed);
    QFETCH(bool, disconnectAllowed);
    const auto action = ProtonVpnKde::connectionActionCapabilities(
        true, true, true, loggedIn, busy, state, authState);
    QCOMPARE(action.connect, connectAllowed);
    QCOMPARE(action.disconnect, disconnectAllowed);
    QCOMPARE(action.waitForDisconnect, state == QStringLiteral("disconnecting"));
    QCOMPARE(action.idleDisconnected, !busy && state == QStringLiteral("disconnected"));
    QVERIFY(!action.activate);
}

void ConnectionActionTest::invalidAndUnauthenticatedStatesNeverAuthorizeConnect()
{
    const QStringList states{
        QStringLiteral("connected"), QStringLiteral("disconnected"),
        QStringLiteral("connecting"), QStringLiteral("disconnecting"),
        QStringLiteral("error"), QStringLiteral("unresponsive"), QString()};
    const QStringList accounts{
        QStringLiteral("signed_in"), QStringLiteral("signed_in_degraded"),
        QStringLiteral("expired"), QStringLiteral("account_restart_required"),
        QStringLiteral("authentication_unknown"), QStringLiteral("protection_unknown"),
        QStringLiteral("settings_unavailable"), QString()};
    for (const QString &state : states) {
        for (const QString &account : accounts) {
            for (int flags = 0; flags < 64; ++flags) {
                const bool available = flags & 1;
                const bool ready = flags & 2;
                const bool healthy = flags & 4;
                const bool loggedIn = flags & 8;
                const bool busy = flags & 16;
                const bool activation = flags & 32;
                const auto action = ProtonVpnKde::connectionActionCapabilities(
                    available, ready, healthy, loggedIn, busy, state, account, activation);
                if (!available || !ready || !healthy) {
                    QVERIFY(!action.connect);
                    QVERIFY(!action.disconnect);
                    QVERIFY(!action.idleDisconnected);
                }
                if (!loggedIn || busy || !ProtonVpnKde::accountAllowsConnection(account)) {
                    QVERIFY(!action.connect);
                }
                QCOMPARE(action.activate, !available && activation);
            }
        }
    }
}

QTEST_GUILESS_MAIN(ConnectionActionTest)

#include "ConnectionActionTest.moc"
