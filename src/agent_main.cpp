#include "AgentControl.h"
#include "AgentVpnClient.h"
#include "AppSettings.h"
#include "NotificationIntegration.h"
#include "ShortcutIntegration.h"
#include "TranslationLoader.h"
#include "TrayIntegration.h"

#include <QApplication>
#include <QIcon>

int main(int argc, char *argv[])
{
    QApplication app(argc, argv);
    QApplication::setApplicationName(QStringLiteral("proton-vpn-kde"));
    QApplication::setApplicationDisplayName(
        QStringLiteral("Proton VPN Plasma Agent"));
    QApplication::setApplicationVersion(QStringLiteral(PROTON_VPN_KDE_VERSION));
    QApplication::setOrganizationDomain(QStringLiteral("proton.me"));
    QApplication::setDesktopFileName(QStringLiteral("proton-vpn-kde"));
    QApplication::setWindowIcon(QIcon::fromTheme(
        QStringLiteral("proton-vpn-kde"),
        QIcon::fromTheme(QStringLiteral("network-vpn"))));
    QApplication::setQuitOnLastWindowClosed(false);
    TranslationLoader::installSystemLocale(app);

    AgentControl control;
    if (!control.registerOnSessionBus()) {
        return 0;
    }

    AppSettings settings;
    if (!settings.closeToTray()) {
        return 0;
    }

    AgentVpnClient client;
    client.setReconnectionEnabled(settings.reconnectEnabled());
    QObject::connect(&settings, &AppSettings::reconnectEnabledChanged,
                     &client, [&settings, &client] {
        client.setReconnectionEnabled(settings.reconnectEnabled());
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
