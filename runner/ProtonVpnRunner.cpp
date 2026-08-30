// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#include "ProtonVpnRunner.h"

#include "DbusContract.h"
#include "RunnerCommand.h"
#include "TranslationLoader.h"

#include <KPluginFactory>
#include <QCoreApplication>
#include <QDBusConnection>
#include <QDBusMessage>
#include <QVariantMap>

namespace
{
namespace ControlCenterDbus = ProtonVpnKde::DBusContract::ControlCenter;

QString actionId(RunnerAction action)
{
    switch (action) {
    case RunnerAction::Open:
        return QStringLiteral("open");
    case RunnerAction::ConnectFastest:
        return QStringLiteral("fastest");
    case RunnerAction::Disconnect:
        return QStringLiteral("disconnect");
    case RunnerAction::ConnectCountry:
        return QStringLiteral("country");
    case RunnerAction::ConnectServer:
        return QStringLiteral("server");
    }
    return {};
}

RunnerAction actionFromId(const QString &id)
{
    if (id == QStringLiteral("fastest")) {
        return RunnerAction::ConnectFastest;
    }
    if (id == QStringLiteral("disconnect")) {
        return RunnerAction::Disconnect;
    }
    if (id == QStringLiteral("country")) {
        return RunnerAction::ConnectCountry;
    }
    if (id == QStringLiteral("server")) {
        return RunnerAction::ConnectServer;
    }
    return RunnerAction::Open;
}

void requestControlCenterAction(RunnerAction action, const QString &argument)
{
    const bool open = action == RunnerAction::Open;
    QDBusMessage request = QDBusMessage::createMethodCall(
        QString::fromLatin1(ControlCenterDbus::serviceName),
        QString::fromLatin1(ControlCenterDbus::objectPath),
        QString::fromLatin1(ControlCenterDbus::interfaceName),
        open
            ? QString::fromLatin1(
                  ControlCenterDbus::Method::showControlCenter)
            : QString::fromLatin1(
                  ControlCenterDbus::Method::requestRunnerAction));
    if (!open) {
        request << actionId(action) << argument;
    }
    (void)QDBusConnection::sessionBus().send(request);
}
}

ProtonVpnRunner::ProtonVpnRunner(QObject *parent,
                                 const KPluginMetaData &metadata)
    : KRunner::AbstractRunner(parent, metadata)
{
    TranslationLoader::installSystemLocale(*QCoreApplication::instance());
    setTriggerWords({QStringLiteral("vpn"), QStringLiteral("proton vpn")});
    addSyntax(QStringLiteral("vpn"), tr("Open or control Proton VPN"));
    addSyntax(QStringLiteral("vpn connect"),
              tr("Connect to the fastest Proton VPN server"));
    addSyntax(QStringLiteral("vpn connect :q:"),
              tr("Connect using a country code or exact server name"));
    addSyntax(QStringLiteral("vpn disconnect"), tr("Disconnect Proton VPN"));
}

void ProtonVpnRunner::match(KRunner::RunnerContext &context)
{
    const QList<RunnerCommand> commands = parseRunnerQuery(context.query());
    for (const RunnerCommand &command : commands) {
        addMatch(context, static_cast<int>(command.action), command.argument);
    }
}

void ProtonVpnRunner::addMatch(KRunner::RunnerContext &context, int rawAction,
                               const QString &argument)
{
    const auto action = static_cast<RunnerAction>(rawAction);
    KRunner::QueryMatch result(this);
    QVariantMap payload;
    payload.insert(QStringLiteral("action"), actionId(action));
    payload.insert(QStringLiteral("argument"), argument);
    result.setData(payload);
    result.setId(actionId(action) + QLatin1Char(':') + argument);
    result.setCategoryRelevance(KRunner::QueryMatch::CategoryRelevance::High);

    switch (action) {
    case RunnerAction::Open:
        result.setText(tr("Open Plasma VPN"));
        result.setSubtext(tr("Show the Proton VPN-compatible community client"));
        result.setIconName(QStringLiteral("plasma-vpn"));
        result.setRelevance(0.95);
        break;
    case RunnerAction::ConnectFastest:
        result.setText(tr("Connect Proton VPN"));
        result.setSubtext(tr("Use the saved fastest-server capability filters"));
        result.setIconName(QStringLiteral("network-connect"));
        result.setRelevance(0.9);
        break;
    case RunnerAction::Disconnect:
        result.setText(tr("Disconnect Proton VPN"));
        result.setSubtext(tr("End the current VPN connection"));
        result.setIconName(QStringLiteral("network-disconnect"));
        result.setRelevance(0.85);
        break;
    case RunnerAction::ConnectCountry:
        result.setText(tr("Connect Proton VPN to %1").arg(argument));
        result.setSubtext(tr("Use the fastest server in this country"));
        result.setIconName(QStringLiteral("network-connect"));
        break;
    case RunnerAction::ConnectServer:
        result.setText(tr("Connect Proton VPN to %1").arg(argument));
        result.setSubtext(tr("Use this exact server"));
        result.setIconName(QStringLiteral("network-connect"));
        break;
    }
    context.addMatch(result);
}

void ProtonVpnRunner::run(const KRunner::RunnerContext &context,
                          const KRunner::QueryMatch &match)
{
    Q_UNUSED(context)
    const QVariantMap payload = match.data().toMap();
    const RunnerAction action = actionFromId(
        payload.value(QStringLiteral("action")).toString());
    const QString argument = payload.value(QStringLiteral("argument")).toString();

    switch (action) {
    case RunnerAction::Open:
    case RunnerAction::ConnectFastest:
    case RunnerAction::Disconnect:
    case RunnerAction::ConnectCountry:
    case RunnerAction::ConnectServer:
        requestControlCenterAction(action, argument);
        break;
    }
}

K_PLUGIN_CLASS_WITH_JSON(ProtonVpnRunner, "proton-vpn-kde-runner.json")

#include "ProtonVpnRunner.moc"
