#include "NotificationIntegration.h"

#include "AppSettings.h"
#include "VpnController.h"

#include <KNotification>

NotificationIntegration::NotificationIntegration(
    VpnController *controller, AppSettings *settings, QObject *parent)
    : QObject(parent)
    , m_controller(controller)
    , m_settings(settings)
{
    connect(m_controller, &VpnController::snapshotChanged,
            this, &NotificationIntegration::updateState);
    updateState();
}

void NotificationIntegration::updateState()
{
    const QString state = m_controller->state();
    if (!m_initialized) {
        m_previousState = state;
        m_initialized = true;
        return;
    }

    if (!m_settings->notificationsEnabled() || state == m_previousState) {
        m_previousState = state;
        return;
    }

    if (state == QStringLiteral("connected")) {
        const QString server = m_controller->serverName();
        KNotification::event(
            QStringLiteral("connected"),
            tr("VPN connected"),
            server.isEmpty() ? tr("Your traffic is protected")
                             : tr("Connected to %1").arg(server),
            QStringLiteral("security-high"),
            KNotification::CloseOnTimeout,
            QStringLiteral("proton-vpn-kde"));
    } else if (state == QStringLiteral("disconnected")
               && (m_previousState == QStringLiteral("connected")
                   || m_previousState == QStringLiteral("disconnecting"))) {
        KNotification::event(
            QStringLiteral("disconnected"),
            tr("VPN disconnected"),
            tr("Your traffic is no longer using Proton VPN"),
            QStringLiteral("network-vpn-disconnected"),
            KNotification::CloseOnTimeout,
            QStringLiteral("proton-vpn-kde"));
    } else if (state == QStringLiteral("error")) {
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
}
