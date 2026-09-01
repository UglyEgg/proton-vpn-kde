// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#pragma once

#include <QString>

namespace ProtonVpnKde
{
[[nodiscard]] QString controlCenterExecutablePath();
[[nodiscard]] QString agentExecutablePath();
[[nodiscard]] QString systemSettingsExecutablePath();
}
