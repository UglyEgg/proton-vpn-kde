// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#include "AgentVpnClient.h"
#include "SnapshotCompatibility.h"

#include "BackendCallPolicy.h"
#include "BackendIdentity.h"
#include "ConnectionAction.h"
#include "DbusContract.h"

#include <QDBusConnection>
#include <QDBusMessage>
#include <QDBusPendingCallWatcher>
#include <QDBusPendingReply>
#include <QDBusServiceWatcher>
#include <QJsonDocument>
#include <QJsonObject>
#include <QTimer>
#include <algorithm>

namespace
{
namespace BackendDbus = ProtonVpnKde::DBusContract::Backend;

QStringList normalizedServerFeatures(const QStringList &features)
{
    static const QStringList supported{
        QStringLiteral("p2p"),
        QStringLiteral("streaming"),
        QStringLiteral("tor"),
        QStringLiteral("secure-core"),
    };
    QStringList requested;
    for (const QString &feature : features) {
        const QString normalized = feature.trimmed().toLower();
        if (supported.contains(normalized) && !requested.contains(normalized)) {
            requested.append(normalized);
        }
    }
    QStringList result;
    for (const QString &feature : supported) {
        if (requested.contains(feature)) {
            result.append(feature);
        }
    }
    return result;
}

QString fixedCallFailureMessage(const QDBusError &error)
{
    using ProtonVpnKde::BackendCallFailure;
    switch (ProtonVpnKde::classifyBackendCallFailure(
        error.type(), error.name())) {
    case BackendCallFailure::Unavailable:
        return AgentVpnClient::tr("The Proton backend is not available");
    case BackendCallFailure::CompletionUnknown:
        return AgentVpnClient::tr("The backend request completion could not be confirmed");
    case BackendCallFailure::Unauthorized:
    case BackendCallFailure::InvalidSecretPayload:
    case BackendCallFailure::Rejected:
        return AgentVpnClient::tr("The Proton backend rejected the request");
    }
    return AgentVpnClient::tr("The Proton backend rejected the request");
}
}

AgentVpnClient::AgentVpnClient(QObject *parent)
    : VpnConnectionController(parent)
    , m_serviceWatcher(new QDBusServiceWatcher(
          QString::fromLatin1(BackendDbus::serviceName),
          QDBusConnection::sessionBus(),
          QDBusServiceWatcher::WatchForRegistration
              | QDBusServiceWatcher::WatchForUnregistration,
          this))
    , m_recoveryRetryTimer(new QTimer(this))
{
    m_recoveryRetryTimer->setSingleShot(true);
    connect(m_recoveryRetryTimer, &QTimer::timeout, this, [this] {
        if (!m_backendDestination.isEmpty()) {
            if (m_backendAvailable) {
                requestSnapshot();
            } else {
                authorizeClient();
            }
        }
    });
    connect(m_serviceWatcher, &QDBusServiceWatcher::serviceRegistered,
            this, &AgentVpnClient::onServiceRegistered);
    connect(m_serviceWatcher, &QDBusServiceWatcher::serviceUnregistered,
            this, &AgentVpnClient::onServiceUnregistered);
    ProtonVpnKde::discoverBackendService(QDBusConnection::sessionBus(),
        QString::fromLatin1(BackendDbus::serviceName), false, this, [this](bool present) {
            if (present && m_serviceGeneration == 0) {
                onServiceRegistered({});
            }
        });
}

bool AgentVpnClient::backendAvailable() const { return m_backendAvailable; }
bool AgentVpnClient::ready() const { return m_backendAvailable && m_ready && m_snapshotHealthy; }
bool AgentVpnClient::loggedIn() const { return m_loggedIn; }
bool AgentVpnClient::busy() const { return m_busy; }
int AgentVpnClient::killSwitch() const { return m_killSwitch; }
QString AgentVpnClient::state() const { return m_state; }
QString AgentVpnClient::serverName() const { return m_serverName; }
int AgentVpnClient::forwardedPort() const { return m_forwardedPort; }
QString AgentVpnClient::message() const { return m_message; }

QString AgentVpnClient::primaryActionText() const
{
    if (m_state == QStringLiteral("connected")) {
        return tr("Disconnect");
    }
    if (m_state == QStringLiteral("connecting")
        || m_state == QStringLiteral("error")) {
        return tr("Cancel Connection");
    }
    if (m_state == QStringLiteral("disconnecting")) {
        return tr("Disconnecting…");
    }
    return tr("Connect fastest");
}

