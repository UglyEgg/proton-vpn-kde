// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#include "InstalledExecutablePaths.h"

#ifndef PROTON_VPN_KDE_CONTROL_CENTER_EXECUTABLE_PATH
#error "The installed Control Center path must be configured"
#endif

#ifndef PROTON_VPN_KDE_AGENT_EXECUTABLE_PATH
#error "The installed agent path must be configured"
#endif

#ifndef PROTON_VPN_KDE_SYSTEM_SETTINGS_EXECUTABLE_PATH
#error "The installed System Settings path must be configured"
#endif

QString ProtonVpnKde::controlCenterExecutablePath()
{
    return QStringLiteral(PROTON_VPN_KDE_CONTROL_CENTER_EXECUTABLE_PATH);
}

QString ProtonVpnKde::agentExecutablePath()
{
    return QStringLiteral(PROTON_VPN_KDE_AGENT_EXECUTABLE_PATH);
}

QString ProtonVpnKde::systemSettingsExecutablePath()
{
    return QStringLiteral(PROTON_VPN_KDE_SYSTEM_SETTINGS_EXECUTABLE_PATH);
}
