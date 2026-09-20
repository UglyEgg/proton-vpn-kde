// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#include "VpnController.h"

#include "BackendCallPolicy.h"
#include "BackendIdentity.h"
#include "CustomDnsModel.h"
#include "DbusContract.h"
#include "LocationModels.h"
#include "SplitTunnelingModel.h"
#include "VpnSettingsModel.h"

#include <QDBusConnection>
#include <QDBusMessage>
#include <QDBusPendingCallWatcher>
#include <QDBusPendingReply>
#include <QTimer>
#include <QVariant>
#include <algorithm>

namespace
{
namespace BackendDbus = ProtonVpnKde::DBusContract::Backend;
constexpr auto systemdService = "org.freedesktop.systemd1";
constexpr auto systemdPath = "/org/freedesktop/systemd1";
constexpr auto systemdManagerInterface = "org.freedesktop.systemd1.Manager";
constexpr auto backendUnit = "proton-vpn-kde-backend.service";
}

void VpnController::restartBackend()
{
    if (m_backendRestartPending) {
        return;
    }
    if (m_backendAvailable && ready() && m_authState == QStringLiteral("expired")) {
        if (busy()) {
            return;
        }
        // Explicit sign-in recovery retires the old tunnel/account first.
        // Credentials are neither retained nor replayed across this boundary.
        callOperation(QString::fromLatin1(BackendDbus::Method::logout));
        return;
    }
    const bool recoveryRequired =
        m_authState == QStringLiteral("authentication_unknown")
        || m_authState == QStringLiteral("settings_unavailable")
        || m_authState == QStringLiteral("protection_unknown")
        || m_authState == QStringLiteral("account_restart_required")
        || m_state == QStringLiteral("unresponsive");
    if (ready() && !recoveryRequired) {
        return;
    }
    restartBackendService();
}

void VpnController::restartBackendService()
{
    if (m_backendRestartPending) {
        return;
    }
    m_message = tr("Restarting the Proton backend service…");
    m_backendRestartPending = true;
    emit snapshotChanged();

    QDBusMessage message = QDBusMessage::createMethodCall(
        QString::fromLatin1(systemdService), QString::fromLatin1(systemdPath),
        QString::fromLatin1(systemdManagerInterface),
        QStringLiteral("RestartUnit"));
    message.setArguments({QString::fromLatin1(backendUnit),
                          QStringLiteral("replace")});
    auto *watcher = new QDBusPendingCallWatcher(
        QDBusConnection::sessionBus().asyncCall(message, 5000), this);
    const quint64 backendGeneration = m_backendGeneration;
    connect(watcher, &QDBusPendingCallWatcher::finished, this,
            [this, backendGeneration](QDBusPendingCallWatcher *finished) {
        const QDBusPendingReply<QDBusObjectPath> reply = *finished;
        finished->deleteLater();
        if (backendGeneration == m_backendGeneration) {
            m_backendRestartPending = false;
            if (reply.isError()) {
                m_message = tr("Unable to restart the Proton backend service");
                emit snapshotChanged();
            }
        }
    });
}

void VpnController::connectBackendSignals()
{
    if (m_backendDestination.isEmpty()) {
        return;
    }
    QDBusConnection bus = QDBusConnection::sessionBus();
    bus.connect(m_backendDestination, QString::fromLatin1(BackendDbus::objectPath),
                QString::fromLatin1(BackendDbus::interfaceName),
                QString::fromLatin1(BackendDbus::Signal::snapshotChanged), this,
                SLOT(onSnapshotChanged(QString)));
    bus.connect(m_backendDestination, QString::fromLatin1(BackendDbus::objectPath),
                QString::fromLatin1(BackendDbus::interfaceName),
                QString::fromLatin1(BackendDbus::Signal::serverDataChanged), this,
                SLOT(onServerDataChanged(bool)));
    bus.connect(m_backendDestination, QString::fromLatin1(BackendDbus::objectPath),
                QString::fromLatin1(BackendDbus::interfaceName),
                QString::fromLatin1(BackendDbus::Signal::settingsChanged), this,
                SLOT(onSettingsChanged(QString)));
    bus.connect(m_backendDestination, QString::fromLatin1(BackendDbus::objectPath),
                QString::fromLatin1(BackendDbus::interfaceName),
                QString::fromLatin1(BackendDbus::Signal::splitTunnelingChanged), this,
                SLOT(onSplitTunnelingChanged(QString)));
    bus.connect(m_backendDestination, QString::fromLatin1(BackendDbus::objectPath),
                QString::fromLatin1(BackendDbus::interfaceName),
                QString::fromLatin1(BackendDbus::Signal::customDnsChanged), this,
                SLOT(onCustomDnsChanged(QString)));
}