ProtonVpnKde::ConnectionActionCapabilities AgentVpnClient::connectionCapabilities() const
{
    return ProtonVpnKde::connectionActionCapabilities(
        m_backendAvailable, m_ready, m_snapshotHealthy, m_loggedIn, m_busy,
        m_state, m_authState, true);
}

void AgentVpnClient::setReconnectionEnabled(bool enabled)
{
    if (m_reconnectionEnabled == enabled && m_reconnectionApplied) {
        return;
    }
    if (m_reconnectionEnabled != enabled) {
        ++m_reconnectionRequestGeneration;
    }
    m_reconnectionEnabled = enabled;
    m_reconnectionApplied = false;
    if (m_backendAvailable) {
        applyReconnectionPreference();
    }
}

void AgentVpnClient::setFastestFeatures(const QStringList &features)
{
    m_fastestFeatures = normalizedServerFeatures(features);
}

void AgentVpnClient::autoConnect(const QString &target)
{
    queueConnection(target, false, true);
}

void AgentVpnClient::activatePrimaryAction()
{
    if (!primaryActionEnabled()) {
        return;
    }
    if (primaryActionDisconnects()) {
        disconnect();
        return;
    }
    queueConnection(QStringLiteral("FASTEST"), true, false);
}

void AgentVpnClient::connectTarget(const QString &target)
{
    queueConnection(target, true, false);
}

void AgentVpnClient::connectGroup(const QString &countryCode,
                                  const QString &groupKind,
                                  const QString &groupName)
{
    const QString normalizedCountry = countryCode.trimmed().toUpper();
    const QString normalizedKind = groupKind.trimmed().toLower();
    const QString normalizedName = groupName.trimmed();
    if (normalizedCountry.size() != 2
        || normalizedCountry.at(0) < QLatin1Char('A')
        || normalizedCountry.at(0) > QLatin1Char('Z')
        || normalizedCountry.at(1) < QLatin1Char('A')
        || normalizedCountry.at(1) > QLatin1Char('Z')
        || (normalizedKind != QStringLiteral("location")
            && normalizedKind != QStringLiteral("secure-core"))
        || normalizedName.isEmpty() || normalizedName.size() > 256
        || normalizedName.contains(QLatin1Char('\0'))
        || normalizedName.contains(QLatin1Char('\n'))
        || normalizedName.contains(QLatin1Char('\r'))) {
        return;
    }
    ++m_connectionIntentGeneration;
    m_pendingTarget.clear();
    m_pendingGroup = {normalizedCountry, normalizedKind, normalizedName};
    m_pendingInteractive = true;
    m_pendingOnlyWhenDisconnected = false;
    if (!m_backendAvailable || !m_snapshotHealthy) {
        m_recoveryRetryCount = 0;
        requestSnapshot(true);
        return;
    }
    acquireTransientLease();
    if (!m_reconnectionApplied) {
        applyReconnectionPreference();
    }
    dispatchPendingConnection();
}

void AgentVpnClient::disconnect()
{
    // Disconnect is a newer user intent even if the backend cannot accept it
    // yet. Retire queued connects before inspecting the current projection so
    // a delayed lease or snapshot cannot dispatch them afterward.
    clearPendingConnection();
    if (!canDisconnect()) {
        releaseTransientLease();
        return;
    }
    callOperation(QString::fromLatin1(BackendDbus::Method::disconnect));
}

void AgentVpnClient::onServiceRegistered(const QString &)
{
    m_recoveryRetryTimer->stop();
    m_recoveryRetryCount = 0;
    m_authorizationRejected = false;
    m_snapshotHealthy = false;
    ++m_serviceGeneration;
    ++m_transientLeaseRequestGeneration;
    m_transientLeasePending = false;
    m_transientLeaseActive = false;
    m_transientLeaseMayExist = false;
    m_operationCompletion.invalidate();
    m_authorizationPending = false;
    disconnectBackendSignals();
    m_backendDestination.clear();
    m_discoveryPending = false;
    m_identityPending = true;
    setBackendAvailable(false);
    m_reconnectionApplied = false;
    m_reconnectionPending = false;
    const quint64 generation = m_serviceGeneration;
    ProtonVpnKde::verifyBackendIdentity(
        QDBusConnection::sessionBus(),
        QString::fromLatin1(BackendDbus::serviceName), this,
        [this, generation](const ProtonVpnKde::BackendIdentityResult &identity) {
            if (generation != m_serviceGeneration) {
                return;
            }
            m_identityPending = false;
            if (!identity.trusted) {
                m_message = tr("The VPN backend could not be authenticated");
                emit snapshotChanged();
                return;
            }
            m_backendDestination = identity.uniqueOwner;
            connectBackendSignals();
            authorizeClient();
        });
}

