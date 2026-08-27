#include "TrayIntegration.h"

#include "VpnController.h"

#include <QAction>
#include <QApplication>
#include <QIcon>
#include <QMenu>
#include <QWindow>

#ifdef HAVE_KSTATUSNOTIFIERITEM
#include <KStatusNotifierItem>
#else
#include <QSystemTrayIcon>
#endif

TrayIntegration::TrayIntegration(VpnController *controller, QWindow *window,
                                 QObject *parent)
    : QObject(parent)
    , m_controller(controller)
    , m_window(window)
    , m_menu(new QMenu)
{
    m_showAction = m_menu->addAction(tr("Show Proton VPN"));
    m_connectionAction = m_menu->addAction(tr("Connect fastest"));
    m_menu->addSeparator();
    QAction *quitAction = m_menu->addAction(tr("Quit"));

    connect(m_showAction, &QAction::triggered, this, &TrayIntegration::toggleWindow);
    connect(m_connectionAction, &QAction::triggered,
            m_controller, &VpnController::activatePrimaryAction);
    connect(quitAction, &QAction::triggered, qApp, &QApplication::quit);
    connect(m_controller, &VpnController::snapshotChanged,
            this, &TrayIntegration::updateState);

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

#ifdef HAVE_KSTATUSNOTIFIERITEM
    m_tray->setToolTipTitle(tr("Proton VPN"));
    m_tray->setToolTipSubTitle(tooltip);
    m_tray->setStatus(connected ? KStatusNotifierItem::Active
                                : KStatusNotifierItem::Passive);
#else
    m_tray->setToolTip(tooltip);
#endif
}
