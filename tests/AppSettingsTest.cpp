// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#include "AppSettings.h"

#include <QSignalSpy>
#include <QTemporaryDir>
#include <QTest>

class AppSettingsTest final : public QObject
{
    Q_OBJECT

private slots:
    void persistsKConfigPreferences();
};

void AppSettingsTest::persistsKConfigPreferences()
{
    QTemporaryDir configHome;
    QVERIFY(configHome.isValid());
    qputenv("XDG_CONFIG_HOME", configHome.path().toUtf8());

    AppSettings initial;
    QVERIFY(initial.notificationsEnabled());
    QVERIFY(initial.reconnectEnabled());
    QVERIFY(initial.closeToTray());
    QVERIFY(!initial.startMinimized());
    QVERIFY(initial.autoConnectTarget().isEmpty());
    QVERIFY(initial.pinnedServers().isEmpty());
    QVERIFY(initial.pinnedServerGroups().isEmpty());
    QVERIFY(!initial.packetCaptureDirectory().isEmpty());
    QCOMPARE(initial.iconStyle(), QStringLiteral("color"));
    QVERIFY(initial.fastestFeatures().isEmpty());

    initial.setNotificationsEnabled(false);
    initial.setReconnectEnabled(false);
    initial.setCloseToTray(false);
    initial.setStartMinimized(true);
    initial.setAutoConnectTarget(QStringLiteral(" ch#101 "));
    initial.setPinnedServersText(QStringLiteral(" us, ch#101, US, fastest "));
    initial.togglePinnedServer(QStringLiteral("nl#42"));
    initial.togglePinnedServerGroup(
        QStringLiteral(" us "), QStringLiteral(" LOCATION "),
        QStringLiteral("  New York  "));
    initial.togglePinnedServerGroup(
        QStringLiteral("CH"), QStringLiteral("secure-core"),
        QStringLiteral("Via Secure Core"));
    initial.togglePinnedServerGroup(
        QStringLiteral("invalid"), QStringLiteral("location"),
        QStringLiteral("Ignored"));
    initial.setPacketCaptureDirectory(QStringLiteral("/tmp/proton-captures"));
    initial.setIconStyle(QStringLiteral("light"));
    initial.setFastestFeatures({QStringLiteral(" streaming "),
                                QStringLiteral("p2p"),
                                QStringLiteral("streaming"),
                                QStringLiteral("unsupported")});

    AppSettings reloaded;
    QVERIFY(!reloaded.notificationsEnabled());
    QVERIFY(!reloaded.reconnectEnabled());
    QVERIFY(!reloaded.closeToTray());
    QVERIFY(reloaded.startMinimized());
    QCOMPARE(reloaded.autoConnectTarget(), QStringLiteral("CH#101"));
    QCOMPARE(
        reloaded.pinnedServers(),
        QStringList({QStringLiteral("US"), QStringLiteral("CH#101"),
                     QStringLiteral("NL#42")}));
    QVERIFY(reloaded.isServerPinned(QStringLiteral(" ch#101 ")));
    QCOMPARE(reloaded.pinnedServerGroups().size(), 2);
    QVERIFY(reloaded.isServerGroupPinned(
        QStringLiteral("US"), QStringLiteral("location"),
        QStringLiteral("New York")));
    QCOMPARE(reloaded.pinnedServerGroupsText(),
             QStringLiteral("US — New York, CH — Via Secure Core"));
    QCOMPARE(
        reloaded.packetCaptureDirectory(),
        QStringLiteral("/tmp/proton-captures"));
    QCOMPARE(reloaded.iconStyle(), QStringLiteral("light"));
    QCOMPARE(reloaded.fastestFeatures(),
             QStringList({QStringLiteral("p2p"),
                          QStringLiteral("streaming")}));
    QVERIFY(reloaded.fastestFeatureEnabled(QStringLiteral("P2P")));
    QVERIFY(!reloaded.fastestFeatureEnabled(QStringLiteral("tor")));

    reloaded.setFastestFeatureEnabled(QStringLiteral("secure-core"), true);
    reloaded.setFastestFeatureEnabled(QStringLiteral("p2p"), false);
    QCOMPARE(reloaded.fastestFeatures(),
             QStringList({QStringLiteral("streaming"),
                          QStringLiteral("secure-core")}));

    reloaded.setAutoConnectTarget(QStringLiteral("off"));
    QVERIFY(reloaded.autoConnectTarget().isEmpty());
    reloaded.togglePinnedServer(QStringLiteral("CH#101"));
    QVERIFY(!reloaded.isServerPinned(QStringLiteral("CH#101")));
    reloaded.togglePinnedServerGroup(
        QStringLiteral("US"), QStringLiteral("location"),
        QStringLiteral("New York"));
    QVERIFY(!reloaded.isServerGroupPinned(
        QStringLiteral("US"), QStringLiteral("location"),
        QStringLiteral("New York")));
    reloaded.setIconStyle(QStringLiteral("unsupported"));
    QCOMPARE(reloaded.iconStyle(), QStringLiteral("color"));

    QSignalSpy iconStyleChanged(&reloaded, &AppSettings::iconStyleChanged);
    initial.setIconStyle(QStringLiteral("dark"));
    QTRY_COMPARE(reloaded.iconStyle(), QStringLiteral("dark"));
    QCOMPARE(iconStyleChanged.count(), 1);

    QSignalSpy notificationChanged(
        &reloaded, &AppSettings::notificationsEnabledChanged);
    initial.setNotificationsEnabled(true);
    QTRY_VERIFY(reloaded.notificationsEnabled());
    QCOMPARE(notificationChanged.count(), 1);

    QSignalSpy fastestFeaturesChanged(
        &reloaded, &AppSettings::fastestFeaturesChanged);
    initial.setFastestFeatures({QStringLiteral("tor"), QStringLiteral("p2p")});
    QTRY_COMPARE(reloaded.fastestFeatures(),
                 QStringList({QStringLiteral("p2p"), QStringLiteral("tor")}));
    QCOMPARE(fastestFeaturesChanged.count(), 1);

    QSignalSpy pinnedGroupsChanged(
        &reloaded, &AppSettings::pinnedServerGroupsChanged);
    initial.togglePinnedServerGroup(
        QStringLiteral("DE"), QStringLiteral("location"),
        QStringLiteral("Frankfurt"));
    QTRY_VERIFY(reloaded.isServerGroupPinned(
        QStringLiteral("DE"), QStringLiteral("location"),
        QStringLiteral("Frankfurt")));
    QCOMPARE(pinnedGroupsChanged.count(), 1);
}

QTEST_GUILESS_MAIN(AppSettingsTest)

#include "AppSettingsTest.moc"