void AgentVpnClient::onServiceUnregistered(const QString &)
{
    m_recoveryRetryTimer->stop();
    m_recoveryRetryCount = 0;
    m_authorizationRejected = false;
    m_discoveryPending = false;
    m_identityPending = false;
    disconnectBackendSignals();
    m_backendDestination.clear();
    ++m_serviceGeneration;
    setBackendAvailable(false);
    m_ready = false;
    m_snapshotHealthy = false;
    m_authState = QStringLiteral("signed_out");
    m_loggedIn = false;
    m_busy = false;
    m_reconnectionApplied = false;
    m_reconnectionPending = false;
    m_operationCompletion.invalidate();
    m_authorizationPending = false;
    ++m_transientLeaseRequestGeneration;
    m_transientLeasePending = false;
    m_transientLeaseActive = false;
    m_transientLeaseMayExist = false;
    m_killSwitch = 0;
    m_forwardedPort = 0;
    m_state = QStringLiteral("unavailable");
    m_serverName.clear();
    m_message.clear();
    emit snapshotChanged();
}

void AgentVpnClient::onSnapshotChanged(const QString &snapshotJson)
{
    if (!backendSignalIsCurrent()) {
        return;
    }
    applySnapshot(snapshotJson);
}

void AgentVpnClient::setBackendAvailable(bool available)
{
    if (m_backendAvailable == available) {
        return;
    }
    m_backendAvailable = available;
    emit backendAvailableChanged();
    emit snapshotChanged();
}

void AgentVpnClient::stampBackendRequest(
    QDBusPendingCallWatcher *watcher) const
{
    watcher->setProperty("backendGeneration",
                         QVariant::fromValue<qulonglong>(m_serviceGeneration));
    watcher->setProperty("backendDestination", m_backendDestination);
}

bool AgentVpnClient::backendReplyIsCurrent(
    const QDBusPendingCallWatcher *watcher) const
{
    return watcher
        && watcher->property("backendGeneration").toULongLong()
            == m_serviceGeneration
        && watcher->property("backendDestination").toString()
            == m_backendDestination;
}

bool AgentVpnClient::backendSignalIsCurrent() const
{
    return !calledFromDBus()
        || QDBusContext::message().service() == m_backendDestination;
}

void AgentVpnClient::connectBackendSignals()
{
    if (m_backendDestination.isEmpty()) {
        return;
    }
    QDBusConnection::sessionBus().connect(
        m_backendDestination, QString::fromLatin1(BackendDbus::objectPath),
        QString::fromLatin1(BackendDbus::interfaceName),
        QString::fromLatin1(BackendDbus::Signal::snapshotChanged), this,
        SLOT(onSnapshotChanged(QString)));
}

void AgentVpnClient::disconnectBackendSignals()
{
    if (m_backendDestination.isEmpty()) {
        return;
    }
    QDBusConnection::sessionBus().disconnect(
        m_backendDestination, QString::fromLatin1(BackendDbus::objectPath),
        QString::fromLatin1(BackendDbus::interfaceName), {}, this, {});
}

