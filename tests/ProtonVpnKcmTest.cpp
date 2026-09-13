// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#include <KPluginMetaData>
#include <KQuickConfigModule>
#include <KQuickConfigModuleLoader>

#include <QGuiApplication>
#include <QDir>
#include <QQuickItem>
#include <QResource>
#include <QTemporaryDir>
#include <QTest>

class ProtonVpnKcmTest final : public QObject
{
    Q_OBJECT

private slots:
    void loadsQmlConfigurationModule();
};

void ProtonVpnKcmTest::loadsQmlConfigurationModule()
{
    const KPluginMetaData metadata = KPluginMetaData::findPluginById(
        QStringLiteral(PROTON_VPN_KCM_PLUGIN_DIR),
        QStringLiteral(PROTON_VPN_KCM_PLUGIN_NAME));
    QVERIFY2(metadata.isValid(), "KCM plugin metadata was not discoverable");
    QCOMPARE(metadata.name(), QStringLiteral("Plasma VPN"));

    const auto result = KQuickConfigModuleLoader::loadModule(metadata, this);
    QVERIFY2(result.plugin, qPrintable(result.errorString));
    QTRY_VERIFY_WITH_TIMEOUT(result.plugin->mainUi() != nullptr, 5000);
    QVERIFY2(result.plugin->errorString().isEmpty(),
             qPrintable(result.plugin->errorString()));
    QVERIFY(result.plugin->supportsInstantApply());
#ifdef PROTON_VPN_KCM_EXPECTED_RESOURCE_EPOCH
    // Same-day RPM builds must not reuse the changelog's midnight timestamp:
    // Qt can otherwise accept bytecode cached from an older embedded main.qml.
    QCOMPARE(QResource(QStringLiteral(":/kcm/kcm_proton_vpn_kde/main.qml"))
                 .lastModified().toSecsSinceEpoch(),
             qint64(PROTON_VPN_KCM_EXPECTED_RESOURCE_EPOCH));
#endif
    QVERIFY(result.plugin->mainUi()->findChild<QObject *>(QStringLiteral("startupSettingsSection")));
    QVERIFY(result.plugin->mainUi()->findChild<QObject *>(QStringLiteral("startAtLoginSwitch")));

    auto *settings = result.plugin->property("appSettings").value<QObject *>();
    auto *error = result.plugin->mainUi()->findChild<QObject *>(QStringLiteral("localPreferenceSaveError"));
    QVERIFY(settings && error);
    const QString configPath = QDir(QString::fromUtf8(qgetenv("XDG_CONFIG_HOME")))
        .filePath(QStringLiteral("proton-vpn-kderc"));
    QVERIFY(QDir().mkpath(configPath)); // Disposable unwritable config filename.
    QVERIFY(settings->setProperty("iconStyle", QStringLiteral("light")));
    QVERIFY(!settings->property("errorMessage").toString().isEmpty());
    QCOMPARE(error->property("text"), settings->property("errorMessage"));
    QVERIFY(error->property("visible").toBool());
    QCOMPARE(settings->property("iconStyle").toString(), QStringLiteral("color"));
}

int main(int argc, char **argv)
{
    QTemporaryDir state;
    if (!state.isValid()) {
        return 1;
    }
    // Set these before Qt starts. Tests must neither consume nor populate the
    // desktop user's configuration or QML cache, even when an old KCM is installed.
    qputenv("XDG_CONFIG_HOME", state.filePath("config").toUtf8());
    qputenv("XDG_CACHE_HOME", state.filePath("cache").toUtf8());
    QGuiApplication application(argc, argv);
    ProtonVpnKcmTest test;
    return QTest::qExec(&test, argc, argv);
}

#include "ProtonVpnKcmTest.moc"
