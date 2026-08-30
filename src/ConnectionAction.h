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
}
