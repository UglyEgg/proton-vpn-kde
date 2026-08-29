#include "AgentControl.h"
#include "AppSettings.h"
#include "TranslationLoader.h"
#include "UpdateChannel.h"
#include "VpnController.h"

#include <QApplication>
#include <QCommandLineOption>
#include <QCommandLineParser>
#include <QDebug>
#include <QIcon>
#include <QImage>
#include <QQmlApplicationEngine>
#include <QQmlContext>
#include <QQuickWindow>
#include <QTimer>

int main(int argc, char *argv[])
{
    QApplication app(argc, argv);
    QApplication::setApplicationName(QStringLiteral("proton-vpn-kde"));
    QApplication::setApplicationDisplayName(QStringLiteral("Proton VPN for Plasma"));
    QApplication::setApplicationVersion(QStringLiteral(PROTON_VPN_KDE_VERSION));
    QApplication::setOrganizationDomain(QStringLiteral("proton.me"));
    QApplication::setDesktopFileName(QStringLiteral("proton-vpn-kde"));
    QApplication::setWindowIcon(QIcon::fromTheme(
        QStringLiteral("proton-vpn-kde"),
        QIcon::fromTheme(QStringLiteral("network-vpn"))));
    QApplication::setQuitOnLastWindowClosed(true);
    TranslationLoader::installSystemLocale(app);

    QCommandLineParser commandLine;
    commandLine.setApplicationDescription(
        QStringLiteral("Native Proton VPN client for KDE Plasma"));
    commandLine.addHelpOption();
    commandLine.addVersionOption();
    const QCommandLineOption settingsOption(
        QStringLiteral("settings"),
        QStringLiteral("Open the Proton VPN settings page"));
    const QCommandLineOption diagnosticSmokeOption(
        QStringLiteral("diagnostics-smoke"),
        QStringLiteral("Exercise native pages and quit (internal test option)"));
    const QCommandLineOption showOption(
        QStringLiteral("show"),
        QStringLiteral("Show the Proton VPN Control Center"));
    const QCommandLineOption visualSnapshotOption(
        QStringLiteral("visual-snapshot"),
        QStringLiteral("Save one rendered page and quit (internal test option)"),
        QStringLiteral("path"));
    const QCommandLineOption visualPageOption(
        QStringLiteral("visual-page"),
        QStringLiteral("Page used with --visual-snapshot"),
        QStringLiteral("page"), QStringLiteral("overview"));
    commandLine.addOption(settingsOption);
    commandLine.addOption(diagnosticSmokeOption);
    commandLine.addOption(showOption);
    commandLine.addOption(visualSnapshotOption);
    commandLine.addOption(visualPageOption);
    commandLine.process(app);
    const bool openSettings = commandLine.isSet(settingsOption);
    const bool diagnosticSmoke = commandLine.isSet(diagnosticSmokeOption);
    const bool forceShow = commandLine.isSet(showOption);
    const QString visualSnapshotPath = commandLine.value(visualSnapshotOption);
    const bool visualSnapshot = !visualSnapshotPath.isEmpty();
    const bool internalTest = diagnosticSmoke || visualSnapshot;

    if (internalTest
        && qEnvironmentVariableIntValue("PROTON_KDE_DIAGNOSTIC_RTL") == 1) {
        QApplication::setLayoutDirection(Qt::RightToLeft);
    }

    ControlCenterControl controlCenter;
    if (!internalTest && !controlCenter.registerOnSessionBus()) {
        ProtonVpnKde::requestControlCenter(openSettings);
        return 0;
    }

    AppSettings settings;
    if (!internalTest) {
        ProtonVpnKde::setAgentEnabled(settings.closeToTray());
        QObject::connect(&settings, &AppSettings::closeToTrayChanged,
                         &app, [&settings] {
            ProtonVpnKde::setAgentEnabled(settings.closeToTray());
        });
        if (settings.closeToTray() && settings.startMinimized()
            && !openSettings && !forceShow) {
            return 0;
        }
    }

    UpdateChannel updateChannel;
    VpnController controller;
    bool startupActionHandled = false;
    controller.setReconnectionEnabled(settings.reconnectEnabled());
    QObject::connect(&settings, &AppSettings::reconnectEnabledChanged,
                     &controller, [&settings, &controller] {
        controller.setReconnectionEnabled(settings.reconnectEnabled());
    });
    QObject::connect(&controller, &VpnController::snapshotChanged,
                     &app, [&controller, &settings, &startupActionHandled] {
        if (settings.closeToTray() || startupActionHandled
            || !controller.ready()) {
            return;
        }
        startupActionHandled = true;
        if (controller.loggedIn()
            && controller.state() == QStringLiteral("disconnected")
            && !settings.autoConnectTarget().isEmpty()) {
            controller.connectTarget(settings.autoConnectTarget());
        }
    });

    QQmlApplicationEngine engine;
    engine.rootContext()->setContextProperty(
        QStringLiteral("vpnController"), &controller);
    engine.rootContext()->setContextProperty(
        QStringLiteral("appSettings"), &settings);
    engine.rootContext()->setContextProperty(
        QStringLiteral("updateChannel"), &updateChannel);
    engine.rootContext()->setContextProperty(
        QStringLiteral("startMinimized"), false);
    QString initialPage = openSettings ? QStringLiteral("settings")
                                       : QStringLiteral("overview");
    if (visualSnapshot) {
        initialPage = commandLine.value(visualPageOption).toLower();
    }
    engine.rootContext()->setContextProperty(
        QStringLiteral("initialPageName"), initialPage);
    engine.rootContext()->setContextProperty(
        QStringLiteral("diagnosticSmokeTest"), diagnosticSmoke);
    engine.rootContext()->setContextProperty(
        QStringLiteral("diagnosticWindowWidth"),
        qEnvironmentVariableIntValue("PROTON_KDE_DIAGNOSTIC_WIDTH"));
    engine.rootContext()->setContextProperty(
        QStringLiteral("diagnosticWindowHeight"),
        qEnvironmentVariableIntValue("PROTON_KDE_DIAGNOSTIC_HEIGHT"));
    engine.rootContext()->setContextProperty(
        QStringLiteral("appVersion"), QApplication::applicationVersion());
    if (diagnosticSmoke) {
        qInfo() << "diagnostics-smoke: loading native interface";
    }
    engine.loadFromModule(QStringLiteral("Proton.VPN.KDE"), QStringLiteral("Main"));
    if (engine.rootObjects().isEmpty()) {
        qWarning() << "The native interface did not create an application window";
        return 1;
    }
    if (diagnosticSmoke) {
        qInfo() << "diagnostics-smoke: native interface loaded";
    }

    auto *window = qobject_cast<QQuickWindow *>(engine.rootObjects().constFirst());
    controlCenter.setWindow(window);
    QObject::connect(&app, &QCoreApplication::aboutToQuit, window, [window] {
        QMetaObject::invokeMethod(window, "prepareForQuit");
    });
    if (visualSnapshot) {
        const int requestedDelay = qEnvironmentVariableIntValue(
            "PROTON_KDE_SNAPSHOT_DELAY_MS");
        const int snapshotDelay = requestedDelay > 0 ? requestedDelay : 1200;
        QTimer::singleShot(snapshotDelay, window,
                           [window, visualSnapshotPath, &app] {
            const QImage image = window->grabWindow();
            if (image.isNull() || !image.save(visualSnapshotPath)) {
                qWarning() << "Unable to save visual snapshot to"
                           << visualSnapshotPath;
                app.exit(1);
                return;
            }
            qInfo() << "Saved visual snapshot to" << visualSnapshotPath;
            app.quit();
        });
    }
    return app.exec();
}