void AgentVpnClient::authorizeClient()
{
    if (m_authorizationPending || m_authorizationRejected || m_backendDestination.isEmpty()) {
        return;
    }
    const QString uniqueName = QDBusConnection::sessionBus().baseService();
    if (uniqueName.isEmpty()) {
        return;
    }
    m_authorizationPending = true;
    const quint64 generation = m_serviceGeneration;
    const QString destination = m_backendDestination;
    QDBusMessage message = QDBusMessage::createMethodCall(
        destination, QString::fromLatin1(BackendDbus::objectPath),
        QString::fromLatin1(BackendDbus::interfaceName),
        QString::fromLatin1(BackendDbus::Method::authorizeClient));
    message << uniqueName;
    auto *watcher = new QDBusPendingCallWatcher(
        QDBusConnection::sessionBus().asyncCall(message, 5000), this);
    connect(watcher, &QDBusPendingCallWatcher::finished, this,
            [this, destination, generation](QDBusPendingCallWatcher *finished) {
        const QDBusPendingReply<> reply = *finished;
        finished->deleteLater();
        if (generation != m_serviceGeneration
            || destination != m_backendDestination) {
            return;
        }
        m_authorizationPending = false;
        if (reply.isError()) {
            setBackendAvailable(false);
            m_message = fixedCallFailureMessage(reply.error());
            m_authorizationRejected = !ProtonVpnKde::isTransientSameOwnerFailure(
                reply.error().type());
            if (!m_authorizationRejected) {
                scheduleRecoveryRead();
            }
            emit snapshotChanged();
            return;
        }
        setBackendAvailable(true);
        applyReconnectionPreference();
        requestSnapshot();
        if (!m_pendingTarget.isEmpty() || !m_pendingGroup.isEmpty()) {
            acquireTransientLease();
        }
    });
}

void AgentVpnClient::scheduleRecoveryRead()
{
    if (!m_backendDestination.isEmpty() && !m_authorizationRejected
        && !m_recoveryRetryTimer->isActive() && m_recoveryRetryCount < 3) {
        m_recoveryRetryTimer->start(250 * (1 << m_recoveryRetryCount));
        ++m_recoveryRetryCount;
    }
}

void AgentVpnClient::requestSnapshot(bool allowActivation,
                                     quint64 operationGeneration)
{
    if (!m_backendAvailable || m_backendDestination.isEmpty()) {
        if (!m_backendDestination.isEmpty()) {
            authorizeClient();
            return;
        }
        if (allowActivation && !m_discoveryPending && !m_identityPending) {
            m_discoveryPending = true;
            const quint64 generation = m_serviceGeneration;
            ProtonVpnKde::discoverBackendService(QDBusConnection::sessionBus(),
                QString::fromLatin1(BackendDbus::serviceName), true, this,
                [this, generation](bool present) {
                    if (generation != m_serviceGeneration) {
                        return;
                    }
                    m_discoveryPending = false;
                    if (present) {
                        onServiceRegistered({});
                    }
                });
        }
        return;
    }
    QDBusMessage message = QDBusMessage::createMethodCall(
        m_backendDestination,
        QString::fromLatin1(BackendDbus::objectPath),
        QString::fromLatin1(BackendDbus::interfaceName),
        QString::fromLatin1(BackendDbus::Method::getSnapshot));
    auto *watcher = new QDBusPendingCallWatcher(
        QDBusConnection::sessionBus().asyncCall(message, 5000), this);
    stampBackendRequest(watcher);
    const quint64 requestGeneration = operationGeneration == 0
        ? m_operationCompletion.generation()
        : operationGeneration;
    watcher->setProperty(
        "operationGeneration",
        QVariant::fromValue<qulonglong>(requestGeneration));
    connect(watcher, &QDBusPendingCallWatcher::finished,
            this, &AgentVpnClient::handleSnapshotReply);
}

