// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#pragma once

#include <QJsonDocument>
#include <QJsonObject>
#include <QString>

namespace ProtonVpnKde::TestData
{
inline QString completeSnapshot(const QString &state = QStringLiteral("disconnected"),
                                bool loggedIn = true, bool ready = true)
{
    const QJsonObject snapshot{
        {QStringLiteral("schemaVersion"), 1},
        {QStringLiteral("ready"), ready},
        {QStringLiteral("startupCompatible"), true},
        {QStringLiteral("loggedIn"), loggedIn},
        {QStringLiteral("authState"),
         loggedIn ? QStringLiteral("signed_in")
                  : QStringLiteral("signed_out")},
        {QStringLiteral("accountName"),
         loggedIn ? QStringLiteral("test-user") : QString()},
        {QStringLiteral("planTitle"),
         loggedIn ? QStringLiteral("VPN Plus") : QString()},
        {QStringLiteral("userTier"), loggedIn ? 2 : 0},
        {QStringLiteral("maxConnections"), loggedIn ? 10 : 0},
        {QStringLiteral("fido2Available"), false},
        {QStringLiteral("reconnectEnabled"), true},
        {QStringLiteral("killSwitch"), 0},
        {QStringLiteral("busy"), false},
        {QStringLiteral("state"), state},
        {QStringLiteral("errorCode"), QString()},
        {QStringLiteral("serverName"), QString()},
        {QStringLiteral("serverLocation"), QString()},
        {QStringLiteral("exitCountry"), QString()},
        {QStringLiteral("entryCountry"), QString()},
        {QStringLiteral("forwardedPort"), 0},
        {QStringLiteral("secureCore"), false},
        {QStringLiteral("tor"), false},
        {QStringLiteral("p2p"), false},
        {QStringLiteral("streaming"), false},
        {QStringLiteral("smartRouting"), false},
        {QStringLiteral("packetCaptureActive"), false},
        {QStringLiteral("coreMemoryOptimized"), false},
        {QStringLiteral("coreVersion"), QStringLiteral("5.7.0")},
        {QStringLiteral("message"), QString()},
    };
    return QString::fromUtf8(QJsonDocument(snapshot).toJson(QJsonDocument::Compact));
}
} // namespace ProtonVpnKde::TestData
