// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#pragma once

#include <QString>
#include <QStringList>

class QDBusConnection;

namespace ProtonVpnKde
{
struct BackendIdentityResult
{
    bool trusted = false;
    QString uniqueOwner;
    QString error;
};

[[nodiscard]] bool isRootOwnedImmutableFile(const QString &path);
[[nodiscard]] bool areRootOwnedImmutableFiles(const QStringList &paths);
[[nodiscard]] BackendIdentityResult
verifyBackendIdentity(const QDBusConnection &bus, const QString &wellKnownName);
}
