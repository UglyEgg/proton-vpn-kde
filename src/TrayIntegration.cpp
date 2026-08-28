#include "TrayIntegration.h"

#include "AppLifecycle.h"
#include "AppSettings.h"
#include "VpnController.h"

#include <QAction>
#include <QApplication>
#include <QIcon>
#include <QMenu>
#include <QWindow>
#include <utility>

#ifdef HAVE_KSTATUSNOTIFIERITEM
#include <KStatusNotifierItem>
#else
#include <QSystemTrayIcon>
#endif

TrayIntegration::TrayIntegration(VpnController *controller, AppSettings *settings,
                                 AppLifecycle *lifecycle, QWindow *window,
                                 QObject *parent)
    : QObject(parent)
    , m_controller(controller)
    , m_settings(settings)
    , m_lifecycle(lifecycle)
    , m_window(window)
    , m_menu(new QMenu)
{
    m_showAction = m_menu->addAction(tr("Show Proton VPN"));
    m_connectionAction = m_menu->addAction(tr("Connect fastest"));
    m_pinnedSeparator = m_menu->addSeparator();
    QAction *quitAction = m_menu->addAction(tr("Quit"));

    connect(m_showAction, &QAction::triggered, this, &TrayIntegration::toggleWindow);
    connect(m_connectionAction, &QAction::triggered,
            m_controller, &VpnController::activatePrimaryAction);
    connect(quitAction, &QAction::triggered, this, [this] {
        m_lifecycle->requestQuit(
            m_controller->state(),
            m_controller->backendAvailable() && m_controller->ready()
                && m_controller->loggedIn());
    });
    connect(m_controller, &VpnController::snapshotChanged,
            this, &TrayIntegration::updateState);
    connect(m_settings, &AppSettings::pinnedServersChanged,
            this, &TrayIntegration::rebuildPinnedActions);
    rebuildPinnedActions();

#ifdef HAVE_KSTATUSNOTIFIERITEM
    m_tray = new KStatusNotifierItem(this);
    m_tray->setCategory(KStatusNotifierItem::SystemServices);
    m_tray->setStandardActionsEnabled(false);
    m_tray->setContextMenu(m_menu);
    m_tray->setIconByName(QStringLiteral("network-vpn"));
    m_tray->setTitle(tr("Proton VPN"));
    connect(m_tray, &KStatusNotifierItem::activateRequested,
            this, [this](bool, const QPoint &) { toggleWindow(); });
#else
    m_tray = new QSystemTrayIcon(QIcon::fromTheme(QStringLiteral("network-vpn")), this);
    m_tray->setContextMenu(m_menu);
    m_tray->show();
    connect(m_tray, &QSystemTrayIcon::activated, this,
            [this](QSystemTrayIcon::ActivationReason reason) {
                if (reason == QSystemTrayIcon::Trigger) {
                    toggleWindow();
                }
            });
#endif

    updateState();
}

void TrayIntegration::rebuildPinnedActions()
{
    for (QAction *action : std::as_const(m_pinnedActions)) {
        m_menu->removeAction(action);
        action->deleteLater();
    }
    m_pinnedActions.clear();

    for (const QString &target : m_settings->pinnedServers()) {
        QAction *action = new QAction(
            QIcon::fromTheme(QStringLiteral("favorite")), target, m_menu);
        action->setEnabled(m_controller->primaryActionEnabled());
        connect(action, &QAction::triggered, this,
                [this, target] { m_controller->connectTarget(target); });
        m_menu->insertAction(m_pinnedSeparator, action);
        m_pinnedActions.append(action);
    }
}
void TrayIntegration::toggleWindow()
{
    if (!m_window) {
        return;
    }
    if (m_window->isVisible()) {
        m_window->hide();
    } else {
        m_window->show();
        m_window->raise();
        m_window->requestActivate();
    }
}

void TrayIntegration::updateState()
{
    const QString state = m_controller->state();
    const QString server = m_controller->serverName();
    const bool connected = state == QStringLiteral("connected");
    const QString tooltip = connected && !server.isEmpty()
        ? tr("Proton VPN — connected to %1").arg(server)
        : tr("Proton VPN — %1").arg(state);

    m_connectionAction->setText(m_controller->primaryActionText());
    m_connectionAction->setEnabled(m_controller->primaryActionEnabled());
    for (QAction *action : std::as_const(m_pinnedActions)) {
        action->setEnabled(m_controller->primaryActionEnabled());
    }

#ifdef HAVE_KSTATUSNOTIFIERITEM
    m_tray->setToolTipTitle(tr("Proton VPN"));
    m_tray->setToolTipSubTitle(tooltip);
    m_tray->setStatus(connected ? KStatusNotifierItem::Active
                                : KStatusNotifierItem::Passive);
#else
    m_tray->setToolTip(tooltip);
#endif
}
