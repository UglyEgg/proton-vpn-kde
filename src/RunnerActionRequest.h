// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#pragma once

#include <QString>
#include <QStringView>

#include <optional>

namespace ProtonVpnKde
{
struct RunnerActionRequest {
    QString action;
    QString argument;
};

[[nodiscard]] std::optional<RunnerActionRequest>
validatedRunnerActionRequest(QStringView action, QStringView argument);
}
