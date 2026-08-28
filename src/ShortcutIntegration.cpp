#include "ShortcutIntegration.h"

#include "VpnController.h"

#include <KGlobalAccel>
#include <QAction>
#include <QKeySequence>
#include <QList>
#include <QWindow>

ShortcutIntegration::ShortcutIntegration(VpnController *controller,
                                         QWindow *window, QObject *parent)
    : QObject(parent)
    , m_controller(controller)
    , m_window(window)
{
    QAction *toggleConnection = registerAction(
        QStringLiteral("toggle-connection"), tr("Toggle VPN connection"));
    connect(toggleConnection, &QAction::triggered,
            m_controller, &VpnController::activatePrimaryAction);

    QAction *connectFastest = registerAction(
        QStringLiteral("connect-fastest"), tr("Connect to fastest VPN server"));
    connect(connectFastest, &QAction::triggered, this, [this] {
        if (m_controller->state() == QStringLiteral("disconnected")) {
            m_controller->connectTarget(QStringLiteral("FASTEST"));
        }
    });

    QAction *disconnect = registerAction(
        QStringLiteral("disconnect"), tr("Disconnect VPN"));
    connect(disconnect, &QAction::triggered, this, [this] {
        if (m_controller->state() == QStringLiteral("connected")
            || m_controller->state() == QStringLiteral("connecting")) {
            m_controller->activatePrimaryAction();
        }
    });

    QAction *toggleWindowAction = registerAction(
        QStringLiteral("toggle-window"), tr("Show or hide Proton VPN"));
    connect(toggleWindowAction, &QAction::triggered,
            this, &ShortcutIntegration::toggleWindow);
}

QAction *ShortcutIntegration::registerAction(const QString &id,
                                             const QString &text)
{
    auto *action = new QAction(text, this);
    action->setObjectName(id);
    const QList<QKeySequence> unassigned;
    KGlobalAccel::self()->setDefaultShortcut(action, unassigned);
    KGlobalAccel::self()->setShortcut(action, unassigned);
    return action;
}

void ShortcutIntegration::toggleWindow()
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
