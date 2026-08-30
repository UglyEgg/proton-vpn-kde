#include "ShortcutIntegration.h"

#include "VpnConnectionController.h"

#include <KGlobalAccel>
#include <QAction>
#include <QKeySequence>
#include <QList>
#include <utility>

ShortcutIntegration::ShortcutIntegration(
    VpnConnectionController *controller,
    std::function<void()> showControlCenter, QObject *parent)
    : QObject(parent)
    , m_controller(controller)
    , m_showControlCenter(std::move(showControlCenter))
{
    QAction *toggleConnection = registerAction(
        QStringLiteral("toggle-connection"), tr("Toggle VPN connection"));
    connect(toggleConnection, &QAction::triggered,
            m_controller, &VpnConnectionController::activatePrimaryAction);

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
        QStringLiteral("toggle-window"), tr("Show Plasma VPN"));
    connect(toggleWindowAction, &QAction::triggered,
            this, &ShortcutIntegration::showControlCenter);
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

void ShortcutIntegration::showControlCenter()
{
    if (m_showControlCenter) {
        m_showControlCenter();
    }
}
