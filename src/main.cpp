#include "AppSettings.h"
#include "NotificationIntegration.h"
#include "TrayIntegration.h"
#include "VpnController.h"

#include <QApplication>
#include <QIcon>
#include <QQmlApplicationEngine>
#include <QQmlContext>
#include <QQuickWindow>

int main(int argc, char *argv[])
{
    QApplication app(argc, argv);
    QApplication::setApplicationName(QStringLiteral("Proton VPN"));
    QApplication::setApplicationDisplayName(QStringLiteral("Proton VPN for Plasma"));
    QApplication::setOrganizationDomain(QStringLiteral("proton.me"));
    QApplication::setDesktopFileName(QStringLiteral("proton-vpn-kde"));
    QApplication::setWindowIcon(QIcon::fromTheme(QStringLiteral("proton-vpn-kde"),
                                                  QIcon::fromTheme(QStringLiteral("network-vpn"))));
    QApplication::setQuitOnLastWindowClosed(false);

    AppSettings settings;
    VpnController controller;
    controller.setReconnectionEnabled(settings.reconnectEnabled());
    QObject::connect(&settings, &AppSettings::reconnectEnabledChanged,
                     &controller, [&settings, &controller] {
                         controller.setReconnectionEnabled(settings.reconnectEnabled());
                     });
    QObject::connect(&settings, &AppSettings::closeToTrayChanged,
                     &app, [&settings] {
                         QApplication::setQuitOnLastWindowClosed(!settings.closeToTray());
                     });
    QApplication::setQuitOnLastWindowClosed(!settings.closeToTray());

    QQmlApplicationEngine engine;
    engine.rootContext()->setContextProperty(QStringLiteral("vpnController"), &controller);
    engine.rootContext()->setContextProperty(QStringLiteral("appSettings"), &settings);
    engine.rootContext()->setContextProperty(
        QStringLiteral("startMinimized"), settings.startMinimized());
    engine.loadFromModule(QStringLiteral("Proton.VPN.KDE"), QStringLiteral("Main"));
    if (engine.rootObjects().isEmpty()) {
        return 1;
    }

    auto *window = qobject_cast<QQuickWindow *>(engine.rootObjects().constFirst());
    TrayIntegration tray(&controller, window);
    NotificationIntegration notifications(&controller, &settings);

    return app.exec();
}