void AgentVpnClient::applySnapshot(const QString &snapshotJson)
{
    m_snapshotHealthy = false;
    QJsonParseError error;
    const QJsonDocument document = QJsonDocument::fromJson(
        snapshotJson.toUtf8(), &error);
    if (error.error != QJsonParseError::NoError || !document.isObject()) {
        m_message = tr("The backend returned an invalid state snapshot");
        clearPendingConnection();
        releaseTransientLease();
        emit snapshotChanged();
        return;
    }
    QJsonObject snapshot = document.object();
    const auto compatibility = ProtonVpnKde::normalizeSnapshot(&snapshot);
    if (compatibility == ProtonVpnKde::SnapshotCompatibilityResult::UnsupportedVersion) {
        m_message = tr("The backend uses an unsupported interface version. Restart Plasma VPN after the upgrade completes.");
        clearPendingConnection();
        releaseTransientLease();
        emit snapshotChanged();
        return;
    }
    if (compatibility != ProtonVpnKde::SnapshotCompatibilityResult::Accepted) {
        m_message = tr("The backend returned an incomplete state snapshot");
        clearPendingConnection();
        releaseTransientLease();
        emit snapshotChanged();
        return;
    }

    const quint64 operationGeneration = m_operationCompletion.generation();
    m_snapshotHealthy = true;
    if (m_backendAvailable) {
        m_recoveryRetryTimer->stop();
        m_recoveryRetryCount = 0;
    }
    m_ready = snapshot.value(QStringLiteral("ready")).toBool();
    m_loggedIn = snapshot.value(QStringLiteral("loggedIn")).toBool();
    m_authState = snapshot.value(QStringLiteral("authState")).toString();
    m_busy = snapshot.value(QStringLiteral("busy")).toBool();
    m_killSwitch = std::clamp(
        snapshot.value(QStringLiteral("killSwitch")).toInt(), 0, 2);
    m_forwardedPort = std::clamp(
        snapshot.value(QStringLiteral("forwardedPort")).toInt(), 0, 65535);
    m_state = snapshot.value(QStringLiteral("state")).toString(
        QStringLiteral("disconnected"));
    m_serverName = snapshot.value(QStringLiteral("serverName")).toString();
    m_message = snapshot.value(QStringLiteral("message")).toString();
    emit snapshotChanged();
    dispatchPendingConnection();
    // Emission/dispatch can synchronously start a successor. Only this
    // generation's post-reply reconciliation may release its transient lease.
    if (m_operationCompletion.settleIfIdle(
            operationGeneration, m_ready && !m_busy
                && m_pendingTarget.isEmpty() && m_pendingGroup.isEmpty())) {
        releaseTransientLease();
    }
}

void AgentVpnClient::applyReconnectionPreference()
{
    if (!m_backendAvailable || m_reconnectionPending) {
        return;
    }
    m_reconnectionApplied = false;
    m_reconnectionPending = true;
    const quint64 generation = m_serviceGeneration;
    const quint64 requestGeneration = m_reconnectionRequestGeneration;
    const QString destination = m_backendDestination;
    QDBusMessage message = QDBusMessage::createMethodCall(
        destination,
        QString::fromLatin1(BackendDbus::objectPath),
        QString::fromLatin1(BackendDbus::interfaceName),
        QString::fromLatin1(BackendDbus::Method::setReconnectionEnabled));
    message.setArguments({m_reconnectionEnabled});
    auto *watcher = new QDBusPendingCallWatcher(
        QDBusConnection::sessionBus().asyncCall(message, 5000), this);
    connect(watcher, &QDBusPendingCallWatcher::finished, this,
            [this, destination, generation,
             requestGeneration](QDBusPendingCallWatcher *finished) {
        const QDBusPendingReply<> reply = *finished;
        finished->deleteLater();
        if (generation != m_serviceGeneration
            || destination != m_backendDestination) {
            return;
        }
        m_reconnectionPending = false;
        if (requestGeneration != m_reconnectionRequestGeneration) {
            applyReconnectionPreference();
            return;
        }
        if (reply.isError()) {
            m_reconnectionApplied = false;
            m_message = fixedCallFailureMessage(reply.error());
            clearPendingConnection();
            releaseTransientLease();
            emit snapshotChanged();
            return;
        }
        m_reconnectionApplied = true;
        dispatchPendingConnection();
    });
}

void AgentVpnClient::acquireTransientLease()
{
    if (!m_backendAvailable || m_transientLeasePending
        || m_transientLeaseActive) {
        return;
    }
    const QString uniqueName = QDBusConnection::sessionBus().baseService();
    if (uniqueName.isEmpty()) {
        return;
    }
    m_transientLeasePending = true;
    m_transientLeaseMayExist = true;
    const quint64 leaseRequestGeneration =
        ++m_transientLeaseRequestGeneration;
    const quint64 generation = m_serviceGeneration;
    const quint64 connectionIntentGeneration = m_connectionIntentGeneration;
    const QString destination = m_backendDestination;
    QDBusMessage message = QDBusMessage::createMethodCall(
        destination,
        QString::fromLatin1(BackendDbus::objectPath),
        QString::fromLatin1(BackendDbus::interfaceName),
        QString::fromLatin1(BackendDbus::Method::registerClient));
    message.setArguments({uniqueName});
    auto *watcher = new QDBusPendingCallWatcher(
        QDBusConnection::sessionBus().asyncCall(message, 5000), this);
    connect(watcher, &QDBusPendingCallWatcher::finished, this,
            [this, destination, generation, leaseRequestGeneration,
             connectionIntentGeneration](QDBusPendingCallWatcher *finished) {
        const QDBusPendingReply<> reply = *finished;
        finished->deleteLater();
        if (generation != m_serviceGeneration
            || destination != m_backendDestination
            || leaseRequestGeneration != m_transientLeaseRequestGeneration) {
            return;
        }
        m_transientLeasePending = false;
        const bool currentIntent = connectionIntentGeneration
            == m_connectionIntentGeneration;
        if (reply.isError()) {
            if (!currentIntent) {
                releaseTransientLease();
                if (!m_pendingTarget.isEmpty() || !m_pendingGroup.isEmpty()) {
                    acquireTransientLease();
                }
                return;
            }
            const bool interactive = m_pendingInteractive;
            clearPendingConnection();
            m_message = fixedCallFailureMessage(reply.error());
            releaseTransientLease();
            emit snapshotChanged();
            if (interactive) {
                emit controlCenterRequested();
            }
            return;
        }
        m_transientLeaseActive = true;
        if (!currentIntent && m_pendingTarget.isEmpty()
            && m_pendingGroup.isEmpty()) {
            releaseTransientLease();
            return;
        }
        dispatchPendingConnection();
    });
}

