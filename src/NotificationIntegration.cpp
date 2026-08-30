// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#include "NotificationIntegration.h"

#include "AppSettings.h"
#include "VpnConnectionController.h"

#include <KNotification>
#include <QGuiApplication>

NotificationIntegration::NotificationIntegration(
    VpnConnectionController *controller, AppSettings *settings, QObject *parent)
    : QObject(parent)
    , m_controller(controller)
    , m_settings(settings)
{
    connect(m_controller, &VpnConnectionController::snapshotChanged,
            this, &NotificationIntegration::updateState);
    updateState();
}

void NotificationIntegration::updateState()
{
    const QString state = m_controller->state();
    const int forwardedPort = m_controller->forwardedPort();
    if (!m_initialized) {
        m_previousState = state;
        m_previousForwardedPort = forwardedPort;
        m_initialized = true;
        return;
    }

    if (m_settings->notificationsEnabled()
        && state == QStringLiteral("connected")
        && forwardedPort > 0
        && forwardedPort != m_previousForwardedPort
        && QGuiApplication::applicationState() != Qt::ApplicationActive) {
        KNotification::event(
            QStringLiteral("portForwarding"),
            tr("Port forwarding"),
            tr("Active port is %1").arg(forwardedPort),
            QStringLiteral("network-server"),
            KNotification::CloseOnTimeout,
            QStringLiteral("proton-vpn-kde"));
    }

    if (m_settings->notificationsEnabled()
        && state != m_previousState
        && state == QStringLiteral("connected")) {
        const QString server = m_controller->serverName();
        KNotification::event(
            QStringLiteral("connected"),
            tr("VPN connected"),
            server.isEmpty() ? tr("Your traffic is protected")
                             : tr("Connected to %1").arg(server),
            QStringLiteral("security-high"),
            KNotification::CloseOnTimeout,
            QStringLiteral("proton-vpn-kde"));
    } else if (m_settings->notificationsEnabled()
               && state != m_previousState
               && state == QStringLiteral("disconnected")
               && (m_previousState == QStringLiteral("connected")
                   || m_previousState == QStringLiteral("disconnecting"))) {
        KNotification::event(
            QStringLiteral("disconnected"),
            tr("VPN disconnected"),
            tr("Your traffic is no longer using Proton VPN"),
            QStringLiteral("network-vpn-disconnected"),
            KNotification::CloseOnTimeout,
            QStringLiteral("proton-vpn-kde"));
    } else if (m_settings->notificationsEnabled()
               && state != m_previousState
               && state == QStringLiteral("error")) {
        KNotification::event(
            QStringLiteral("connectionError"),
            tr("VPN connection problem"),
            m_controller->message().isEmpty()
                ? tr("Proton VPN encountered a connection error")
                : m_controller->message(),
            QStringLiteral("dialog-error"),
            KNotification::CloseOnTimeout,
            QStringLiteral("proton-vpn-kde"));
    }

    m_previousState = state;
    m_previousForwardedPort = forwardedPort;
}
