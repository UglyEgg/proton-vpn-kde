// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#pragma once

#include <QList>
#include <QString>
#include <QStringView>

enum class RunnerAction {
    Open,
    ConnectFastest,
    Disconnect,
    ConnectCountry,
    ConnectServer,
};

struct RunnerCommand {
    RunnerAction action;
    QString argument;
};

[[nodiscard]] QList<RunnerCommand> parseRunnerQuery(QStringView query);