void VpnController::disconnectBackendSignals()
{
    if (m_backendDestination.isEmpty()) {
        return;
    }
    QDBusConnection bus = QDBusConnection::sessionBus();
    bus.disconnect(m_backendDestination, QString::fromLatin1(BackendDbus::objectPath),
                   QString::fromLatin1(BackendDbus::interfaceName), {}, this, {});
}

void VpnController::onServiceRegistered(const QString &)
{
    m_backendRestartPending = false;
    m_snapshotError.clear();
    m_snapshotRestartAllowed = false;
    m_packetCaptureError.clear();
    m_packetCaptureExpectedActive.reset();
    ++m_packetCaptureOperationGeneration;
    m_packetCaptureOperationPending = false;
    m_packetCaptureStopRequested = false;
    ++m_locationRequestGeneration;
    m_locationsBusy = false;
    disconnectBackendSignals();
    m_backendDestination.clear();
    ++m_backendGeneration;
    m_backendDiscoveryPending = false;
    m_backendIdentityPending = true;
    m_snapshotRefreshRetryTimer->stop();
    m_snapshotRefreshRetryCount = 0;
    setBackendAvailable(false);
    m_clientRegistration.serviceChanged();
    m_clientRegistrationRetryTimer->stop();
    const quint64 generation = m_backendGeneration;
    ProtonVpnKde::verifyBackendIdentity(
        QDBusConnection::sessionBus(), QString::fromLatin1(BackendDbus::serviceName), this,
        [this, generation](const ProtonVpnKde::BackendIdentityResult &identity) {
            if (generation != m_backendGeneration) {
                return;
            }
            m_backendIdentityPending = false;
            if (!identity.trusted) {
                m_state = QStringLiteral("unavailable");
                m_message = tr("The VPN backend could not be authenticated");
                emit snapshotChanged();
                return;
            }
            m_backendDestination = identity.uniqueOwner;
            connectBackendSignals();
            registerClient();
        });
}

