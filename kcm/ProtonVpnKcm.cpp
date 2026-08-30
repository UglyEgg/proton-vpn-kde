// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#include "ProtonVpnKcm.h"

#include "AppSettings.h"
#include "TranslationLoader.h"

#include <KPluginFactory>
#include <QCoreApplication>
#include <QProcess>
#include <QStandardPaths>

ProtonVpnKcm::ProtonVpnKcm(QObject *parent, const KPluginMetaData &metadata)
    : KQuickConfigModule(parent, metadata)
    , m_settings(new AppSettings(this))
{
    TranslationLoader::installSystemLocale(*QCoreApplication::instance());
    setButtons(KAbstractConfigModule::NoAdditionalButton);
    setSupportsInstantApply(true);
}

AppSettings *ProtonVpnKcm::appSettings() const
{
    return m_settings;
}

void ProtonVpnKcm::openFullSettings()
{
    QProcess::startDetached(QStringLiteral("proton-vpn-kde"),
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
