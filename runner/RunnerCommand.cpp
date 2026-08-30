// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#include "RunnerCommand.h"

#include <QRegularExpression>

namespace
{
QString commandTail(QString query)
{
    query = query.trimmed();
    static const QRegularExpression prefix(
        QStringLiteral("^(?:proton\\s+vpn|vpn)(?:\\s+|$)"),
        QRegularExpression::CaseInsensitiveOption);
    const QRegularExpressionMatch match = prefix.match(query);
    if (!match.hasMatch()) {
        return {};
    }
    return query.mid(match.capturedEnd()).trimmed();
}

bool hasRunnerPrefix(QStringView query)
{
    static const QRegularExpression prefix(
        QStringLiteral("^(?:proton\\s+vpn|vpn)(?:\\s+|$)"),
        QRegularExpression::CaseInsensitiveOption);
    return prefix.match(query.toString().trimmed()).hasMatch();
}

bool isCountryCode(const QString &value)
{
    static const QRegularExpression country(QStringLiteral("^[A-Za-z]{2}$"));
    return country.match(value).hasMatch();
}

bool isServerName(const QString &value)
{
    static const QRegularExpression server(
        QStringLiteral("^[A-Za-z0-9-]+#[0-9]+$"));
    return server.match(value).hasMatch();
}

RunnerCommand connectionCommand(const QString &target)
{
    if (isCountryCode(target)) {
        return {RunnerAction::ConnectCountry, target.toUpper()};
    }
    return {RunnerAction::ConnectServer, target.toUpper()};
}
}

QList<RunnerCommand> parseRunnerQuery(QStringView query)
{
    if (!hasRunnerPrefix(query)) {
        return {};
    }

    const QString tail = commandTail(query.toString());
    if (tail.isEmpty()) {
        return {
            {RunnerAction::Open, {}},
            {RunnerAction::ConnectFastest, {}},
            {RunnerAction::Disconnect, {}},
        };
    }

    if (tail.compare(QStringLiteral("open"), Qt::CaseInsensitive) == 0
        || tail.compare(QStringLiteral("show"), Qt::CaseInsensitive) == 0) {
        return {{RunnerAction::Open, {}}};
    }
    if (tail.compare(QStringLiteral("fastest"), Qt::CaseInsensitive) == 0
        || tail.compare(QStringLiteral("connect"), Qt::CaseInsensitive) == 0
        || tail.compare(QStringLiteral("connect fastest"),
                        Qt::CaseInsensitive) == 0) {
        return {{RunnerAction::ConnectFastest, {}}};
    }
    if (tail.compare(QStringLiteral("disconnect"), Qt::CaseInsensitive) == 0) {
        return {{RunnerAction::Disconnect, {}}};
    }

    static const QRegularExpression targetCommand(
        QStringLiteral("^(?:(connect|country|server)\\s+)(\\S+)$"),
        QRegularExpression::CaseInsensitiveOption);
    const QRegularExpressionMatch match = targetCommand.match(tail);
    if (match.hasMatch()) {
        const QString verb = match.captured(1).toLower();
        const QString target = match.captured(2);
        if (verb == QStringLiteral("country") && isCountryCode(target)) {
            return {{RunnerAction::ConnectCountry, target.toUpper()}};
        }
        if (verb == QStringLiteral("server") && isServerName(target)) {
            return {{RunnerAction::ConnectServer, target.toUpper()}};
        }
        if (verb == QStringLiteral("connect")
            && (isCountryCode(target) || isServerName(target))) {
            return {connectionCommand(target)};
        }
        return {};
    }

    if (isCountryCode(tail) || isServerName(tail)) {
        return {connectionCommand(tail)};
    }
    return {};
}
