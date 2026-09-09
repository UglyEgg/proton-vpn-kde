// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#include "NativeStartup.h"
#include "UnsafeBackendEnvironment.generated.h"

#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <string>
#include <string_view>
#include <unistd.h>

// Link-time failure injection belongs only to this probe, never the app.
extern "C" int __real_execv(const char *, char *const []);
extern "C" int __wrap_execv(const char *file, char *const argv[])
{
    if (std::getenv("PLASMA_VPN_TEST_FAIL_EXEC") != nullptr) {
        errno = ENOENT;
        return -1;
    }
    return __real_execv(file, argv);
}

extern "C" int __real_unsetenv(const char *);
extern "C" int __wrap_unsetenv(const char *name)
{
    if (std::getenv("PLASMA_VPN_TEST_FAIL_UNSET") != nullptr) {
        errno = EPERM;
        return -1;
    }
    return __real_unsetenv(name);
}

int main(int argc, char *argv[])
{
    std::printf("entry:%ld\n", static_cast<long>(::getpid()));
    std::fflush(stdout);
    if (argc > 1 && std::string_view(argv[1]) == "--unset-only") {
        // Negative control: a late environment scrub must fail the /proc check.
        for (const auto prefix : ProtonVpnKde::kUnsafeBackendEnvironmentPrefixes) {
            const std::string name(prefix.substr(0, prefix.size() - 1));
            ::unsetenv(name.c_str());
        }
    } else {
        ProtonVpnKde::prepareNativeStartup(argv);
    }

    std::ifstream environment("/proc/self/environ", std::ios::binary);
    if (!environment) {
        return 2;
    }
    std::string entry;
    while (std::getline(environment, entry, '\0')) {
        for (const auto prefix : ProtonVpnKde::kUnsafeBackendEnvironmentPrefixes) {
            if (entry.starts_with(prefix)) {
                return 3;
            }
        }
    }
    for (const auto prefix : ProtonVpnKde::kUnsafeBackendEnvironmentPrefixes) {
        const std::string name(prefix.substr(0, prefix.size() - 1));
        if (std::getenv(name.c_str()) != nullptr) {
            return 4;
        }
    }
    for (int index = 0; index < argc; ++index) {
        std::printf("%s%c", argv[index], '\0');
    }
    for (const char *name : {"HOME", "DBUS_SESSION_BUS_ADDRESS", "OPENSSL_CONFUSION"}) {
        const char *value = std::getenv(name);
        std::printf("%s%c", value == nullptr ? "<missing>" : value, '\0');
    }
    return 0;
}