void VpnController::onServiceUnregistered(const QString &)
{
    m_backendDiscoveryPending = false;
    m_backendIdentityPending = false;
    m_backendRestartPending = false;
    disconnectBackendSignals();
    m_backendDestination.clear();
    ++m_backendGeneration;
    m_clientRegistration.serviceChanged();
    m_snapshotRefreshRetryTimer->stop();
    m_snapshotRefreshRetryCount = 0;
    setBackendAvailable(false);
    m_ready = false;
    m_startupCompatible = true;
    if (m_loggedIn) {
        ++m_sessionGeneration;
    }
    m_loggedIn = false;
    ++m_locationRequestGeneration;
    m_snapshotRefreshPending = false;
    m_snapshotError.clear();
    m_snapshotRestartAllowed = false;
    m_authState = QStringLiteral("signed_out");
    m_accountName.clear();
    m_planTitle.clear();
    m_userTier = 0;
    m_maxConnections = 0;
    m_fido2Available = false;
    m_killSwitch = 0;
    m_busy = false;
    m_foregroundReconciliation.reset();
    const bool wasLocationsBusy = locationsBusy();
    const bool hadBrowserErrors = !m_countriesError.isEmpty()
        || !m_locationSearchError.isEmpty()
        || !m_serverGroupsError.isEmpty()
        || !m_serversError.isEmpty()
        || !m_serverLoadsError.isEmpty();
    m_locationsBusy = false;
    m_state = QStringLiteral("unavailable");
    m_errorCode.clear();
    m_serverName.clear();
    m_serverLocation.clear();
    m_exitCountry.clear();
    m_entryCountry.clear();
    m_forwardedPort = 0;
    m_vpnExitIpv4.clear();
    m_vpnExitIpv6.clear();
    m_deviceIpAtConnect.clear();
    m_secureCore = false;
    m_tor = false;
    m_p2p = false;
    m_streaming = false;
    m_smartRouting = false;
    m_packetCaptureActive = false;
    m_packetCaptureError.clear();
    m_packetCaptureExpectedActive.reset();
    ++m_packetCaptureOperationGeneration;
    m_packetCaptureOperationPending = false;
    m_packetCaptureStopRequested = false;
    m_coreMemoryOptimized = false;
    m_coreVersion.clear();
    if (!m_clientIdentityRejected) {
        m_message = tr("The Proton backend service stopped");
    }
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
    finishNpsSurveySubmission(
        m_npsSurveyOperationGeneration,
        false,
        tr("The Proton backend service stopped"),
        false);
    emit npsSurveyChanged();
    m_settings->reset(tr("The Proton backend service stopped"));
    m_settingsRequest.invalidate();
    m_splitTunnelingRequest.invalidate();
    m_customDnsRequest.invalidate();
    m_splitTunneling->reset(tr("The Proton backend service stopped"));
    m_customDns->reset(tr("The Proton backend service stopped"));
    if (wasLocationsBusy != locationsBusy() || hadBrowserErrors) {
        emit locationsChanged();
    }
    emit snapshotChanged();
    completeShutdownIfSafe();
    scheduleClientRegistrationRetry();
}

void VpnController::registerClient()
{
    if (m_clientIdentityRejected) {
        return;
    }
    if (m_backendDestination.isEmpty()) {
        if (m_backendDiscoveryPending || m_backendIdentityPending) {
            return;
        }
        m_backendDiscoveryPending = true;
        const quint64 generation = m_backendGeneration;
        ProtonVpnKde::discoverBackendService(QDBusConnection::sessionBus(),
            QString::fromLatin1(BackendDbus::serviceName), true, this,
            [this, generation](bool present) {
                if (generation != m_backendGeneration) {
                    return;
                }
                m_backendDiscoveryPending = false;
                if (present) {
                    onServiceRegistered({});
                } else {
                    scheduleClientRegistrationRetry();
                }
            });
        return;
    }
    const auto generation = m_clientRegistration.begin();
    if (!generation.has_value()) {
        return;
    }
    const QString uniqueName = QDBusConnection::sessionBus().baseService();
    if (uniqueName.isEmpty()) {
        static_cast<void>(m_clientRegistration.complete(*generation, false));
        scheduleClientRegistrationRetry();
        return;
    }
    QDBusMessage message = QDBusMessage::createMethodCall(
        m_backendDestination,
        QString::fromLatin1(BackendDbus::objectPath),
        QString::fromLatin1(BackendDbus::interfaceName),
        QString::fromLatin1(BackendDbus::Method::registerClient));
    message.setArguments({uniqueName});
    auto *watcher = new QDBusPendingCallWatcher(
        QDBusConnection::sessionBus().asyncCall(message, 5000), this);
    stampBackendRequest(watcher);
    watcher->setProperty("registrationGeneration",
                         QVariant::fromValue<qulonglong>(*generation));
    connect(watcher, &QDBusPendingCallWatcher::finished,
            this, &VpnController::handleRegisterClientReply);
}

