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

    initial.setNotificationsEnabled(false);
    initial.setReconnectEnabled(false);
    initial.setCloseToTray(false);
    initial.setStartMinimized(true);

    AppSettings reloaded;
    QVERIFY(!reloaded.notificationsEnabled());
    QVERIFY(!reloaded.reconnectEnabled());
    QVERIFY(!reloaded.closeToTray());
    QVERIFY(reloaded.startMinimized());
}

QTEST_GUILESS_MAIN(AppSettingsTest)

#include "AppSettingsTest.moc"
