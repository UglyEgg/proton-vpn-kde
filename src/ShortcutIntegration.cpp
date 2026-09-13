// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#include "ShortcutIntegration.h"

#include "AgentControl.h"
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
    connect(toggleConnection, &QAction::triggered, this, [this] {
        if (!m_controller->primaryActionEnabled()) {
            return;
        }
        const QString action = m_controller->primaryActionDisconnects()
            ? QStringLiteral("disconnect") : QStringLiteral("fastest");
        ProtonVpnKde::requestConfirmedControlCenterAction(action);
    });

    QAction *connectFastest = registerAction(
        QStringLiteral("connect-fastest"), tr("Connect to fastest VPN server"));
    connect(connectFastest, &QAction::triggered, this, [this] {
        if (m_controller->canConnect()) {
            ProtonVpnKde::requestConfirmedControlCenterAction(
                QStringLiteral("fastest"));
        }
    });

    QAction *disconnect = registerAction(
        QStringLiteral("disconnect"), tr("Disconnect VPN"));
    connect(disconnect, &QAction::triggered, this, [this] {
        if (m_controller->canDisconnect()) {
            ProtonVpnKde::requestConfirmedControlCenterAction(
                QStringLiteral("disconnect"));
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
