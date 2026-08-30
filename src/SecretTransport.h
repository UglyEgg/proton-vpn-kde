// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#pragma once

#include <QDBusUnixFileDescriptor>
#include <QJsonObject>
#include <QString>

class QByteArray;

namespace SecretTransport
{
[[nodiscard]] QDBusUnixFileDescriptor createSealedPayload(
    const QJsonObject &fields, const QByteArray &backendPublicKey,
    QString *errorMessage = nullptr);
}
