#include "AppSettings.h"

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
    QVERIFY(!initial.packetCaptureDirectory().isEmpty());

    initial.setNotificationsEnabled(false);
    initial.setReconnectEnabled(false);
    initial.setCloseToTray(false);
    initial.setStartMinimized(true);
    initial.setAutoConnectTarget(QStringLiteral(" ch#101 "));
    initial.setPinnedServersText(QStringLiteral(" us, ch#101, US, fastest "));
    initial.togglePinnedServer(QStringLiteral("nl#42"));
    initial.setPacketCaptureDirectory(QStringLiteral("/tmp/proton-captures"));

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
    QCOMPARE(
        reloaded.packetCaptureDirectory(),
        QStringLiteral("/tmp/proton-captures"));

    reloaded.setAutoConnectTarget(QStringLiteral("off"));
    QVERIFY(reloaded.autoConnectTarget().isEmpty());
    reloaded.togglePinnedServer(QStringLiteral("CH#101"));
    QVERIFY(!reloaded.isServerPinned(QStringLiteral("CH#101")));
}

QTEST_GUILESS_MAIN(AppSettingsTest)

#include "AppSettingsTest.moc"
