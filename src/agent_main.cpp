// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#include "AgentControl.h"
#include "AgentVpnClient.h"
#include "AppIcon.h"
#include "AppSettings.h"
#include "NotificationIntegration.h"
#include "ShortcutIntegration.h"
#include "TranslationLoader.h"
#include "TrayIntegration.h"

#include <QApplication>

int main(int argc, char *argv[])
{
    QApplication app(argc, argv);
    QApplication::setApplicationName(QStringLiteral("proton-vpn-kde"));
    QApplication::setApplicationDisplayName(QStringLiteral("Plasma VPN Agent"));
    QApplication::setApplicationVersion(QStringLiteral(PROTON_VPN_KDE_VERSION));
    QApplication::setOrganizationDomain(QStringLiteral("entropy.quest"));
    QApplication::setDesktopFileName(QStringLiteral("proton-vpn-kde"));
    AppSettings settings;
    QApplication::setWindowIcon(
        ProtonVpnKde::applicationIcon(settings.iconStyle()));
    QObject::connect(&settings, &AppSettings::iconStyleChanged,
                     &app, [&settings] {
        QApplication::setWindowIcon(
            ProtonVpnKde::applicationIcon(settings.iconStyle()));
    });
    QApplication::setQuitOnLastWindowClosed(false);
    TranslationLoader::installSystemLocale(app);

    AgentControl control;
    if (!control.registerOnSessionBus()) {
        return 0;
    }

    if (!settings.closeToTray()) {
        return 0;
    }

    AgentVpnClient client;
    client.setReconnectionEnabled(settings.reconnectEnabled());
    client.setFastestFeatures(settings.fastestFeatures());
    QObject::connect(&settings, &AppSettings::reconnectEnabledChanged,
                     &client, [&settings, &client] {
        client.setReconnectionEnabled(settings.reconnectEnabled());
    });
    QObject::connect(&settings, &AppSettings::fastestFeaturesChanged,
                     &client, [&settings, &client] {
        client.setFastestFeatures(settings.fastestFeatures());
    });
    QObject::connect(&settings, &AppSettings::closeToTrayChanged,
                     &app, [&settings] {
        if (!settings.closeToTray()) {
            QCoreApplication::quit();
        }
    });
    QObject::connect(&client, &AgentVpnClient::controlCenterRequested,
                     &control, &AgentControl::ShowControlCenter);

    const auto showControlCenter = [&control] { control.ShowControlCenter(); };
    TrayIntegration tray(&client, &settings, showControlCenter);
    ShortcutIntegration shortcuts(&client, showControlCenter);
    NotificationIntegration notifications(&client, &settings);

    if (!settings.autoConnectTarget().isEmpty()) {
        client.autoConnect(settings.autoConnectTarget());
    }
    return app.exec();
}
