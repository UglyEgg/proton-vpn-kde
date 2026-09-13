// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#include "RunnerActionRequest.h"

#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonParseError>
#include <QRegularExpression>

namespace
{
constexpr qsizetype kMaximumServerNameLength = 64;
constexpr qsizetype kMaximumGroupNameLength = 128;

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

std::optional<QString> validatedGroupArgument(QStringView argument)
{
    if (argument.isEmpty() || argument.size() > 512) {
        return std::nullopt;
    }
    QJsonParseError parseError;
    const QJsonDocument document = QJsonDocument::fromJson(
        argument.toUtf8(), &parseError);
    if (parseError.error != QJsonParseError::NoError
        || !document.isObject()) {
        return std::nullopt;
    }
    const QJsonObject object = document.object();
    if (object.size() != 3
        || !object.value(QStringLiteral("countryCode")).isString()
        || !object.value(QStringLiteral("kind")).isString()
        || !object.value(QStringLiteral("name")).isString()) {
        return std::nullopt;
    }
    const QString countryCode = object.value(
        QStringLiteral("countryCode")).toString();
    const QString kind = object.value(QStringLiteral("kind")).toString();
    const QString name = object.value(QStringLiteral("name")).toString();
    if (!isCountryCode(countryCode)
        || (kind != QStringLiteral("location")
            && kind != QStringLiteral("secure-core"))
        || name.isEmpty() || name.size() > kMaximumGroupNameLength
        || name != name.trimmed() || name.contains(QChar::Null)) {
        return std::nullopt;
    }
    const QJsonObject canonical{
        {QStringLiteral("countryCode"), countryCode},
        {QStringLiteral("kind"), kind},
        {QStringLiteral("name"), name},
    };
    return QString::fromUtf8(
        QJsonDocument(canonical).toJson(QJsonDocument::Compact));
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
    if (action == QStringView(u"group")) {
        const auto groupArgument = validatedGroupArgument(argument);
        if (groupArgument) {
            return RunnerActionRequest{action.toString(), *groupArgument};
        }
    }
    return std::nullopt;
}
