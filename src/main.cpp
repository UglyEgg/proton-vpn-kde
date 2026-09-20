// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#include "AgentControl.h"
#include "AppIcon.h"
#include "AppSettings.h"
#include "BackendIdentity.h"
#include "ConnectionAction.h"
#include "CommunityReport.h"
#include "DesktopReadiness.h"
#include "NativeStartup.h"
#include "TranslationLoader.h"
#include "UpdateChannel.h"
#include "VpnController.h"

#include <QApplication>
#include <QCommandLineOption>
#include <QCommandLineParser>
#include <QDebug>
#include <QEvent>
#include <QFile>
#include <QImage>
#include <QQmlApplicationEngine>
#include <QQmlContext>
#include <QQuickWindow>
#include <QScreen>
#include <QTimer>
#include <QVariant>

#include <memory>
#include <optional>

namespace
{
struct ProcessMemorySample {
    quint64 pssKiB = 0;
    quint64 privateKiB = 0;
};

std::optional<ProcessMemorySample> selfMemorySample()
{
    QFile rollup(QStringLiteral("/proc/self/smaps_rollup"));
    if (!rollup.open(QIODevice::ReadOnly | QIODevice::Text)) {
        return std::nullopt;
    }
    ProcessMemorySample sample;
    bool foundPss = false;
    bool foundPrivateClean = false;
    bool foundPrivateDirty = false;
    const QList<QByteArray> lines = rollup.readAll().split('\n');
    for (const QByteArray &line : lines) {
        const bool isPss = line.startsWith("Pss:");
        const bool isPrivateClean = line.startsWith("Private_Clean:");
        const bool isPrivateDirty = line.startsWith("Private_Dirty:");
        if (!isPss && !isPrivateClean && !isPrivateDirty) {
            continue;
        }
        const QList<QByteArray> fields = line.simplified().split(' ');
        bool valid = false;
        const quint64 value = fields.size() >= 2
            ? fields.at(1).toULongLong(&valid) : 0;
        if (!valid) {
            return std::nullopt;
        }
        if (isPss) {
            sample.pssKiB = value;
            foundPss = true;
        } else {
            sample.privateKiB += value;
            foundPrivateClean = foundPrivateClean || isPrivateClean;
            foundPrivateDirty = foundPrivateDirty || isPrivateDirty;
        }
    }
    if (!foundPss || !foundPrivateClean || !foundPrivateDirty) {
        return std::nullopt;
    }
    return sample;
}

struct InspectorRetentionSamples {
    ProcessMemorySample baseline;
    ProcessMemorySample firstOpen;
    ProcessMemorySample firstClosed;
    ProcessMemorySample secondOpen;
};
}

