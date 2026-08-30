// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#pragma once

#include <QDBusError>
#include <QStringView>

namespace ProtonVpnKde
{
enum class BackendCallFailure
{
    Unavailable,
    InvalidSecretPayload,
    Rejected,
};

[[nodiscard]] inline BackendCallFailure classifyBackendCallFailure(
    QDBusError::ErrorType type, QStringView name)
{
    if (name == u"quest.entropy.PlasmaVPN.Error.InvalidSecretPayload") {
        return BackendCallFailure::InvalidSecretPayload;
    }
    switch (type) {
    case QDBusError::ServiceUnknown:
    case QDBusError::NoReply:
    case QDBusError::NoServer:
    case QDBusError::Timeout:
    case QDBusError::NoNetwork:
    case QDBusError::Disconnected:
        return BackendCallFailure::Unavailable;
    default:
        return BackendCallFailure::Rejected;
    }
}
}
