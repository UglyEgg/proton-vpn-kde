// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#include "BackgroundQuitCoordinator.h"

#include "VpnConnectionController.h"

BackgroundQuitCoordinator::BackgroundQuitCoordinator(
    VpnConnectionController *controller, int disconnectTimeoutMs,
    QObject *parent)
    : QObject(parent)
    , m_controller(controller)
{
    Q_ASSERT(m_controller);
    m_disconnectTimeout.setSingleShot(true);
    m_disconnectTimeout.setInterval(qMax(1, disconnectTimeoutMs));
    connect(m_controller, &VpnConnectionController::snapshotChanged,
            this, &BackgroundQuitCoordinator::finishIfDisconnected);
    connect(&m_disconnectTimeout, &QTimer::timeout, this, [this] {
        if (!m_pending) {
            return;
        }
        setPending(false);
        emit disconnectTimedOut();
    });
}

bool BackgroundQuitCoordinator::pending() const
{
    return m_pending;
}

void BackgroundQuitCoordinator::disconnectAndQuit()
{
    if (m_pending) {
        return;
    }
    if (m_controller->state() == QStringLiteral("disconnected")) {
        emit readyToQuit();
        return;
    }

    setPending(true);
    m_disconnectTimeout.start();
    if (m_controller->state() != QStringLiteral("disconnecting")) {
        m_controller->disconnect();
    }
    finishIfDisconnected();
}

void BackgroundQuitCoordinator::finishIfDisconnected()
{
    if (!m_pending || !m_controller->backendAvailable()
        || m_controller->busy()
        || m_controller->state() != QStringLiteral("disconnected")) {
        return;
    }
    m_disconnectTimeout.stop();
    setPending(false);
    emit readyToQuit();
}

void BackgroundQuitCoordinator::setPending(bool pending)
{
    if (m_pending == pending) {
        return;
    }
    m_pending = pending;
    emit pendingChanged();
}
