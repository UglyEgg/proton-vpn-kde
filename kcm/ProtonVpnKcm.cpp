#include "ProtonVpnKcm.h"

#include "AppSettings.h"

#include <KPluginFactory>
#include <QProcess>
#include <QStandardPaths>

ProtonVpnKcm::ProtonVpnKcm(QObject *parent, const KPluginMetaData &metadata)
    : KQuickConfigModule(parent, metadata)
    , m_settings(new AppSettings(this))
{
    setButtons(KAbstractConfigModule::NoAdditionalButton);
    setSupportsInstantApply(true);
}

AppSettings *ProtonVpnKcm::appSettings() const
{
    return m_settings;
}

void ProtonVpnKcm::openFullSettings()
{
    QProcess::startDetached(QStringLiteral(PROTON_VPN_KDE_EXECUTABLE),
                            {QStringLiteral("--settings")});
}

void ProtonVpnKcm::openGlobalShortcuts()
{
    const QString systemSettings =
        QStandardPaths::findExecutable(QStringLiteral("systemsettings"));
    if (!systemSettings.isEmpty()) {
        QProcess::startDetached(systemSettings, {QStringLiteral("kcm_keys")});
    }
}

K_PLUGIN_CLASS_WITH_JSON(ProtonVpnKcm, "kcm_proton_vpn_kde.json")

#include "ProtonVpnKcm.moc"