int main(int argc, char *argv[])
{
    ProtonVpnKde::prepareNativeStartup(argv);
    QApplication app(argc, argv);
    QApplication::setApplicationName(QStringLiteral("proton-vpn-kde"));
    QApplication::setApplicationDisplayName(QStringLiteral("Plasma VPN"));
    QApplication::setApplicationVersion(QStringLiteral(PROTON_VPN_KDE_VERSION));
    QApplication::setOrganizationDomain(QStringLiteral("entropy.quest"));
    QApplication::setDesktopFileName(QStringLiteral("proton-vpn-kde"));
    AppSettings settings;
    QApplication::setWindowIcon(
        ProtonVpnKde::applicationIcon(settings.iconStyle()));
    QApplication::setQuitOnLastWindowClosed(true);
    TranslationLoader::installSystemLocale(app);

    QCommandLineParser commandLine;
    commandLine.setApplicationDescription(
        QStringLiteral("Unofficial Plasma client compatible with Proton VPN"));
    commandLine.addHelpOption();
    commandLine.addVersionOption();
    const QCommandLineOption settingsOption(
        QStringLiteral("settings"),
        QStringLiteral("Open the Proton VPN settings page"));
    const QCommandLineOption diagnosticSmokeOption(
        QStringLiteral("diagnostics-smoke"),
        QStringLiteral("Exercise native pages and quit (internal test option)"));
    const QCommandLineOption settingsRouteSmokeOption(
        QStringLiteral("settings-route-smoke"),
        QStringLiteral("Exercise a settings update after sign-in navigation "
                       "(internal test option)"));
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
    const QCommandLineOption inspectorRetentionOption(
        QStringLiteral("inspector-retention-smoke"),
        QStringLiteral("Measure repeated Inspector retention (internal test option)"));
    commandLine.addOption(settingsOption);
    commandLine.addOption(diagnosticSmokeOption);
    commandLine.addOption(settingsRouteSmokeOption);
    commandLine.addOption(showOption);
    commandLine.addOption(visualSnapshotOption);
    commandLine.addOption(visualPageOption);
    commandLine.addOption(inspectorRetentionOption);
    commandLine.process(app);
    const bool openSettings = commandLine.isSet(settingsOption);
    const bool diagnosticSmoke = commandLine.isSet(diagnosticSmokeOption);
    const bool settingsRouteSmoke = commandLine.isSet(settingsRouteSmokeOption);
    const bool forceShow = commandLine.isSet(showOption);
    const QString visualSnapshotPath = commandLine.value(visualSnapshotOption);
    const bool visualSnapshot = !visualSnapshotPath.isEmpty();
    const bool inspectorRetention = commandLine.isSet(inspectorRetentionOption);
    const bool internalTest = diagnosticSmoke || settingsRouteSmoke
                              || visualSnapshot || inspectorRetention;

    if (internalTest
        && ProtonVpnKde::isRootOwnedImmutableFile(
            QCoreApplication::applicationFilePath())) {
        qCritical() << "Internal test options are unavailable in an installed build";
        return 2;
    }

    if (internalTest
        && qEnvironmentVariableIntValue("PROTON_KDE_DIAGNOSTIC_RTL") == 1) {
        QApplication::setLayoutDirection(Qt::RightToLeft);
    }

    ControlCenterControl controlCenter;
    if (!internalTest && !controlCenter.registerOnSessionBus()) {
        ProtonVpnKde::requestControlCenter(openSettings);
        return 0;
    }

    if (!internalTest) {
        if (settings.startTrayOnly(openSettings, forceShow)) {
            // A windowless launcher must keep its event loop alive until the
            // bounded activation attempt and any detached fallback settle.
            QTimer::singleShot(0, &app, [] {
                ProtonVpnKde::ensureAgentRunning([](bool started) {
                    QCoreApplication::exit(started ? 0 : 1);
                });
            });
            return app.exec();
        }
        ProtonVpnKde::setAgentEnabled(settings.closeToTray());
        QObject::connect(&settings, &AppSettings::closeToTrayChanged,
                         &app, [&settings] {
            ProtonVpnKde::setAgentEnabled(settings.closeToTray());
        });
    }

    UpdateChannel updateChannel;
    VpnController controller;
    DesktopReadiness desktopReadiness;
    CommunityReport communityReport(&controller, &desktopReadiness);
    QString startupTarget = settings.closeToTray() ? QString()
                                                  : settings.autoConnectTarget();
    const auto retireStartup = [&startupTarget] { startupTarget.clear(); };
    QObject::connect(&settings, &AppSettings::closeToTrayChanged, &app, retireStartup);
    QObject::connect(&settings, &AppSettings::autoConnectTargetChanged, &app, retireStartup);
    QObject::connect(&controller, &VpnController::connectionOperationStarted,
                     &app, retireStartup);
    controller.setReconnectionEnabled(settings.reconnectEnabled());
    controller.setFastestFeatures(settings.fastestFeatures());
    QObject::connect(&settings, &AppSettings::reconnectEnabledChanged,
                     &controller, [&settings, &controller] {
        controller.setReconnectionEnabled(settings.reconnectEnabled());
    });
    QObject::connect(&settings, &AppSettings::fastestFeaturesChanged,
                     &controller, [&settings, &controller] {
        controller.setFastestFeatures(settings.fastestFeatures());
    });
    QObject::connect(&controller, &VpnController::snapshotChanged,
                     &app, [&controller, &startupTarget] {
        const QString target = ProtonVpnKde::takeStartupConnectionTarget(
            startupTarget, controller.ready(), controller.loggedIn(),
            controller.state(), controller.canConnect());
        if (!target.isEmpty()) {
            controller.connectTarget(target);
        }
    });

    QQmlApplicationEngine engine;
    engine.rootContext()->setContextProperty(
        QStringLiteral("availableScreen"), app.primaryScreen());
    engine.rootContext()->setContextProperty(
        QStringLiteral("vpnController"), &controller);
    engine.rootContext()->setContextProperty(
        QStringLiteral("desktopReadiness"), &desktopReadiness);
    engine.rootContext()->setContextProperty(
        QStringLiteral("communityReport"), &communityReport);
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
        QStringLiteral("settingsRouteSmokeTest"), settingsRouteSmoke);
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
    engine.rootContext()->setContextProperty(
        QStringLiteral("availableScreen"), window->screen());
    QObject::connect(window, &QWindow::screenChanged, engine.rootContext(),
                     [context = engine.rootContext()](QScreen *screen) {
        context->setContextProperty(QStringLiteral("availableScreen"), screen);
    });
    window->setIcon(ProtonVpnKde::applicationIcon(settings.iconStyle()));
    QObject::connect(&settings, &AppSettings::iconStyleChanged,
                     window, [&settings, window] {
        const QIcon icon = ProtonVpnKde::applicationIcon(
            settings.iconStyle());
        QApplication::setWindowIcon(icon);
        window->setIcon(icon);
    });
    QObject::connect(
        &controlCenter, &ControlCenterControl::runnerActionRequested,
        window, [window](const QString &action, const QString &argument) {
        if (!QMetaObject::invokeMethod(
                window, "requestRunnerAction", Qt::QueuedConnection,
                Q_ARG(QVariant, QVariant(action)),
                Q_ARG(QVariant, QVariant(argument)))) {
            qWarning() << "Unable to present the KRunner action confirmation";
        }
    });
    controlCenter.setWindow(window);
    QObject::connect(&app, &QCoreApplication::aboutToQuit, window, [window] {
        QMetaObject::invokeMethod(window, "prepareForQuit");
    });
    QObject::connect(&controller, &VpnController::shutdownReady,
                     &app, [] { QCoreApplication::quit(); });
    if (visualSnapshot) {
        const int requestedDelay = qEnvironmentVariableIntValue(
            "PROTON_KDE_SNAPSHOT_DELAY_MS");
        const int snapshotDelay = requestedDelay > 0 ? requestedDelay : 1200;
        QTimer::singleShot(snapshotDelay, window,
                           [window, visualSnapshotPath, &app] {
            qInfo().noquote()
                << "visual-snapshot: current section"
                << window->property("currentSection").toString();
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
    if (inspectorRetention) {
        auto samples = std::make_shared<InspectorRetentionSamples>();
        if (!QMetaObject::invokeMethod(window, "showOverview")) {
            qCritical() << "Unable to prepare the Inspector measurement";
            return 1;
        }
        QTimer::singleShot(2000, window,
                           [window, &engine, &app, samples] {
            const auto baseline = selfMemorySample();
            if (!baseline) {
                qCritical() << "Unable to read the baseline Inspector PSS";
                app.exit(1);
                return;
            }
            if (!QMetaObject::invokeMethod(
                    window, "openOverviewDestination",
                    Q_ARG(QVariant, QVariant(QStringLiteral("inspector"))))) {
                qCritical() << "Unable to open the Inspector measurement";
                app.exit(1);
                return;
            }
            samples->baseline = *baseline;
            QTimer::singleShot(2000, window,
                               [window, &engine, &app, samples] {
                const auto firstOpen = selfMemorySample();
                if (!firstOpen
                    || !QMetaObject::invokeMethod(
                        window, "closeOverviewDestination")) {
                    qCritical() << "Unable to close the Inspector measurement";
                    app.exit(1);
                    return;
                }
                samples->firstOpen = *firstOpen;
                QCoreApplication::sendPostedEvents(nullptr,
                                                   QEvent::DeferredDelete);
                engine.collectGarbage();
                QTimer::singleShot(2000, window,
                                   [window, &engine, &app, samples] {
                    const auto firstClosed = selfMemorySample();
                    if (!firstClosed
                        || !QMetaObject::invokeMethod(
                            window, "openOverviewDestination",
                            Q_ARG(QVariant,
                                  QVariant(QStringLiteral("inspector"))))) {
                        qCritical() << "Unable to repeat Inspector measurement";
                        app.exit(1);
                        return;
                    }
                    samples->firstClosed = *firstClosed;
                    QTimer::singleShot(2000, window,
                                       [window, &engine, &app, samples] {
                        const auto secondOpen = selfMemorySample();
                        if (!secondOpen
                            || !QMetaObject::invokeMethod(
                                window, "closeOverviewDestination")) {
                            qCritical() << "Unable to finish Inspector measurement";
                            app.exit(1);
                            return;
                        }
                        samples->secondOpen = *secondOpen;
                        QCoreApplication::sendPostedEvents(
                            nullptr, QEvent::DeferredDelete);
                        engine.collectGarbage();
                        QTimer::singleShot(2000, window,
                                           [&app, samples] {
                            const auto secondClosed = selfMemorySample();
                            if (!secondClosed) {
                                qCritical() << "Unable to read Inspector retention";
                                app.exit(1);
                                return;
                            }
                            const qint64 firstPssRetained =
                                static_cast<qint64>(samples->firstClosed.pssKiB)
                                - static_cast<qint64>(samples->baseline.pssKiB);
                            const qint64 repeatPssRetained =
                                static_cast<qint64>(secondClosed->pssKiB)
                                - static_cast<qint64>(samples->firstClosed.pssKiB);
                            const qint64 firstPrivateRetained =
                                static_cast<qint64>(samples->firstClosed.privateKiB)
                                - static_cast<qint64>(samples->baseline.privateKiB);
                            const qint64 repeatPrivateRetained =
                                static_cast<qint64>(secondClosed->privateKiB)
                                - static_cast<qint64>(samples->firstClosed.privateKiB);
                            qInfo().noquote()
                                << QStringLiteral(
                                    "inspector-retention: {"
                                    "\"baselinePssKiB\":%1,\"firstOpenPssKiB\":%2,"
                                    "\"firstClosedPssKiB\":%3,\"secondOpenPssKiB\":%4,"
                                    "\"secondClosedPssKiB\":%5,\"firstPssRetainedKiB\":%6,"
                                    "\"repeatPssRetainedKiB\":%7,\"baselinePrivateKiB\":%8,"
                                    "\"firstOpenPrivateKiB\":%9,\"firstClosedPrivateKiB\":%10,"
                                    "\"secondOpenPrivateKiB\":%11,\"secondClosedPrivateKiB\":%12,"
                                    "\"firstPrivateRetainedKiB\":%13,"
                                    "\"repeatPrivateRetainedKiB\":%14}")
                                       .arg(samples->baseline.pssKiB)
                                       .arg(samples->firstOpen.pssKiB)
                                       .arg(samples->firstClosed.pssKiB)
                                       .arg(samples->secondOpen.pssKiB)
                                       .arg(secondClosed->pssKiB)
                                       .arg(firstPssRetained)
                                       .arg(repeatPssRetained)
                                       .arg(samples->baseline.privateKiB)
                                       .arg(samples->firstOpen.privateKiB)
                                       .arg(samples->firstClosed.privateKiB)
                                       .arg(samples->secondOpen.privateKiB)
                                       .arg(secondClosed->privateKiB)
                                       .arg(firstPrivateRetained)
                                       .arg(repeatPrivateRetained);
                            app.quit();
                        });
                    });
                });
            });
        });
    }
    return app.exec();
}
