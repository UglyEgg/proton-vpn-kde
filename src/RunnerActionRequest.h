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
