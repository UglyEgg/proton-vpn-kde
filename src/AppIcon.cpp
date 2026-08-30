// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#include "AppIcon.h"

QIcon ProtonVpnKde::applicationIcon()
{
    return applicationIcon(QStringLiteral("color"));
}

QIcon ProtonVpnKde::applicationIcon(const QString &style)
{
    return QIcon(applicationIconSource(style));
}

QString ProtonVpnKde::applicationIconSource(const QString &style)
{
    const QString normalized = style.trimmed().toLower();
    if (normalized == QStringLiteral("light")) {
        return QStringLiteral(":/data/plasma-vpn-light.svg");
    }
    if (normalized == QStringLiteral("dark")) {
        return QStringLiteral(":/data/plasma-vpn-dark.svg");
    }
    return QStringLiteral(":/data/plasma-vpn.svg");
}
