// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#include "VpnController.h"
#include "SnapshotContract.generated.h"

#include "BackendCallPolicy.h"
#include "CustomDnsModel.h"
#include "DbusContract.h"
#include "LocationModels.h"
#include "SplitTunnelingModel.h"
#include "VpnSettingsModel.h"

#include <QDBusPendingCallWatcher>
#include <QDBusPendingReply>
#include <QJsonDocument>
#include <QJsonObject>
#include <QTimer>
#include <algorithm>

void VpnController::onSnapshotChanged(const QString &snapshotJson)
{
    if (!backendSignalIsCurrent()) {
        return;
    }
    applySnapshot(snapshotJson);
}

void VpnController::onServerDataChanged(bool topologyChanged)
{
    if (!backendSignalIsCurrent()) {
        return;
    }
    const bool wasLocationsBusy = locationsBusy();
    if (topologyChanged) {
        m_countryRefreshPending = true;
        m_serverGroupRefreshPending = !m_currentServerCountry.isEmpty();
        m_serverRefreshPending = !m_currentServerCountry.isEmpty()
            && !m_currentServerGroupKind.isEmpty()
            && !m_currentServerGroupName.isEmpty();
        m_serverLoadsRefreshPending = false;
    } else if (!m_currentServerCountry.isEmpty()) {
        m_serverLoadsRefreshPending = true;
    }
    if (wasLocationsBusy != locationsBusy()) {
        emit locationsChanged();
    }
    if (topologyChanged && !m_locationSearchQuery.isEmpty()) {
        searchLocations(m_locationSearchQuery);
    }
    dispatchPendingLocationRefreshes();
}

void VpnController::onSettingsChanged(const QString &settingsJson)
{
    if (!backendSignalIsCurrent() || !m_loggedIn) {
        return;
    }
    QString errorMessage;
    if (!m_settings->applyJson(settingsJson, &errorMessage)) {
        m_settings->setMessage(errorMessage);
    }
}

void VpnController::onSplitTunnelingChanged(const QString &settingsJson)
{
    if (!backendSignalIsCurrent() || !m_loggedIn) {
        return;
    }
    QString errorMessage;
    if (!m_splitTunneling->applyJson(settingsJson, &errorMessage)) {
        m_splitTunneling->setMessage(errorMessage);
    }
}

void VpnController::onCustomDnsChanged(const QString &settingsJson)
{
    if (!backendSignalIsCurrent() || !m_loggedIn) {
        return;
    }
    QString errorMessage;
    if (!m_customDns->applyJson(settingsJson, &errorMessage)) {
        m_customDns->setMessage(errorMessage);
    }
}

