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
    Unauthorized,
    InvalidSecretPayload,
    Rejected,
};

[[nodiscard]] inline bool isTransientSameOwnerFailure(
    QDBusError::ErrorType type)
{
    return type == QDBusError::NoReply || type == QDBusError::Timeout
        || type == QDBusError::NoNetwork;
}

[[nodiscard]] inline bool isSafeBackendAuthoredMessage(
    QStringView name, QStringView message)
{
    const bool knownError =
        name == QLatin1StringView(DBusContract::Backend::Error::invalidCustomDns)
        || name
            == QLatin1StringView(
                DBusContract::Backend::Error::invalidSettings)
        || name
            == QLatin1StringView(
                DBusContract::Backend::Error::invalidSplitTunneling)
        || name
            == QLatin1StringView(
                DBusContract::Backend::Error::invalidSupportReport)
        || name
            == QLatin1StringView(
                DBusContract::Backend::Error::operationFailed);
    if (!knownError || message.isEmpty() || message.size() > 256
        || message.trimmed() != message) {
        return false;
    }
    for (const QChar character : message) {
        if (!character.isPrint()) {
            return false;
        }
    }
    return true;
}

[[nodiscard]] inline BackendCallFailure classifyBackendCallFailure(
    QDBusError::ErrorType type, QStringView name)
{
    if (name == QLatin1StringView(
                    DBusContract::Backend::Error::invalidSecretPayload)) {
        return BackendCallFailure::InvalidSecretPayload;
    }
    if (name == QLatin1StringView(
                    DBusContract::Backend::Error::unauthorized)) {
        return BackendCallFailure::Unauthorized;
    }
    switch (type) {
    case QDBusError::ServiceUnknown:
    case QDBusError::NoServer:
    case QDBusError::Disconnected:
    case QDBusError::NoReply:
    case QDBusError::Timeout:
    case QDBusError::NoNetwork:
        // The caller must check isTransientSameOwnerFailure() before treating
        // these as owner loss. Classification remains conservative for older
        // consumers that cannot reconcile a same-owner operation.
        return BackendCallFailure::Unavailable;
    default:
        return BackendCallFailure::Rejected;
    }
}
}