void VpnController::unregisterClient()
{
    if (!m_clientRegistration.registered()) {
        m_clientRegistration.serviceChanged();
        return;
    }
    m_clientRegistration.serviceChanged();
    const QString uniqueName = QDBusConnection::sessionBus().baseService();
    if (uniqueName.isEmpty() || m_backendDestination.isEmpty()) {
        return;
    }
    QDBusMessage message = QDBusMessage::createMethodCall(
        m_backendDestination,
        QString::fromLatin1(BackendDbus::objectPath),
        QString::fromLatin1(BackendDbus::interfaceName),
        QString::fromLatin1(BackendDbus::Method::unregisterClient));
    message.setArguments({uniqueName});
    // The event loop has already stopped when this destructor runs. A direct
    // fire-and-forget send still queues the release before bus teardown.
    QDBusConnection::sessionBus().send(message);
}

void VpnController::setBackendAvailable(bool available)
{
    if (m_backendAvailable == available) {
        return;
    }
    m_backendAvailable = available;
    emit backendAvailableChanged();
    emit snapshotChanged();
}

void VpnController::handleRegisterClientReply(QDBusPendingCallWatcher *watcher)
{
    const bool currentBackend = backendReplyIsCurrent(watcher);
    const QDBusPendingReply<> reply = *watcher;
    const auto generation = watcher->property("registrationGeneration").toULongLong();
    watcher->deleteLater();
    if (!currentBackend) {
        return;
    }
    const auto completion = m_clientRegistration.complete(generation, !reply.isError());
    if (completion == ProtonVpnKde::ClientRegistrationState::Completion::Stale) {
        return;
    }
    if (completion == ProtonVpnKde::ClientRegistrationState::Completion::Failed) {
        if (ProtonVpnKde::classifyBackendCallFailure(
                reply.error().type(), reply.error().name())
            == ProtonVpnKde::BackendCallFailure::Unauthorized) {
            m_clientIdentityRejected = true;
            setBackendAvailable(false);
            m_ready = false;
            m_busy = false;
            m_state = QStringLiteral("unavailable");
            m_message = tr(
                "The Control Center could not be authenticated. Close and "
                "reopen it after an upgrade; reinstall the client if the "
                "problem continues.");
            emit snapshotChanged();
            return;
        }
        scheduleClientRegistrationRetry();
        return;
    }
    m_clientIdentityRejected = false;
    m_clientRegistrationRetryTimer->stop();
    m_clientRegistrationRetryCount = 0;
    setBackendAvailable(true);
    setReconnectionEnabled(m_reconnectionEnabled);
    refresh();
}

void VpnController::scheduleClientRegistrationRetry()
{
    if (m_clientIdentityRejected || m_clientRegistration.registered()
        || m_clientRegistration.inFlight()
        || m_clientRegistrationRetryTimer->isActive()) {
        return;
    }
    constexpr unsigned int maximumShift = 5;
    const auto shift = std::min(m_clientRegistrationRetryCount, maximumShift);
    const int delayMilliseconds = 1000 * (1 << shift);
    ++m_clientRegistrationRetryCount;
    m_clientRegistrationRetryTimer->start(delayMilliseconds);
}

void VpnController::scheduleSnapshotRefreshRetry()
{
    if (m_backendDestination.isEmpty()
        || m_snapshotRefreshRetryTimer->isActive()) {
        return;
    }
    constexpr unsigned int maximumRetries = 3;
    if (m_snapshotRefreshRetryCount >= maximumRetries) {
        m_snapshotRefreshPending = false;
        m_ready = false;
        m_busy = false;
        m_state = QStringLiteral("unresponsive");
        m_message = tr(
            "The Proton backend is not responding. Restart it before continuing.");
        emit snapshotChanged();
        return;
    }
    constexpr int retryBaseMilliseconds = 250;
    const int delayMilliseconds =
        retryBaseMilliseconds * (1 << m_snapshotRefreshRetryCount);
    ++m_snapshotRefreshRetryCount;
    m_snapshotRefreshRetryTimer->start(delayMilliseconds);
}