void VpnController::applySnapshot(const QString &snapshotJson,
                                  quint64 reconciliationGeneration)
{
    QJsonParseError error;
    const QJsonDocument document = QJsonDocument::fromJson(
        snapshotJson.toUtf8(), &error);
    if (error.error != QJsonParseError::NoError || !document.isObject()) {
        m_message = tr("The backend returned an invalid state snapshot");
        m_snapshotError = m_message;
        m_snapshotRestartAllowed = true;
        emit snapshotChanged();
        return;
    }

    const QJsonObject snapshot = document.object();
    if (snapshot.value(QStringLiteral("schemaVersion")).toInt()
        != ProtonVpnKde::snapshotSchemaVersion) {
        m_message = tr(
            "The backend uses an unsupported interface version. Update or reinstall Plasma VPN.");
        m_snapshotError = m_message;
        m_snapshotRestartAllowed = false;
        emit snapshotChanged();
        return;
    }
    if (!ProtonVpnKde::validateSnapshotV1(snapshot)) {
        m_message = tr("The backend returned an incomplete state snapshot");
        m_snapshotError = m_message;
        m_snapshotRestartAllowed = true;
        emit snapshotChanged();
        return;
    }

    if (m_foregroundReconciliation
        && reconciliationGeneration == m_foregroundReconciliation->generation) {
        m_foregroundReconciliation->observedRead = true;
    }
    m_snapshotError.clear();
    m_snapshotRestartAllowed = false;

    const bool wasReady = m_ready;
    const bool wasLoggedIn = m_loggedIn;
    const bool locationsWereBusy = locationsBusy();
    const QString previousState = m_state;
    m_ready = snapshot.value(QStringLiteral("ready")).toBool();
    m_startupCompatible = snapshot.value(
        QStringLiteral("startupCompatible")).toBool(true);
    m_loggedIn = snapshot.value(QStringLiteral("loggedIn")).toBool();
    if (wasLoggedIn != m_loggedIn) {
        ++m_sessionGeneration;
        ++m_locationRequestGeneration;
        m_locationsBusy = false;
        m_packetCaptureError.clear();
        ++m_packetCaptureOperationGeneration;
        m_packetCaptureOperationPending = false;
        finishNpsSurveySubmission(
            m_npsSurveyOperationGeneration,
            false,
            tr("The Proton account session changed"),
            false);
    }
    m_authState = snapshot.value(QStringLiteral("authState")).toString(
        m_loggedIn ? QStringLiteral("signed_in") : QStringLiteral("signed_out"));
    m_accountName = snapshot.value(QStringLiteral("accountName")).toString();
    m_planTitle = snapshot.value(QStringLiteral("planTitle")).toString();
    m_userTier = snapshot.value(QStringLiteral("userTier")).toInt();
    m_maxConnections = snapshot.value(QStringLiteral("maxConnections")).toInt();
    m_fido2Available = snapshot.value(QStringLiteral("fido2Available")).toBool();
    m_killSwitch = std::clamp(
        snapshot.value(QStringLiteral("killSwitch")).toInt(), 0, 2);
    m_busy = snapshot.value(QStringLiteral("busy")).toBool();
    m_state = snapshot.value(QStringLiteral("state")).toString(
        QStringLiteral("unavailable"));
    m_errorCode = snapshot.value(QStringLiteral("errorCode")).toString();
    if (m_state != QStringLiteral("connected")) {
        m_customDns->setRestartRequired(false);
    }
    m_serverName = snapshot.value(QStringLiteral("serverName")).toString();
    m_serverLocation = snapshot.value(QStringLiteral("serverLocation")).toString();
    m_exitCountry = snapshot.value(QStringLiteral("exitCountry")).toString();
    m_entryCountry = snapshot.value(QStringLiteral("entryCountry")).toString();
    m_forwardedPort = std::clamp(
        snapshot.value(QStringLiteral("forwardedPort")).toInt(), 0, 65535);
    m_secureCore = snapshot.value(QStringLiteral("secureCore")).toBool();
    m_tor = snapshot.value(QStringLiteral("tor")).toBool();
    m_p2p = snapshot.value(QStringLiteral("p2p")).toBool();
    m_streaming = snapshot.value(QStringLiteral("streaming")).toBool();
    m_smartRouting = snapshot.value(QStringLiteral("smartRouting")).toBool();
    m_packetCaptureActive = snapshot.value(
        QStringLiteral("packetCaptureActive")).toBool();
    if (!m_packetCaptureOperationPending
        && m_packetCaptureExpectedActive.has_value()
        && m_packetCaptureActive == *m_packetCaptureExpectedActive) {
        const bool stopped = !*m_packetCaptureExpectedActive;
        m_packetCaptureExpectedActive.reset();
        // Inactive confirms the cleanup postcondition. Active includes Core's
        // reserved/unconfirmed capture obligation, not a Start acknowledgement.
        if (stopped) {
            m_packetCaptureError.clear();
        }
    }
    if (!m_packetCaptureOperationPending && !m_busy
        && !m_packetCaptureActive
        && m_packetCaptureExpectedActive.value_or(false)) {
        // An authoritative idle snapshot after a settled Start failure proves
        // that no capture cleanup remains, even though the requested positive
        // state was never reached.
        m_packetCaptureExpectedActive.reset();
    }
    if (!m_packetCaptureOperationPending && !m_busy
        && !m_packetCaptureActive
        && (!m_packetCaptureExpectedActive.has_value()
            || !*m_packetCaptureExpectedActive)) {
        m_packetCaptureStopRequested = false;
    }
    m_coreMemoryOptimized = snapshot.value(
        QStringLiteral("coreMemoryOptimized")).toBool();
    m_coreVersion = snapshot.value(QStringLiteral("coreVersion")).toString();
    m_message = snapshot.value(QStringLiteral("message")).toString();
    if (wasLoggedIn && !m_loggedIn) {
        const bool hadBrowserErrors = !m_countriesError.isEmpty()
            || !m_locationSearchError.isEmpty()
            || !m_serverGroupsError.isEmpty()
            || !m_serversError.isEmpty()
            || !m_serverLoadsError.isEmpty();
        m_countryModel->clear();
        m_serverGroupModel->clear();
        m_serverModel->clear();
        m_locationSearchModel->clear();
        m_countryRefreshPending = false;
        m_serverGroupRefreshPending = false;
        m_serverRefreshPending = false;
        m_serverLoadsRefreshPending = false;
        ++m_serverRequestGeneration;
        m_currentServerCountry.clear();
        m_currentServerGroupKind.clear();
        m_currentServerGroupName.clear();
        m_locationSearchQuery.clear();
        ++m_locationSearchGeneration;
        m_locationSearchBusy = false;
        m_locationSearchRequestPending = false;
        m_countriesError.clear();
        m_locationSearchError.clear();
        m_serverGroupsError.clear();
        m_serversError.clear();
        m_serverLoadsError.clear();
        m_npsSurveyChecked = false;
        m_npsSurveyAvailable = false;
        emit npsSurveyChanged();
        m_settings->reset();
        m_settingsRequest.invalidate();
        m_splitTunnelingRequest.invalidate();
        m_customDnsRequest.invalidate();
        m_splitTunneling->reset();
        m_customDns->reset();
        if (locationsWereBusy != locationsBusy() || hadBrowserErrors) {
            emit locationsChanged();
        }
    }
    if (m_foregroundReconciliation && m_foregroundReconciliation->observedRead
        && !m_busy) {
        const auto completed = *m_foregroundReconciliation;
        m_foregroundReconciliation.reset();
        if (completed.generation == m_foregroundOperationGeneration
            && completed.connectionGeneration == m_connectionOperationGeneration
            && !completed.connectionTarget.isEmpty()) {
            // Idle retires our wait; it cannot recover a missing method reply.
            // In particular, Connected may still be the pre-switch tunnel.
            emit connectionOperationFinished(
                completed.connectionGeneration, completed.connectionTarget,
                false, tr("The request result could not be confirmed. Review the current connection before trying again."));
        }
    }
    if (m_foregroundReconciliation && m_message.isEmpty()) {
        m_message = tr("The VPN operation is still completing; refreshing its state");
    }
    emit snapshotChanged();
    if (m_loggedIn && !m_npsSurveyChecked) {
        loadPendingNpsSurvey();
    }
    if (m_loggedIn && !m_busy) {
        // Retrying a failed reconciliation is read-only. No settings write is
        // replayed, and the local write gate remains closed until it succeeds.
        if (m_settingsRequest.needsRead()) {
            loadSettings();
        }
        if (m_splitTunnelingRequest.needsRead()) {
            loadSplitTunneling();
        }
        if (m_customDnsRequest.needsRead()) {
            loadCustomDns();
        }
    }
    if (m_loggedIn
        && (!m_settings->loaded() || previousState != m_state)
        && !m_settings->busy()) {
        loadSettings();
    }
    if (m_ready && m_loggedIn && (!wasReady || !wasLoggedIn)) {
        if (!m_locationSearchQuery.isEmpty()) {
            searchLocations(m_locationSearchQuery);
        }
        dispatchPendingLocationRefreshes();
    }
    dispatchPendingPacketCaptureStop();
    completeShutdownIfSafe();
}

