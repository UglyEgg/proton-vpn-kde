#include "ProtonVpnRunner.h"

#include "RunnerCommand.h"
#include "TranslationLoader.h"

#include <KPluginFactory>
#include <QCoreApplication>
#include <QDBusConnection>
#include <QDBusMessage>
#include <QProcess>
#include <QVariantMap>

namespace
{
constexpr auto serviceName = "proton.vpn.app.kde.backend";
constexpr auto objectPath = "/proton/vpn/app/kde/backend";
constexpr auto interfaceName = "proton.vpn.app.kde.Backend1";

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

void callBackend(const QString &method, const QString &argument = {})
{
    QDBusMessage message = QDBusMessage::createMethodCall(
        QString::fromLatin1(serviceName), QString::fromLatin1(objectPath),
        QString::fromLatin1(interfaceName), method);
    if (!argument.isEmpty()) {
        message << argument;
    }
    QDBusConnection::sessionBus().send(message);
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
        result.setText(tr("Open Proton VPN"));
        result.setSubtext(tr("Show the native Plasma client"));
        result.setIconName(QStringLiteral("proton-vpn-kde"));
        result.setRelevance(0.95);
        break;
    case RunnerAction::ConnectFastest:
        result.setText(tr("Connect Proton VPN"));
        result.setSubtext(tr("Use the fastest available server"));
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
        QProcess::startDetached(QStringLiteral("proton-vpn-kde"), {});
        break;
    case RunnerAction::ConnectFastest:
        callBackend(QStringLiteral("ConnectFastest"));
        break;
    case RunnerAction::Disconnect:
        callBackend(QStringLiteral("Disconnect"));
        break;
    case RunnerAction::ConnectCountry:
        callBackend(QStringLiteral("ConnectCountry"), argument);
        break;
    case RunnerAction::ConnectServer:
        callBackend(QStringLiteral("ConnectServer"), argument);
        break;
    }
}

K_PLUGIN_CLASS_WITH_JSON(ProtonVpnRunner, "proton-vpn-kde-runner.json")

#include "ProtonVpnRunner.moc"
