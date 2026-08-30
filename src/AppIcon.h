// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#pragma once

#include <QIcon>
#include <QString>

namespace ProtonVpnKde
{
[[nodiscard]] QIcon applicationIcon();
[[nodiscard]] QIcon applicationIcon(const QString &style);
[[nodiscard]] QString applicationIconSource(const QString &style);
}
