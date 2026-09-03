// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#include "AgentVpnClient.h"
#include "SnapshotContract.generated.h"

#include "BackendCallPolicy.h"
#include "BackendIdentity.h"
#include "ConnectionAction.h"
#include "DbusContract.h"

#include <QDBusConnection>
#include <QDBusConnectionInterface>
#include <QDBusMessage>
#include <QDBusPendingCallWatcher>
#include <QDBusPendingReply>
#include <QDBusServiceWatcher>
#include <QJsonDocument>
#include <QJsonObject>
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
{
    connect(m_serviceWatcher, &QDBusServiceWatcher::serviceRegistered,
            this, &AgentVpnClient::onServiceRegistered);
    connect(m_serviceWatcher, &QDBusServiceWatcher::serviceUnregistered,
            this, &AgentVpnClient::onServiceUnregistered);
    auto *interface = QDBusConnection::sessionBus().interface();
    if (interface && interface->isServiceRegistered(
            QString::fromLatin1(BackendDbus::serviceName))) {
        onServiceRegistered(QString::fromLatin1(BackendDbus::serviceName));
    }
}

bool AgentVpnClient::backendAvailable() const { return m_backendAvailable; }
bool AgentVpnClient::ready() const { return m_ready; }
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
    return tr("Connect fastest");
}

