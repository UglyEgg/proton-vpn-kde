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
#include <QDBusConnectionInterface>
#include <QDBusMessage>
#include <QDBusPendingCallWatcher>
#include <QDBusPendingReply>
#include <QTimer>
#include <QVariant>
#include <algorithm>

namespace
{
namespace BackendDbus = ProtonVpnKde::DBusContract::Backend;
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
    const auto identity = ProtonVpnKde::verifyBackendIdentity(
        QDBusConnection::sessionBus(), QString::fromLatin1(BackendDbus::serviceName));
    if (!identity.trusted) {
        disconnectBackendSignals();
        m_backendDestination.clear();
        ++m_backendGeneration;
        setBackendAvailable(false);
        m_state = QStringLiteral("unavailable");
        m_message = tr("The VPN backend could not be authenticated");
        emit snapshotChanged();
        return;
    }
    disconnectBackendSignals();
    m_backendDestination = identity.uniqueOwner;
    ++m_backendGeneration;
    connectBackendSignals();
    setBackendAvailable(false);
    m_clientRegistration.serviceChanged();
    m_clientRegistrationRetryTimer->stop();
    registerClient();
}

void VpnController::onServiceUnregistered(const QString &)
{
    disconnectBackendSignals();
    m_backendDestination.clear();
    ++m_backendGeneration;
    m_clientRegistration.serviceChanged();
    setBackendAvailable(false);
    m_ready = false;
    m_busy = false;
    const bool wasLocationsBusy = locationsBusy();
    m_locationsBusy = false;
    m_state = QStringLiteral("unavailable");
    m_errorCode.clear();
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
    m_npsSurveyChecked = false;
    m_npsSurveyAvailable = false;
    emit npsSurveyChanged();
    m_settings->reset(tr("The Proton backend service stopped"));
    m_splitTunneling->reset(tr("The Proton backend service stopped"));
    m_customDns->reset(tr("The Proton backend service stopped"));
    if (wasLocationsBusy != locationsBusy()) {
        emit locationsChanged();
    }
    emit snapshotChanged();
    scheduleClientRegistrationRetry();
}

void VpnController::registerClient()
{
    if (m_clientIdentityRejected) {
        return;
    }
    if (m_backendDestination.isEmpty()) {
        auto *interface = QDBusConnection::sessionBus().interface();
        if (!interface
            || !interface->startService(
                    QString::fromLatin1(BackendDbus::serviceName)).isValid()) {
            scheduleClientRegistrationRetry();
        }
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
    const QDBusPendingReply<> reply = *watcher;
    const auto generation = watcher->property("registrationGeneration").toULongLong();
    watcher->deleteLater();
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
