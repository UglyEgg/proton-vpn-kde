#include "TrayIntegration.h"

#include "AppIcon.h"
#include "AppSettings.h"
#include "VpnConnectionController.h"

#include <QAction>
#include <QApplication>
#include <QIcon>
#include <QMenu>
#include <utility>

#ifdef HAVE_KSTATUSNOTIFIERITEM
#include <KStatusNotifierItem>
#else
#include <QSystemTrayIcon>
#endif

TrayIntegration::TrayIntegration(VpnConnectionController *controller,
                                 AppSettings *settings,
                                 std::function<void()> showControlCenter,
                                 QObject *parent)
    : QObject(parent)
    , m_controller(controller)
    , m_settings(settings)
    , m_showControlCenter(std::move(showControlCenter))
    , m_menu(new QMenu)
{
    m_showAction = m_menu->addAction(tr("Show Plasma VPN"));
    m_connectionAction = m_menu->addAction(tr("Connect fastest"));
    m_pinnedSeparator = m_menu->addSeparator();
    QAction *quitAction = m_menu->addAction(tr("Quit background controls"));

    connect(m_showAction, &QAction::triggered,
            this, &TrayIntegration::showControlCenter);
    connect(m_connectionAction, &QAction::triggered,
            m_controller, &VpnConnectionController::activatePrimaryAction);
    connect(quitAction, &QAction::triggered,
            qApp, &QCoreApplication::quit);
    connect(m_controller, &VpnConnectionController::snapshotChanged,
            this, &TrayIntegration::updateState);
    connect(m_settings, &AppSettings::pinnedServersChanged,
            this, &TrayIntegration::rebuildPinnedActions);
    connect(m_settings, &AppSettings::pinnedServerGroupsChanged,
            this, &TrayIntegration::rebuildPinnedActions);
    rebuildPinnedActions();

#ifdef HAVE_KSTATUSNOTIFIERITEM
    m_tray = new KStatusNotifierItem(this);
    m_tray->setCategory(KStatusNotifierItem::SystemServices);
    m_tray->setStandardActionsEnabled(false);
    m_tray->setContextMenu(m_menu);
    m_tray->setTitle(tr("Plasma VPN"));
    connect(m_tray, &KStatusNotifierItem::activateRequested,
            this, [this](bool, const QPoint &) { this->showControlCenter(); });
#else
    m_tray = new QSystemTrayIcon(this);
    m_tray->setContextMenu(m_menu);
    m_tray->show();
    connect(m_tray, &QSystemTrayIcon::activated, this,
            [this](QSystemTrayIcon::ActivationReason reason) {
                if (reason == QSystemTrayIcon::Trigger) {
                    this->showControlCenter();
                }
            });
#endif

    connect(m_settings, &AppSettings::iconStyleChanged,
            this, &TrayIntegration::updateIcon);
    updateIcon();
    updateState();
}

void TrayIntegration::updateIcon()
{
    const QIcon icon = ProtonVpnKde::applicationIcon(
        m_settings->iconStyle());
#ifdef HAVE_KSTATUSNOTIFIERITEM
    m_tray->setIconByPixmap(icon);
#else
    m_tray->setIcon(icon);
#endif
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
            QIcon::fromTheme(QStringLiteral("window-pin")), target, m_menu);
        action->setEnabled(m_controller->primaryActionEnabled());
        connect(action, &QAction::triggered, this,
                [this, target] { m_controller->connectTarget(target); });
        m_menu->insertAction(m_pinnedSeparator, action);
        m_pinnedActions.append(action);
    }
    for (const AppSettings::PinnedServerGroup &group
         : m_settings->pinnedServerGroups()) {
        const QString label = QStringLiteral("%1 — %2")
                                  .arg(group.countryCode, group.name);
        QAction *action = new QAction(
            QIcon::fromTheme(QStringLiteral("window-pin")), label, m_menu);
        action->setEnabled(m_controller->primaryActionEnabled());
        connect(action, &QAction::triggered, this,
                [this, group] {
                    m_controller->connectGroup(
                        group.countryCode, group.kind, group.name);
                });
        m_menu->insertAction(m_pinnedSeparator, action);
        m_pinnedActions.append(action);
    }
}
void TrayIntegration::showControlCenter()
{
    if (m_showControlCenter) {
        m_showControlCenter();
    }
}

void TrayIntegration::updateState()
{
    const QString state = m_controller->state();
    const QString server = m_controller->serverName();
    const bool connected = state == QStringLiteral("connected");
    const QString tooltip = connected && !server.isEmpty()
        ? tr("Plasma VPN — connected to %1").arg(server)
        : tr("Plasma VPN — %1").arg(state);

    m_connectionAction->setText(m_controller->primaryActionText());
    m_connectionAction->setEnabled(m_controller->primaryActionEnabled());
    for (QAction *action : std::as_const(m_pinnedActions)) {
        action->setEnabled(m_controller->primaryActionEnabled());
    }

#ifdef HAVE_KSTATUSNOTIFIERITEM
    m_tray->setToolTipTitle(tr("Plasma VPN"));
    m_tray->setToolTipSubTitle(tooltip);
    m_tray->setStatus(connected ? KStatusNotifierItem::Active
                                : KStatusNotifierItem::Passive);
#else
    m_tray->setToolTip(tooltip);
#endif
}
