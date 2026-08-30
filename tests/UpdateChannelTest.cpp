// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#include "UpdateChannel.h"

#include <QTest>

class UpdateChannelTest final : public QObject
{
    Q_OBJECT

private slots:
    void parsesExactRepositoryPackageNames();
    void buildsFixedDnfArguments();
};

void UpdateChannelTest::parsesExactRepositoryPackageNames()
{
    auto state = UpdateChannel::packageState(
        QByteArrayLiteral("protonvpn-beta-release\n"));
    QVERIFY(state.available);
    QVERIFY(state.betaEnabled);

    state = UpdateChannel::packageState(
        QByteArrayLiteral("prefix-protonvpn-beta-release\n"));
    QVERIFY(!state.available);
    QVERIFY(!state.betaEnabled);
}

void UpdateChannelTest::buildsFixedDnfArguments()
{
    QCOMPARE(
        UpdateChannel::switchArguments(true),
        QStringList({QStringLiteral("/usr/bin/dnf"), QStringLiteral("swap"),
                     QStringLiteral("-y"),
                     QStringLiteral("protonvpn-stable-release"),
                     QStringLiteral("protonvpn-beta-release")}));
    QCOMPARE(
        UpdateChannel::switchArguments(false),
        QStringList({QStringLiteral("/usr/bin/dnf"), QStringLiteral("swap"),
                     QStringLiteral("-y"),
                     QStringLiteral("protonvpn-beta-release"),
                     QStringLiteral("protonvpn-stable-release")}));
}

QTEST_GUILESS_MAIN(UpdateChannelTest)

#include "UpdateChannelTest.moc"
