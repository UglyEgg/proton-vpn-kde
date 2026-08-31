// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#include "VpnController.h"

#include "BackendCallPolicy.h"
#include "CustomDnsModel.h"
#include "LocationModels.h"
#include "SplitTunnelingModel.h"
#include "VpnSettingsModel.h"

#include <QDBusPendingCallWatcher>
#include <QDBusPendingReply>
#include <QJsonDocument>
#include <QJsonObject>
#include <algorithm>

void VpnController::onSnapshotChanged(const QString &snapshotJson)
{
    applySnapshot(snapshotJson);
}

void VpnController::onServerDataChanged(bool topologyChanged)
{
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
    QString errorMessage;
    if (!m_settings->applyJson(settingsJson, &errorMessage)) {
        m_settings->setBusy(false);
        m_settings->setMessage(errorMessage);
    }
}

void VpnController::onSplitTunnelingChanged(const QString &settingsJson)
{
    QString errorMessage;
    if (!m_splitTunneling->applyJson(settingsJson, &errorMessage)) {
        m_splitTunneling->setBusy(false);
        m_splitTunneling->setMessage(errorMessage);
    }
}

void VpnController::onCustomDnsChanged(const QString &settingsJson)
{
    QString errorMessage;
    if (!m_customDns->applyJson(settingsJson, &errorMessage)) {
        m_customDns->setBusy(false);
        m_customDns->setMessage(errorMessage);
    }
}

void VpnController::applySnapshot(const QString &snapshotJson)
{
    QJsonParseError error;
    const QJsonDocument document = QJsonDocument::fromJson(
        snapshotJson.toUtf8(), &error);
    if (error.error != QJsonParseError::NoError || !document.isObject()) {
        m_message = tr("The backend returned an invalid state snapshot");
        emit snapshotChanged();
        return;
    }

    const QJsonObject snapshot = document.object();
    if (snapshot.value(QStringLiteral("schemaVersion")).toInt() != 1) {
        m_message = tr("The backend uses an unsupported interface version");
        emit snapshotChanged();
        return;
    }

    const bool wasReady = m_ready;
    const bool wasLoggedIn = m_loggedIn;
    const QString previousState = m_state;
    m_ready = snapshot.value(QStringLiteral("ready")).toBool();
    m_startupCompatible = snapshot.value(
        QStringLiteral("startupCompatible")).toBool(true);
    m_loggedIn = snapshot.value(QStringLiteral("loggedIn")).toBool();
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
    m_coreMemoryOptimized = snapshot.value(
        QStringLiteral("coreMemoryOptimized")).toBool();
    m_coreVersion = snapshot.value(QStringLiteral("coreVersion")).toString();
    m_message = snapshot.value(QStringLiteral("message")).toString();
    if (wasLoggedIn && !m_loggedIn) {
        const bool wasLocationsBusy = locationsBusy();
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
        m_npsSurveyChecked = false;
        m_npsSurveyAvailable = false;
        emit npsSurveyChanged();
        m_settings->reset();
        m_splitTunneling->reset();
        m_customDns->reset();
        if (wasLocationsBusy != locationsBusy()) {
            emit locationsChanged();
        }
    }
    emit snapshotChanged();
    if (m_loggedIn && !m_npsSurveyChecked) {
        loadPendingNpsSurvey();
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
}

void VpnController::handleSnapshotReply(QDBusPendingCallWatcher *watcher)
{
    const QDBusPendingReply<QString> reply = *watcher;
    watcher->deleteLater();
    if (reply.isError()) {
        setBackendAvailable(false);
        m_message = tr("Unable to read backend state");
        emit snapshotChanged();
        return;
    }
    setBackendAvailable(true);
    applySnapshot(reply.value());
}

void VpnController::handleOperationReply(QDBusPendingCallWatcher *watcher)
{
    const QDBusPendingReply<> reply = *watcher;
    watcher->deleteLater();
    if (reply.isError()) {
        m_busy = false;
        const auto failure = ProtonVpnKde::classifyBackendCallFailure(
            reply.error().type(), reply.error().name());
        if (failure == ProtonVpnKde::BackendCallFailure::Unavailable) {
            setBackendAvailable(false);
            m_message = tr("The Proton backend service stopped");
        } else if (failure
                   == ProtonVpnKde::BackendCallFailure::InvalidSecretPayload) {
            m_message = tr("Protected authentication data was rejected; try again");
        } else {
            m_message = tr("The VPN operation could not be completed");
        }
        emit snapshotChanged();
        return;
    }
    refresh();
}

void VpnController::handleControlOperationReply(QDBusPendingCallWatcher *watcher)
{
    const QDBusPendingReply<> reply = *watcher;
    watcher->deleteLater();
    if (reply.isError()) {
        const auto failure = ProtonVpnKde::classifyBackendCallFailure(
            reply.error().type(), reply.error().name());
        if (failure == ProtonVpnKde::BackendCallFailure::Unavailable) {
            setBackendAvailable(false);
            m_message = tr("The Proton backend service stopped");
        } else if (failure
                   == ProtonVpnKde::BackendCallFailure::InvalidSecretPayload) {
            m_message = tr("Protected authentication data was rejected; try again");
        } else {
            m_message = tr("The VPN operation could not be completed");
        }
        emit snapshotChanged();
        return;
    }
    refresh();
}
