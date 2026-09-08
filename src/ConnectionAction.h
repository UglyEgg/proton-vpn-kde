// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#pragma once

#include <QStringView>

namespace ProtonVpnKde
{
inline bool primaryActionDisconnects(QStringView state)
{
    return state == QStringView(u"connected")
        || state == QStringView(u"connecting")
        || state == QStringView(u"disconnecting")
        || state == QStringView(u"error");
}

struct ConnectionActionCapabilities
{
    bool connect = false;
    bool disconnect = false;
    bool activate = false;
    bool primaryDisconnects = false;
    bool waitForDisconnect = false;
    bool idleDisconnected = false;
};

inline bool accountAllowsConnection(QStringView authState)
{
    return authState == QStringView(u"signed_in")
        || authState == QStringView(u"signed_in_degraded");
}

// This is client admission, not a substitute for backend operation ownership.
// Schema 1 exposes busy but not the remote operation kind. An explicit
// Disconnect may request cleanup during that interval; the backend waits for
// unrelated accepted work under its cleanup deadline. Busy never authorizes Up.
inline ConnectionActionCapabilities connectionActionCapabilities(
    bool available, bool ready, bool healthy, bool loggedIn, bool busy,
    QStringView state, QStringView authState, bool allowActivation = false)
{
    ConnectionActionCapabilities result;
    result.primaryDisconnects = primaryActionDisconnects(state);
    if (!available) {
        result.activate = allowActivation;
        // A cold agent may request activation, not act on its stale state.
        result.primaryDisconnects = false;
        return result;
    }
    if (!ready || !healthy) {
        return result;
    }
    result.idleDisconnected = !busy && state == QStringView(u"disconnected");
    result.waitForDisconnect = state == QStringView(u"disconnecting");
    result.disconnect = state == QStringView(u"connected")
        || state == QStringView(u"connecting") || state == QStringView(u"error")
        || (state == QStringView(u"disconnected") && busy);
    result.connect = loggedIn && accountAllowsConnection(authState) && !busy
        && (state == QStringView(u"disconnected") || state == QStringView(u"connected")
            || state == QStringView(u"error"));
    return result;
}
}
