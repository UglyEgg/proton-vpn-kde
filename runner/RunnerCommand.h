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