bool AgentVpnClient::primaryActionEnabled() const
{
    if (!m_backendAvailable) {
        return true;
    }
    const bool disconnectAction = ProtonVpnKde::primaryActionDisconnects(m_state);
    return m_ready && (disconnectAction || m_loggedIn)
        && (!m_busy || m_state == QStringLiteral("connecting"));
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
    if (m_backendAvailable && m_ready
        && ProtonVpnKde::primaryActionDisconnects(m_state)) {
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
    if (!m_backendAvailable) {
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
    if (!m_backendAvailable || !m_ready) {
        releaseTransientLease();
        return;
    }
    // A just-dispatched connect owns busy before its first connecting snapshot
    // arrives. It must still be preemptible from KRunner or another controller.
    if (m_state == QStringLiteral("disconnected") && !m_busy) {
        releaseTransientLease();
        return;
    }
    callOperation(QString::fromLatin1(BackendDbus::Method::disconnect));
}

void AgentVpnClient::onServiceRegistered(const QString &)
{
    ++m_serviceGeneration;
    ++m_transientLeaseRequestGeneration;
    m_transientLeasePending = false;
    m_transientLeaseActive = false;
    m_transientLeaseMayExist = false;
    ++m_operationGeneration;
    m_operationReconciliationGeneration = 0;
    m_authorizationPending = false;
    const auto identity = ProtonVpnKde::verifyBackendIdentity(
        QDBusConnection::sessionBus(),
        QString::fromLatin1(BackendDbus::serviceName));
    if (!identity.trusted) {
        disconnectBackendSignals();
        m_backendDestination.clear();
        setBackendAvailable(false);
        m_message = tr("The VPN backend could not be authenticated");
        emit snapshotChanged();
        return;
    }
    disconnectBackendSignals();
    m_backendDestination = identity.uniqueOwner;
    connectBackendSignals();
    setBackendAvailable(false);
    m_reconnectionApplied = false;
    m_reconnectionPending = false;
    authorizeClient();
}

void AgentVpnClient::onServiceUnregistered(const QString &)
{
    disconnectBackendSignals();
    m_backendDestination.clear();
    ++m_serviceGeneration;
    setBackendAvailable(false);
    m_ready = false;
    m_loggedIn = false;
    m_busy = false;
    m_reconnectionApplied = false;
    m_reconnectionPending = false;
    ++m_operationGeneration;
    m_operationReconciliationGeneration = 0;
    m_authorizationPending = false;
    ++m_transientLeaseRequestGeneration;
    m_transientLeasePending = false;
    m_transientLeaseActive = false;
    m_transientLeaseMayExist = false;
    m_killSwitch = 0;
    m_forwardedPort = 0;
    m_state = QStringLiteral("disconnected");
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
    if (m_authorizationPending || m_backendDestination.isEmpty()) {
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

void AgentVpnClient::requestSnapshot(bool allowActivation,
                                     quint64 operationGeneration)
{
    if (!m_backendAvailable || m_backendDestination.isEmpty()) {
        if (allowActivation) {
            if (auto *interface = QDBusConnection::sessionBus().interface()) {
                static_cast<void>(interface->startService(
                    QString::fromLatin1(BackendDbus::serviceName)));
            }
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
        ? m_operationGeneration
        : operationGeneration;
    watcher->setProperty(
        "operationGeneration",
        QVariant::fromValue<qulonglong>(requestGeneration));
    connect(watcher, &QDBusPendingCallWatcher::finished,
            this, &AgentVpnClient::handleSnapshotReply);
}

void AgentVpnClient::applySnapshot(const QString &snapshotJson)
{
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
    const QJsonObject snapshot = document.object();
    if (snapshot.value(QStringLiteral("schemaVersion")).toInt()
        != ProtonVpnKde::snapshotSchemaVersion) {
        m_message = tr("The backend uses an unsupported interface version");
        clearPendingConnection();
        releaseTransientLease();
        emit snapshotChanged();
        return;
    }
    if (!ProtonVpnKde::validateSnapshotV1(snapshot)) {
        m_message = tr("The backend returned an incomplete state snapshot");
        clearPendingConnection();
        releaseTransientLease();
        emit snapshotChanged();
        return;
    }

    m_ready = snapshot.value(QStringLiteral("ready")).toBool();
    m_loggedIn = snapshot.value(QStringLiteral("loggedIn")).toBool();
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
    if (!m_backendAvailable) {
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
        || !m_backendAvailable || !m_ready
        || !m_transientLeaseActive
        || !m_reconnectionApplied || m_busy) {
        return;
    }
    if (!m_loggedIn) {
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
    const quint64 operationGeneration = ++m_operationGeneration;
    m_operationReconciliationGeneration = 0;
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
    if (!current || operationGeneration != m_operationGeneration) {
        return;
    }
    if (reply.isError()) {
        m_busy = false;
        if (m_operationReconciliationGeneration == operationGeneration) {
            m_operationReconciliationGeneration = 0;
        }
        m_message = fixedCallFailureMessage(reply.error());
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
    const bool settlesOperation = operationGeneration != 0
        && operationGeneration == m_operationGeneration;
    if (m_operationReconciliationGeneration == operationGeneration) {
        m_operationReconciliationGeneration = 0;
    }
    applySnapshot(reply.value());
    // applySnapshot may synchronously dispatch a newer queued operation.  An
    // older reconciliation owns lease retirement only while its operation
    // generation is still current and no successor still needs the lease.
    if (settlesOperation && operationGeneration == m_operationGeneration
        && !m_busy && m_pendingTarget.isEmpty() && m_pendingGroup.isEmpty()) {
        releaseTransientLease();
    }
}

void AgentVpnClient::handleOperationReply(QDBusPendingCallWatcher *watcher)
{
    const bool current = backendReplyIsCurrent(watcher);
    const quint64 operationGeneration =
        watcher->property("operationGeneration").toULongLong();
    const QDBusPendingReply<> reply = *watcher;
    watcher->deleteLater();
    if (!current || operationGeneration != m_operationGeneration) {
        return;
    }
    if (reply.isError()) {
        if (ProtonVpnKde::isTransientSameOwnerFailure(reply.error().type())) {
            m_operationReconciliationGeneration = operationGeneration;
            m_busy = true;
            m_message = tr(
                "The VPN operation may still be completing; refreshing its state");
            emit snapshotChanged();
            requestSnapshot(false, operationGeneration);
            return;
        }
        m_busy = false;
        m_operationReconciliationGeneration = 0;
        m_message = fixedCallFailureMessage(reply.error());
        emit snapshotChanged();
        if (!m_pendingTarget.isEmpty() || !m_pendingGroup.isEmpty()) {
            requestSnapshot(false, operationGeneration);
        } else {
            releaseTransientLease();
        }
        return;
    }
    m_operationReconciliationGeneration = 0;
    requestSnapshot(false, operationGeneration);
}