void VpnController::handleSnapshotReply(QDBusPendingCallWatcher *watcher,
                                        quint64 reconciliationGeneration)
{
    const bool current = backendReplyIsCurrent(watcher);
    const QDBusPendingReply<QString> reply = *watcher;
    watcher->deleteLater();
    if (!current) {
        return;
    }
    m_snapshotRefreshPending = false;
    if (reply.isError()) {
        const auto errorType = reply.error().type();
        const bool transientSameOwnerFailure =
            ProtonVpnKde::isTransientSameOwnerFailure(errorType);
        if (!transientSameOwnerFailure
            && ProtonVpnKde::classifyBackendCallFailure(
                   errorType, reply.error().name())
                == ProtonVpnKde::BackendCallFailure::Unavailable) {
            setBackendAvailable(false);
        }
        m_message = tr("Unable to read backend state");
        m_snapshotError = m_message;
        emit snapshotChanged();
        if (transientSameOwnerFailure) {
            scheduleSnapshotRefreshRetry();
        }
        return;
    }
    m_snapshotRefreshRetryTimer->stop();
    m_snapshotRefreshRetryCount = 0;
    setBackendAvailable(true);
    applySnapshot(reply.value(), reconciliationGeneration);
    if (m_foregroundReconciliation && !m_foregroundReconciliation->observedRead
        && snapshotHealthy()) {
        // A read sent before the timeout is not a reconciliation receipt.
        refresh();
    }
}

