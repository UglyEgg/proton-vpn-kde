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

QTEST_GUILESS_MAIN(ConnectionActionTest)

#include "ConnectionActionTest.moc"
