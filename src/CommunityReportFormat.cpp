// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#include "CommunityReportFormat.h"

#include <QRegularExpression>
#include <QSet>
#include <QStringList>

namespace
{
QString safeVersion(const QString &value)
{
    static const QRegularExpression pattern(
        QStringLiteral("\\A[0-9][A-Za-z0-9.+_-]{0,31}\\z"));
    return pattern.match(value).hasMatch() ? value : QStringLiteral("not reported");
}

QString safeOsFamily(const QString &value)
{
    static const QRegularExpression pattern(
        QStringLiteral("\\A[a-z][a-z0-9_-]{0,31}\\z"));
    return pattern.match(value).hasMatch() ? value : QStringLiteral("not reported");
}

QString safeState(const QString &value, const QSet<QString> &allowed)
{
    return allowed.contains(value) ? value : QStringLiteral("unknown");
}
}

QString formatCommunityReport(const CommunityReportFacts &facts)
{
    static const QSet<QString> secretStates = {
        QStringLiteral("running"), QStringLiteral("activatable"),
        QStringLiteral("missing"), QStringLiteral("checking"),
        QStringLiteral("unknown")};
    static const QSet<QString> vpnStates = {
        QStringLiteral("connected"), QStringLiteral("connecting"),
        QStringLiteral("disconnecting"), QStringLiteral("disconnected"),
        QStringLiteral("error"), QStringLiteral("starting"),
        QStringLiteral("unavailable")};
    static const QSet<QString> errorCodes = {
        QStringLiteral("tunnel_setup_failed"),
        QStringLiteral("authentication_denied"),
        QStringLiteral("timeout"),
        QStringLiteral("device_disconnected"),
        QStringLiteral("maximum_sessions_reached"),
        QStringLiteral("certificate_expired"),
        QStringLiteral("certificate_not_yet_valid"),
        QStringLiteral("two_factor_required"),
        QStringLiteral("unexpected_error"),
        QStringLiteral("connector_initialization_failed")};
    const QString backendState = !facts.backendAvailable
        ? QStringLiteral("unavailable")
        : !facts.snapshotHealthy ? QStringLiteral("needs attention")
        : facts.backendReady ? QStringLiteral("ready")
                             : QStringLiteral("starting");
    const QString coreCheck = facts.backendReady
        ? (facts.startupCompatible ? QStringLiteral("compatible")
                                   : QStringLiteral("needs attention"))
        : QStringLiteral("not checked");
    const QString memoryOverlay = facts.backendReady
        ? (facts.coreMemoryOptimized ? QStringLiteral("detected")
                                     : QStringLiteral("not detected"))
        : QStringLiteral("not checked");
    const QString errorCode = facts.errorCode.isEmpty()
        ? QStringLiteral("none")
        : safeState(facts.errorCode, errorCodes);
    const QString telemetry = !facts.telemetryBuildEnabled
        ? QStringLiteral("disabled by build policy")
        : !facts.telemetryRuntimeAvailable
        ? QStringLiteral("unavailable with installed Proton Core")
        : !facts.telemetryPreferenceKnown ? QStringLiteral("not checked")
        : facts.telemetryEnabled ? QStringLiteral("enabled by user")
                                 : QStringLiteral("disabled");

    return QStringList{
        QStringLiteral("Plasma VPN community diagnostics"),
        QStringLiteral("Client version: %1").arg(safeVersion(facts.clientVersion)),
        QStringLiteral("OS family: %1").arg(safeOsFamily(facts.osFamily)),
        QStringLiteral("Qt version: %1").arg(safeVersion(facts.qtVersion)),
        QStringLiteral("Backend: %1").arg(backendState),
        QStringLiteral("Proton Core: %1").arg(safeVersion(facts.coreVersion)),
        QStringLiteral("Core startup check: %1").arg(coreCheck),
        QStringLiteral("Secret Service advertised: %1").arg(
            safeState(facts.secretServiceState, secretStates)),
        QStringLiteral("VPN state: %1").arg(safeState(facts.vpnState, vpnStates)),
        QStringLiteral("Error code: %1").arg(errorCode),
        QStringLiteral("Core memory overlay: %1").arg(memoryOverlay),
        QStringLiteral("Connection telemetry: %1").arg(telemetry),
    }.join(QLatin1Char('\n'));
}
