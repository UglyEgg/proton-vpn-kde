// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#include "NativeStartup.h"
#include "UnsafeBackendEnvironment.generated.h"

#include <cstdio>
#include <cstdlib>
#include <string>
#include <unistd.h>

void ProtonVpnKde::prepareNativeStartup(char *const argv[])
{
    bool changed = false;
    for (const auto prefix : kUnsafeBackendEnvironmentPrefixes) {
        const std::string name(prefix.substr(0, prefix.size() - 1));
        if (std::getenv(name.c_str()) == nullptr) {
            continue;
        }
        if (::unsetenv(name.c_str()) != 0) {
            std::perror("Plasma VPN could not clean its startup environment");
            std::_Exit(EXIT_FAILURE);
        }
        changed = true;
    }
    if (!changed) {
        return;
    }

    // unsetenv alone leaves the initial environment visible in /proc, which
    // the backend authenticates. Replace it before QApplication initializes
    // plugins, using the same executable and arguments without PATH lookup or
    // a child process.
    ::execv("/proc/self/exe", argv);
    std::perror("Plasma VPN could not restart with a clean startup environment");
    std::_Exit(EXIT_FAILURE);
}
