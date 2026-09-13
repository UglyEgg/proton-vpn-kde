// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#pragma once

#include <QByteArray>
#include <QString>
#include <QStringList>
#include <functional>

class QDBusConnection;
class QObject;

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
[[nodiscard]] bool isBackendEnvironmentSafe(const QByteArray &environment);
void verifyBackendIdentity(const QDBusConnection &bus, const QString &wellKnownName,
                           QObject *context,
                           std::function<void(BackendIdentityResult)> completed);
void discoverBackendService(const QDBusConnection &bus, const QString &wellKnownName,
                            bool activate, QObject *context,
                            std::function<void(bool)> completed);
}