void AgentVpnClient::releaseTransientLease()
{
    if (!m_transientLeaseMayExist && !m_transientLeasePending
        && !m_transientLeaseActive) {
        return;
    }
    ++m_transientLeaseRequestGeneration;
    m_transientLeasePending = false;
    m_transientLeaseActive = false;
    m_transientLeaseMayExist = false;
    const QString uniqueName = QDBusConnection::sessionBus().baseService();
    if (uniqueName.isEmpty() || !m_backendAvailable
        || m_backendDestination.isEmpty()) {
        return;
    }
    QDBusMessage message = QDBusMessage::createMethodCall(
        m_backendDestination,
        QString::fromLatin1(BackendDbus::objectPath),
        QString::fromLatin1(BackendDbus::interfaceName),
        QString::fromLatin1(BackendDbus::Method::unregisterClient));
    message.setArguments({uniqueName});
    QDBusConnection::sessionBus().send(message);
}

void AgentVpnClient::queueConnection(const QString &target, bool interactive,
                                     bool onlyWhenDisconnected)
{
    const QString normalized = target.trimmed().toUpper();
    if (normalized.isEmpty() || normalized.size() > 128
        || normalized.contains(QLatin1Char('\0'))
        || normalized.contains(QLatin1Char('\n'))
        || normalized.contains(QLatin1Char('\r'))) {
        return;
    }
    ++m_connectionIntentGeneration;
    m_pendingGroup.clear();
    m_pendingTarget = normalized;
    m_pendingInteractive = interactive;
    m_pendingOnlyWhenDisconnected = onlyWhenDisconnected;
    if (!m_backendAvailable || !m_snapshotHealthy) {
        m_recoveryRetryCount = 0;
        requestSnapshot(true);
        return;
    }
    acquireTransientLease();
    if (!m_reconnectionApplied) {
        applyReconnectionPreference();
    }
    dispatchPendingConnection();
}

void AgentVpnClient::dispatchPendingConnection()
{
    if ((m_pendingTarget.isEmpty() && m_pendingGroup.isEmpty())
        || !m_backendAvailable || !m_ready || !m_snapshotHealthy
        || !m_transientLeaseActive
        || !m_reconnectionApplied || m_busy) {
        return;
    }
    if (!m_loggedIn || !ProtonVpnKde::accountAllowsConnection(m_authState)) {
        const bool interactive = m_pendingInteractive;
        clearPendingConnection();
        releaseTransientLease();
        if (interactive) {
            emit controlCenterRequested();
        }
        return;
    }
    if (m_pendingOnlyWhenDisconnected
        && m_state != QStringLiteral("disconnected")) {
        clearPendingConnection();
        releaseTransientLease();
        return;
    }
    if (!connectionCapabilities().connect) {
        return;
    }

    const QString target = m_pendingTarget;
    const QStringList group = m_pendingGroup;
    clearPendingConnection();
    if (group.size() == 3) {
        callOperation(QString::fromLatin1(BackendDbus::Method::connectGroup),
                      {group.at(0), group.at(1), group.at(2)});
    } else if (target == QStringLiteral("FASTEST")) {
        if (m_fastestFeatures.isEmpty()) {
            callOperation(QString::fromLatin1(BackendDbus::Method::connectFastest));
        } else {
            callOperation(
                QString::fromLatin1(BackendDbus::Method::connectFastestWithFeatures),
                {QVariant::fromValue(m_fastestFeatures)});
        }
    } else if (target.contains(QLatin1Char('#'))) {
        callOperation(QString::fromLatin1(BackendDbus::Method::connectServer), {target});
    } else {
        callOperation(QString::fromLatin1(BackendDbus::Method::connectCountry), {target});
    }
}