void VpnController::handleOperationReply(QDBusPendingCallWatcher *watcher)
{
    const bool current = backendReplyIsCurrent(watcher);
    const QString connectionTarget =
        watcher->property("connectionTargetState").toString();
    const quint64 connectionGeneration =
        watcher->property("connectionOperationGeneration").toULongLong();
    const quint64 foregroundGeneration =
        watcher->property("foregroundOperationGeneration").toULongLong();
    const QVariant packetCaptureTarget =
        watcher->property("packetCaptureTargetActive");
    const quint64 packetCaptureGeneration =
        watcher->property("packetCaptureOperationGeneration").toULongLong();
    const QDBusPendingReply<> reply = *watcher;
    const bool restartAfterRetirement =
        watcher->property("restartAfterAccountRetirement").toBool();
    watcher->deleteLater();
    if (!current) {
        return;
    }
    const bool foregroundCurrent = foregroundGeneration == 0
        || foregroundGeneration == m_foregroundOperationGeneration;
    const bool connectionCurrent = connectionTarget.isEmpty()
        || connectionGeneration == m_connectionOperationGeneration;
    const bool captureCurrent = !packetCaptureTarget.isValid()
        || packetCaptureGeneration == m_packetCaptureOperationGeneration;
    if (packetCaptureTarget.isValid() && !captureCurrent) {
        refresh();
        return;
    }
    if (!connectionTarget.isEmpty() && !connectionCurrent) {
        return;
    }
    if (!packetCaptureTarget.isValid() && connectionTarget.isEmpty()
        && !foregroundCurrent) {
        return;
    }
    const bool globalCurrent = foregroundCurrent && connectionCurrent
        && captureCurrent;
    if (packetCaptureTarget.isValid() && captureCurrent) {
        m_packetCaptureOperationPending = false;
    }
    if (reply.isError()) {
        const bool transientSameOwnerFailure =
            ProtonVpnKde::isTransientSameOwnerFailure(reply.error().type());
        QString operationMessage;
        if (transientSameOwnerFailure) {
            operationMessage = tr(
                "The VPN operation is still completing; refreshing its state");
        } else {
            const auto failure = ProtonVpnKde::classifyBackendCallFailure(
                reply.error().type(), reply.error().name());
            if (failure == ProtonVpnKde::BackendCallFailure::Unavailable) {
                operationMessage = tr("The Proton backend service stopped");
                if (globalCurrent) {
                    setBackendAvailable(false);
                }
            } else if (failure
                       == ProtonVpnKde::BackendCallFailure::InvalidSecretPayload) {
                operationMessage = tr(
                    "Protected authentication data was rejected; try again");
            } else if (ProtonVpnKde::isSafeBackendAuthoredMessage(
                           reply.error().name(), reply.error().message())) {
                operationMessage = reply.error().message();
            } else {
                operationMessage = tr(
                    "The VPN operation could not be completed");
            }
        }
        if (globalCurrent) {
            if (transientSameOwnerFailure) {
                m_foregroundReconciliation = ForegroundReconciliation{
                    foregroundGeneration, connectionGeneration, connectionTarget};
            } else {
                m_busy = false;
            }
            m_message = operationMessage;
        }
        if (packetCaptureTarget.isValid() && captureCurrent) {
            m_packetCaptureError = operationMessage;
        }
        if (globalCurrent || (packetCaptureTarget.isValid() && captureCurrent)) {
            emit snapshotChanged();
        }
        if (!connectionTarget.isEmpty() && connectionCurrent
            && foregroundCurrent && !transientSameOwnerFailure) {
            emit connectionOperationFinished(
                connectionGeneration, connectionTarget, false,
                operationMessage);
        }
        if (transientSameOwnerFailure) {
            scheduleSnapshotRefreshRetry();
        }
        if (packetCaptureTarget.isValid() && captureCurrent) {
            refresh();
            if (packetCaptureTarget.toBool()
                && m_packetCaptureStopRequested) {
                dispatchPendingPacketCaptureStop(true);
            }
        }
        if (!packetCaptureTarget.isValid()
            || packetCaptureTarget.toBool()) {
            dispatchPendingPacketCaptureStop();
        }
        return;
    }
    if (!connectionTarget.isEmpty() && connectionCurrent
        && foregroundCurrent) {
        emit connectionOperationFinished(
            connectionGeneration, connectionTarget, true, {});
    }
    if (packetCaptureTarget.isValid() && captureCurrent) {
        if (globalCurrent) {
            m_busy = false;
        }
        if (packetCaptureTarget.toBool() && m_packetCaptureStopRequested) {
            dispatchPendingPacketCaptureStop(true);
        } else if (!packetCaptureTarget.toBool()) {
            m_packetCaptureActive = false;
            m_packetCaptureExpectedActive.reset();
            m_packetCaptureError.clear();
            m_packetCaptureStopRequested = false;
            emit snapshotChanged();
            if (m_shutdownPending) {
                completeShutdownIfSafe();
            }
        }
    }
    if (restartAfterRetirement && globalCurrent) {
        m_busy = false;
        restartBackendService();
        return;
    }
    refresh();
}

