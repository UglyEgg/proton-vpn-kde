// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#include "AppSettings.h"

#include <KConfigGroup>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QSignalSpy>
#include <QTemporaryDir>
#include <QTest>

class AppSettingsTest final : public QObject
{
    Q_OBJECT

private slots:
    void persistsKConfigPreferences();
    void startupCommandHonorsPreferencesWithoutHidingExplicitLaunches();
    void managesOnlyExplicitlyEnabledLoginEntry();
    void preservesForeignLoginEntries_data();
    void preservesForeignLoginEntries();
    void reportsLoginEntryWriteFailure();
    void doesNotClaimLockedLoginEntryWasSaved();
};

void AppSettingsTest::managesOnlyExplicitlyEnabledLoginEntry()
{
    QTemporaryDir configHome;
    QVERIFY(configHome.isValid());
    qputenv("XDG_CONFIG_HOME", configHome.path().toUtf8());
    const QString path = configHome.filePath(QStringLiteral("autostart/proton-vpn-kde.desktop"));
    AppSettings settings;
    QVERIFY(settings.findChildren<AutostartSettings *>().isEmpty());
    auto *startup = settings.autostart();
    QCOMPARE(settings.autostart(), startup);
    QVERIFY(!startup->enabled());
    startup->setEnabled(false);
    QVERIFY(!QFileInfo::exists(path));
    startup->setEnabled(true);
    QVERIFY2(startup->enabled(), qPrintable(startup->errorMessage()));
    KConfig file(path, KConfig::SimpleConfig);
    KConfigGroup entry(&file, QStringLiteral("Desktop Entry"));
    QCOMPARE(entry.readEntry("Exec", QString()),
             QStringLiteral("\"" PROTON_VPN_KDE_CONTROL_CENTER_EXECUTABLE_PATH "\""));
    QCOMPARE(entry.readEntry("TryExec", QString()),
             QStringLiteral(PROTON_VPN_KDE_CONTROL_CENTER_EXECUTABLE_PATH));
    QCOMPARE(entry.readEntry("OnlyShowIn", QString()), QStringLiteral("KDE;"));
    QVERIFY(entry.readEntry("X-PlasmaVPN-Managed", false));
    QVERIFY(!entry.readEntry("Hidden", true));

    // Plasma's Autostart UI remains authoritative when this page is reopened.
    entry.writeEntry("Hidden", true);
    QVERIFY(file.sync());
    startup->refresh();
    QVERIFY(!startup->enabled());
    startup->setEnabled(true);
    QVERIFY(startup->enabled());
    startup->setEnabled(false);
    QVERIFY(!startup->enabled());
    QVERIFY(QFileInfo::exists(path)); // Reversible Hidden=true, not deletion.
    file.reparseConfiguration();
    QVERIFY(entry.readEntry("Hidden", false));
    QCOMPARE(QDir(configHome.filePath("autostart")).entryList(QDir::Files).size(), 1);
}

void AppSettingsTest::preservesForeignLoginEntries_data()
{
    QTest::addColumn<bool>("symlink");
    QTest::newRow("custom-desktop-file") << false;
    QTest::newRow("launcher-symlink") << true;
}

void AppSettingsTest::preservesForeignLoginEntries()
{
    QFETCH(bool, symlink);
    QTemporaryDir configHome;
    QVERIFY(configHome.isValid());
    qputenv("XDG_CONFIG_HOME", configHome.path().toUtf8());
    QVERIFY(QDir().mkpath(configHome.filePath("autostart")));
    const QString path = configHome.filePath("autostart/proton-vpn-kde.desktop");
    const QString originalPath = symlink ? configHome.filePath("launcher.desktop") : path;
    const QByteArray original("[Desktop Entry]\nType=Application\nExec=custom-launcher --show\n");
    QFile originalFile(originalPath);
    QVERIFY(originalFile.open(QIODevice::WriteOnly));
    QCOMPARE(originalFile.write(original), original.size());
    originalFile.close();
    if (symlink) {
        QVERIFY(QFile::link(originalPath, path));
    }
    AutostartSettings settings;
    QVERIFY(!settings.configurable());
    QVERIFY(!settings.errorMessage().isEmpty());
    settings.setEnabled(true);
    settings.setEnabled(false);
    QCOMPARE(QFileInfo(path).isSymbolicLink(), symlink);
    QVERIFY(originalFile.open(QIODevice::ReadOnly));
    QCOMPARE(originalFile.readAll(), original);
}

void AppSettingsTest::reportsLoginEntryWriteFailure()
{
    QTemporaryDir configHome;
    QVERIFY(configHome.isValid());
    qputenv("XDG_CONFIG_HOME", configHome.path().toUtf8());
    QFile obstacle(configHome.filePath("autostart"));
    QVERIFY(obstacle.open(QIODevice::WriteOnly));
    obstacle.close();
    AutostartSettings settings;
    settings.setEnabled(true);
    QVERIFY(!settings.enabled());
    QVERIFY(!settings.errorMessage().isEmpty());
    QVERIFY(QFileInfo(obstacle).isFile());
}

void AppSettingsTest::doesNotClaimLockedLoginEntryWasSaved()
{
    QTemporaryDir configHome;
    QVERIFY(configHome.isValid());
    qputenv("XDG_CONFIG_HOME", configHome.path().toUtf8());
    QVERIFY(QDir().mkpath(configHome.filePath("autostart")));
    QFile entry(configHome.filePath("autostart/proton-vpn-kde.desktop"));
    const QByteArray original("[Desktop Entry][$i]\nX-PlasmaVPN-Managed=true\nHidden=true\n");
    QVERIFY(entry.open(QIODevice::WriteOnly));
    QCOMPARE(entry.write(original), original.size());
    entry.close();
    AutostartSettings settings;
    settings.setEnabled(true);
    QVERIFY(!settings.enabled());
    QVERIFY(!settings.errorMessage().isEmpty());
    QVERIFY(entry.open(QIODevice::ReadOnly));
    QCOMPARE(entry.readAll(), original);
}

void AppSettingsTest::startupCommandHonorsPreferencesWithoutHidingExplicitLaunches()
{
    QTemporaryDir configHome;
    qputenv("XDG_CONFIG_HOME", configHome.path().toUtf8());
    AppSettings settings;
    for (const bool tray : {false, true}) {
        for (const bool minimized : {false, true}) {
            settings.setCloseToTray(tray);
            settings.setStartMinimized(minimized);
            QCOMPARE(settings.startTrayOnly(false, false), tray && minimized);
            QVERIFY(!settings.startTrayOnly(false, true)); // Launcher --show.
            QVERIFY(!settings.startTrayOnly(true, false)); // Settings route.
            QVERIFY(!settings.startTrayOnly(true, true));
        }
    }
}

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
