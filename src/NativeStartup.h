// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#pragma once

namespace ProtonVpnKde
{
// Call before QApplication or other application initialization. Re-executes
// this executable only if inherited code-loading overrides need removal.
void prepareNativeStartup(char *const argv[]);
}
