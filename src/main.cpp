#include "AppLifecycle.h"
#include "AppSettings.h"
#include "NotificationIntegration.h"
#include "ShortcutIntegration.h"
#include "TranslationLoader.h"
#include "TrayIntegration.h"
#include "UpdateChannel.h"
#include "VpnController.h"

#include <KDBusService>
#include <QApplication>
#include <QCommandLineOption>
#include <QCommandLineParser>
#include <QIcon>
#include <QQmlApplicationEngine>
#include <QQmlContext>
#include <QQuickWindow>

int main(int argc, char *argv[])
{
    QApplication app(argc, argv);
    QApplication::setApplicationName(QStringLiteral("proton-vpn-kde"));
    QApplication::setApplicationDisplayName(QStringLiteral("Proton VPN for Plasma"));
    QApplication::setApplicationVersion(
        QStringLiteral(PROTON_VPN_KDE_VERSION));
    QApplication::setOrganizationDomain(QStringLiteral("proton.me"));
    QApplication::setDesktopFileName(QStringLiteral("proton-vpn-kde"));
    QApplication::setWindowIcon(QIcon::fromTheme(QStringLiteral("proton-vpn-kde"),
                                                  QIcon::fromTheme(QStringLiteral("network-vpn"))));
    QApplication::setQuitOnLastWindowClosed(false);
    TranslationLoader::installSystemLocale(app);

    QCommandLineParser commandLine;
    commandLine.setApplicationDescription(
        QStringLiteral("Native Proton VPN client for KDE Plasma"));
    commandLine.addHelpOption();
    commandLine.addVersionOption();
    const QCommandLineOption settingsOption(
        QStringLiteral("settings"),
        QStringLiteral("Open the Proton VPN settings page"));
    commandLine.addOption(settingsOption);
    commandLine.process(app);
    const bool openSettings = commandLine.isSet(settingsOption);

    AppSettings settings;
    AppLifecycle lifecycle;
    UpdateChannel updateChannel;
    VpnController controller;
    bool startupActionHandled = false;
    controller.setReconnectionEnabled(settings.reconnectEnabled());
    QObject::connect(&settings, &AppSettings::reconnectEnabledChanged,
                     &controller, [&settings, &controller] {
                         controller.setReconnectionEnabled(settings.reconnectEnabled());
                     });
    QObject::connect(&settings, &AppSettings::closeToTrayChanged,
                     &app, [&settings] {
                         QApplication::setQuitOnLastWindowClosed(!settings.closeToTray());
                     });
    QObject::connect(&controller, &VpnController::snapshotChanged,
                     &app, [&controller, &settings, &startupActionHandled] {
                         if (startupActionHandled || !controller.ready()) {
                             return;
                         }
                         startupActionHandled = true;
                         if (controller.loggedIn()
                             && controller.state() == QStringLiteral("disconnected")
                             && !settings.autoConnectTarget().isEmpty()) {
                             controller.connectTarget(settings.autoConnectTarget());
                         }
                     });
    QObject::connect(&controller, &VpnController::snapshotChanged,
                     &lifecycle, [&controller, &lifecycle] {
                         lifecycle.observeConnectionState(controller.state());
                     });
    QObject::connect(&lifecycle, &AppLifecycle::disconnectRequested,
                     &controller, &VpnController::disconnect);
    QObject::connect(&lifecycle, &AppLifecycle::quitReady,
                     &app, &QApplication::quit);
    QApplication::setQuitOnLastWindowClosed(!settings.closeToTray());

    QQmlApplicationEngine engine;
    engine.rootContext()->setContextProperty(QStringLiteral("vpnController"), &controller);
    engine.rootContext()->setContextProperty(QStringLiteral("appSettings"), &settings);
    engine.rootContext()->setContextProperty(QStringLiteral("appLifecycle"), &lifecycle);
    engine.rootContext()->setContextProperty(
        QStringLiteral("updateChannel"), &updateChannel);
    engine.rootContext()->setContextProperty(
        QStringLiteral("startMinimized"),
        settings.startMinimized() && !openSettings);
    engine.rootContext()->setContextProperty(
        QStringLiteral("initialPageName"),
        openSettings ? QStringLiteral("SettingsPage.qml")
                     : QStringLiteral("OverviewPage.qml"));
    engine.rootContext()->setContextProperty(
        QStringLiteral("appVersion"), QApplication::applicationVersion());
    engine.loadFromModule(QStringLiteral("Proton.VPN.KDE"), QStringLiteral("Main"));
    if (engine.rootObjects().isEmpty()) {
        return 1;
    }

    auto *window = qobject_cast<QQuickWindow *>(engine.rootObjects().constFirst());
    KDBusService applicationService(KDBusService::Unique);
    QObject::connect(
        &applicationService, &KDBusService::activateRequested, window,
        [window](const QStringList &arguments, const QString &) {
            if (arguments.contains(QStringLiteral("--settings"))) {
                QMetaObject::invokeMethod(window, "showSettings");
            }
            window->show();
            window->raise();
            window->requestActivate();
        });
    TrayIntegration tray(&controller, &settings, &lifecycle, window);
    ShortcutIntegration shortcuts(&controller, window);
    NotificationIntegration notifications(&controller, &settings);

    return app.exec();
}