void VpnController::handleControlOperationReply(QDBusPendingCallWatcher *watcher)
{
    const quint64 npsGeneration =
        watcher->property("npsSubmissionGeneration").toULongLong();
    const bool npsSubmission = npsGeneration != 0;
    const bool npsRetryAllowed =
        watcher->property("npsRetryAllowed").toBool();
    const bool current = sessionReplyIsCurrent(watcher);
    const bool foregroundOwnershipRequired =
        watcher->property("foregroundOwnershipRequired").toBool();
    const quint64 foregroundGeneration =
        watcher->property("foregroundOperationGeneration").toULongLong();
    const bool foregroundCurrent = !foregroundOwnershipRequired
        || foregroundGeneration == m_foregroundOperationGeneration;
    const QString connectionTarget =
        watcher->property("connectionTargetState").toString();
    const quint64 connectionGeneration =
        watcher->property("connectionOperationGeneration").toULongLong();
    const QDBusPendingReply<> reply = *watcher;
    watcher->deleteLater();
    if (!current || !foregroundCurrent) {
        if (npsSubmission) {
            finishNpsSurveySubmission(
                npsGeneration,
                false,
                tr("The Proton account session changed"),
                false);
        }
        return;
    }
    if (npsSubmission
        && npsGeneration != m_npsSurveyOperationGeneration) {
        return;
    }
    if (!connectionTarget.isEmpty()
        && connectionGeneration != m_connectionOperationGeneration) {
        return;
    }
    if (reply.isError()) {
        const bool transientSameOwnerFailure =
            ProtonVpnKde::isTransientSameOwnerFailure(reply.error().type());
        const bool npsCompletionUnknown = npsSubmission
            && reply.error().name()
                == QString::fromLatin1(
                    ProtonVpnKde::DBusContract::Backend::Error::
                        npsCompletionUnknown);
        if (npsSubmission
            && (transientSameOwnerFailure || npsCompletionUnknown)) {
            const QString operationMessage = tr(
                "Survey submission completion is unknown; it will not be "
                "retried automatically");
            if (transientSameOwnerFailure) {
                scheduleSnapshotRefreshRetry();
            }
            finishNpsSurveySubmission(
                npsGeneration, false, operationMessage, false);
            return;
        }
        const auto failure = ProtonVpnKde::classifyBackendCallFailure(
            reply.error().type(), reply.error().name());
        QString operationMessage;
        if (failure == ProtonVpnKde::BackendCallFailure::CompletionUnknown) {
            operationMessage = tr(
                "The VPN operation may still be completing; refreshing its state");
            scheduleSnapshotRefreshRetry();
            if (!connectionTarget.isEmpty()) {
                m_foregroundReconciliation = ForegroundReconciliation{
                    foregroundGeneration, connectionGeneration, connectionTarget};
            }
        } else if (failure == ProtonVpnKde::BackendCallFailure::Unavailable) {
            setBackendAvailable(false);
            operationMessage = tr("The Proton backend service stopped");
        } else if (failure
                   == ProtonVpnKde::BackendCallFailure::InvalidSecretPayload) {
            operationMessage =
                tr("Protected authentication data was rejected; try again");
        } else if (ProtonVpnKde::isSafeBackendAuthoredMessage(
                       reply.error().name(), reply.error().message())) {
            operationMessage = reply.error().message();
        } else {
            operationMessage =
                tr("The VPN operation could not be completed");
        }
        if (npsSubmission) {
            finishNpsSurveySubmission(
                npsGeneration, false, operationMessage, npsRetryAllowed);
            return;
        }
        if (!connectionTarget.isEmpty()
            && failure != ProtonVpnKde::BackendCallFailure::CompletionUnknown) {
            m_busy = false;
        }
        m_message = operationMessage;
        emit snapshotChanged();
        if (!connectionTarget.isEmpty()
            && failure != ProtonVpnKde::BackendCallFailure::CompletionUnknown) {
            emit connectionOperationFinished(
                connectionGeneration, connectionTarget, false, m_message);
        }
        return;
    }
    if (!connectionTarget.isEmpty()) {
        emit connectionOperationFinished(
            connectionGeneration, connectionTarget, true, {});
    }
    if (npsSubmission) {
        finishNpsSurveySubmission(npsGeneration, true, {});
    }
    refresh();
}
