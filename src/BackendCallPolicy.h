// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#pragma once

#include "DbusContract.h"

#include <QDBusError>
#include <QLatin1StringView>
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
    if (name == QLatin1StringView(
                    DBusContract::Backend::Error::invalidSecretPayload)) {
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