void AgentVpnClient::clearPendingConnection()
{
    // Every terminal path that abandons or consumes a queued connection owns
    // an intent transition. Delayed registration replies can then either serve
    // a genuinely newer request or release their now-orphaned lease.
    ++m_connectionIntentGeneration;
    m_pendingTarget.clear();
    m_pendingGroup.clear();
    m_pendingInteractive = false;
    m_pendingOnlyWhenDisconnected = false;
}

void AgentVpnClient::callOperation(const QString &method,
                                   const QVariantList &arguments)
{
    if (!m_backendAvailable || m_backendDestination.isEmpty()) {
        return;
    }
    const quint64 operationGeneration = m_operationCompletion.begin();
    m_busy = true;
    m_message.clear();
    emit snapshotChanged();
    QDBusMessage message = QDBusMessage::createMethodCall(
        m_backendDestination,
        QString::fromLatin1(BackendDbus::objectPath),
        QString::fromLatin1(BackendDbus::interfaceName), method);
    message.setArguments(arguments);
    auto *watcher = new QDBusPendingCallWatcher(
        QDBusConnection::sessionBus().asyncCall(message, 120000), this);
    stampBackendRequest(watcher);
    watcher->setProperty(
        "operationGeneration",
        QVariant::fromValue<qulonglong>(operationGeneration));
    connect(watcher, &QDBusPendingCallWatcher::finished,
            this, &AgentVpnClient::handleOperationReply);
}

void AgentVpnClient::handleSnapshotReply(QDBusPendingCallWatcher *watcher)
{
    const bool current = backendReplyIsCurrent(watcher);
    const quint64 operationGeneration =
        watcher->property("operationGeneration").toULongLong();
    const QDBusPendingReply<QString> reply = *watcher;
    watcher->deleteLater();
    if (!current || operationGeneration != m_operationCompletion.generation()) {
        return;
    }
    if (reply.isError()) {
        m_snapshotHealthy = false;
        m_busy = false;
        m_operationCompletion.finish(operationGeneration);
        m_message = fixedCallFailureMessage(reply.error());
        if (ProtonVpnKde::isTransientSameOwnerFailure(reply.error().type())) {
            scheduleRecoveryRead();
        }
        const bool interactive = m_pendingInteractive;
        clearPendingConnection();
        releaseTransientLease();
        emit snapshotChanged();
        if (interactive) {
            emit controlCenterRequested();
        }
        return;
    }
    setBackendAvailable(true);
    if (m_serviceGeneration != 0
        && (!m_pendingTarget.isEmpty() || !m_pendingGroup.isEmpty())) {
        acquireTransientLease();
    }
    applySnapshot(reply.value());
}

void AgentVpnClient::handleOperationReply(QDBusPendingCallWatcher *watcher)
{
    const bool current = backendReplyIsCurrent(watcher);
    const quint64 operationGeneration =
        watcher->property("operationGeneration").toULongLong();
    const QDBusPendingReply<> reply = *watcher;
    watcher->deleteLater();
    if (!current || operationGeneration != m_operationCompletion.generation()) {
        return;
    }
    if (reply.isError()) {
        if (ProtonVpnKde::isTransientSameOwnerFailure(reply.error().type())) {
            m_operationCompletion.reconcile(operationGeneration);
            m_busy = true;
            m_message = tr(
                "The VPN operation may still be completing; refreshing its state");
            emit snapshotChanged();
            requestSnapshot(false, operationGeneration);
            return;
        }
        m_busy = false;
        m_operationCompletion.finish(operationGeneration);
        m_message = fixedCallFailureMessage(reply.error());
        emit snapshotChanged();
        if (!m_pendingTarget.isEmpty() || !m_pendingGroup.isEmpty()) {
            requestSnapshot(false, operationGeneration);
        } else {
            releaseTransientLease();
        }
        return;
    }
    m_operationCompletion.reconcile(operationGeneration);
    requestSnapshot(false, operationGeneration);
}
