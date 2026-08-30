#include <KPluginMetaData>
#include <KQuickConfigModule>
#include <KQuickConfigModuleLoader>

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
}

QTEST_MAIN(ProtonVpnKcmTest)

#include "ProtonVpnKcmTest.moc"
