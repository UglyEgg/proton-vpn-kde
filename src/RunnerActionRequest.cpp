#include "RunnerActionRequest.h"

#include <QRegularExpression>

namespace
{
constexpr qsizetype kMaximumServerNameLength = 64;

bool isCountryCode(QStringView value)
{
    static const QRegularExpression pattern(QStringLiteral("^[A-Z]{2}$"));
    return pattern.matchView(value).hasMatch();
}

bool isServerName(QStringView value)
{
    if (value.isEmpty() || value.size() > kMaximumServerNameLength) {
        return false;
    }
    static const QRegularExpression pattern(
        QStringLiteral("^[A-Z0-9-]+#[0-9]+$"));
    return pattern.matchView(value).hasMatch();
}
}

std::optional<ProtonVpnKde::RunnerActionRequest>
ProtonVpnKde::validatedRunnerActionRequest(QStringView action,
                                           QStringView argument)
{
    if ((action == QStringView(u"fastest")
         || action == QStringView(u"disconnect"))
        && argument.isEmpty()) {
        return RunnerActionRequest{action.toString(), {}};
    }
    if (action == QStringView(u"country") && isCountryCode(argument)) {
        return RunnerActionRequest{action.toString(), argument.toString()};
    }
    if (action == QStringView(u"server") && isServerName(argument)) {
        return RunnerActionRequest{action.toString(), argument.toString()};
    }
    return std::nullopt;
}
