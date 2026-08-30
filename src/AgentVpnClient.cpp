#include "AgentVpnClient.h"

#include "BackendCallPolicy.h"
#include "BackendIdentity.h"
#include "ConnectionAction.h"

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
constexpr auto kBackendService = "quest.entropy.PlasmaVPN.Backend";
constexpr auto kBackendPath = "/quest/entropy/PlasmaVPN/Backend";
constexpr auto kBackendInterface = "quest.entropy.PlasmaVPN.Backend1";

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
          QString::fromLatin1(kBackendService),
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
            QString::fromLatin1(kBackendService))) {
        onServiceRegistered(QString::fromLatin1(kBackendService));
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
    return m_ready && m_loggedIn
        && (!m_busy || m_state == QStringLiteral("connecting"));
}

void AgentVpnClient::setReconnectionEnabled(bool enabled)
{
    if (m_reconnectionEnabled == enabled && m_reconnectionApplied) {
        return;
    }
    m_reconnectionEnabled = enabled;
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
    if (m_backendAvailable && m_ready && m_loggedIn
        && ProtonVpnKde::primaryActionDisconnects(m_state)) {
        callOperation(QStringLiteral("Disconnect"));
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
    m_pendingTarget.clear();
    m_pendingGroup = {normalizedCountry, normalizedKind, normalizedName};
    m_pendingInteractive = true;
    m_pendingOnlyWhenDisconnected = false;
    if (!m_backendAvailable) {
        requestSnapshot(true);
        return;
    }
    acquireTransientLease();
    dispatchPendingConnection();
}

void AgentVpnClient::disconnect()
{
    if (!m_backendAvailable || !m_ready || !m_loggedIn
        || m_state == QStringLiteral("disconnected")) {
        return;
    }
    callOperation(QStringLiteral("Disconnect"));
}

void AgentVpnClient::onServiceRegistered(const QString &)
{
    ++m_serviceGeneration;
    m_transientLeasePending = false;
    m_transientLeaseActive = false;
    m_authorizationPending = false;
    const auto identity = ProtonVpnKde::verifyBackendIdentity(
        QDBusConnection::sessionBus(), QString::fromLatin1(kBackendService));
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
    m_authorizationPending = false;
    m_transientLeasePending = false;
    m_transientLeaseActive = false;
    m_killSwitch = 0;
    m_forwardedPort = 0;
    m_state = QStringLiteral("disconnected");
    m_serverName.clear();
    m_message.clear();
    emit snapshotChanged();
}

void AgentVpnClient::onSnapshotChanged(const QString &snapshotJson)
{
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

void AgentVpnClient::connectBackendSignals()
{
    if (m_backendDestination.isEmpty()) {
        return;
    }
    QDBusConnection::sessionBus().connect(
        m_backendDestination, QString::fromLatin1(kBackendPath),
        QString::fromLatin1(kBackendInterface),
        QStringLiteral("SnapshotChanged"), this,
        SLOT(onSnapshotChanged(QString)));
}

void AgentVpnClient::disconnectBackendSignals()
{
    if (m_backendDestination.isEmpty()) {
        return;
    }
    QDBusConnection::sessionBus().disconnect(
        m_backendDestination, QString::fromLatin1(kBackendPath),
        QString::fromLatin1(kBackendInterface), {}, this, {});
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
    QDBusMessage message = QDBusMessage::createMethodCall(
        m_backendDestination, QString::fromLatin1(kBackendPath),
        QString::fromLatin1(kBackendInterface),
        QStringLiteral("AuthorizeClient"));
    message << uniqueName;
    auto *watcher = new QDBusPendingCallWatcher(
        QDBusConnection::sessionBus().asyncCall(message, 5000), this);
    connect(watcher, &QDBusPendingCallWatcher::finished, this,
            [this, generation](QDBusPendingCallWatcher *finished) {
        const QDBusPendingReply<> reply = *finished;
        finished->deleteLater();
        if (generation != m_serviceGeneration) {
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
        if (!m_pendingTarget.isEmpty()) {
            acquireTransientLease();
        }
    });
}

void AgentVpnClient::requestSnapshot(bool allowActivation)
{
    if (!m_backendAvailable || m_backendDestination.isEmpty()) {
        if (allowActivation) {
            if (auto *interface = QDBusConnection::sessionBus().interface()) {
                static_cast<void>(interface->startService(
                    QString::fromLatin1(kBackendService)));
            }
        }
        return;
    }
    QDBusMessage message = QDBusMessage::createMethodCall(
        m_backendDestination,
        QString::fromLatin1(kBackendPath),
        QString::fromLatin1(kBackendInterface),
        QStringLiteral("GetSnapshot"));
    auto *watcher = new QDBusPendingCallWatcher(
        QDBusConnection::sessionBus().asyncCall(message, 5000), this);
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
    if (snapshot.value(QStringLiteral("schemaVersion")).toInt() != 1) {
        m_message = tr("The backend uses an unsupported interface version");
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
    if (!m_backendAvailable) {
        return;
    }
    m_reconnectionApplied = false;
    QDBusMessage message = QDBusMessage::createMethodCall(
        m_backendDestination,
        QString::fromLatin1(kBackendPath),
        QString::fromLatin1(kBackendInterface),
        QStringLiteral("SetReconnectionEnabled"));
    message.setArguments({m_reconnectionEnabled});
    auto *watcher = new QDBusPendingCallWatcher(
        QDBusConnection::sessionBus().asyncCall(message, 5000), this);
    connect(watcher, &QDBusPendingCallWatcher::finished, this,
            [this](QDBusPendingCallWatcher *finished) {
        const QDBusPendingReply<> reply = *finished;
        finished->deleteLater();
        m_reconnectionApplied = true;
        if (reply.isError()) {
            m_message = fixedCallFailureMessage(reply.error());
            emit snapshotChanged();
        }
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
    const quint64 generation = m_serviceGeneration;
    QDBusMessage message = QDBusMessage::createMethodCall(
        m_backendDestination,
        QString::fromLatin1(kBackendPath),
        QString::fromLatin1(kBackendInterface),
        QStringLiteral("RegisterClient"));
    message.setArguments({uniqueName});
    auto *watcher = new QDBusPendingCallWatcher(
        QDBusConnection::sessionBus().asyncCall(message, 5000), this);
    connect(watcher, &QDBusPendingCallWatcher::finished, this,
            [this, generation](QDBusPendingCallWatcher *finished) {
        const QDBusPendingReply<> reply = *finished;
        finished->deleteLater();
        if (generation != m_serviceGeneration) {
            return;
        }
        m_transientLeasePending = false;
        if (reply.isError()) {
            const bool interactive = m_pendingInteractive;
            clearPendingConnection();
            m_message = fixedCallFailureMessage(reply.error());
            emit snapshotChanged();
            if (interactive) {
                emit controlCenterRequested();
            }
            return;
        }
        m_transientLeaseActive = true;
        dispatchPendingConnection();
    });
}

void AgentVpnClient::releaseTransientLease()
{
    if (!m_transientLeaseActive) {
        return;
    }
    m_transientLeaseActive = false;
    const QString uniqueName = QDBusConnection::sessionBus().baseService();
    if (uniqueName.isEmpty() || !m_backendAvailable
        || m_backendDestination.isEmpty()) {
        return;
    }
    QDBusMessage message = QDBusMessage::createMethodCall(
        m_backendDestination,
        QString::fromLatin1(kBackendPath),
        QString::fromLatin1(kBackendInterface),
        QStringLiteral("UnregisterClient"));
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
    m_pendingGroup.clear();
    m_pendingTarget = normalized;
    m_pendingInteractive = interactive;
    m_pendingOnlyWhenDisconnected = onlyWhenDisconnected;
    if (!m_backendAvailable) {
        requestSnapshot(true);
        return;
    }
    acquireTransientLease();
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
        callOperation(QStringLiteral("ConnectGroup"),
                      {group.at(0), group.at(1), group.at(2)});
    } else if (target == QStringLiteral("FASTEST")) {
        if (m_fastestFeatures.isEmpty()) {
            callOperation(QStringLiteral("ConnectFastest"));
        } else {
            callOperation(
                QStringLiteral("ConnectFastestWithFeatures"),
                {QVariant::fromValue(m_fastestFeatures)});
        }
    } else if (target.contains(QLatin1Char('#'))) {
        callOperation(QStringLiteral("ConnectServer"), {target});
    } else {
        callOperation(QStringLiteral("ConnectCountry"), {target});
    }
}

void AgentVpnClient::clearPendingConnection()
{
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
    m_busy = true;
    m_message.clear();
    emit snapshotChanged();
    QDBusMessage message = QDBusMessage::createMethodCall(
        m_backendDestination,
        QString::fromLatin1(kBackendPath),
        QString::fromLatin1(kBackendInterface), method);
    message.setArguments(arguments);
    auto *watcher = new QDBusPendingCallWatcher(
        QDBusConnection::sessionBus().asyncCall(message, 120000), this);
    connect(watcher, &QDBusPendingCallWatcher::finished,
            this, &AgentVpnClient::handleOperationReply);
}

void AgentVpnClient::handleSnapshotReply(QDBusPendingCallWatcher *watcher)
{
    const QDBusPendingReply<QString> reply = *watcher;
    watcher->deleteLater();
    if (reply.isError()) {
        m_busy = false;
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
    applySnapshot(reply.value());
}

void AgentVpnClient::handleOperationReply(QDBusPendingCallWatcher *watcher)
{
    const QDBusPendingReply<> reply = *watcher;
    watcher->deleteLater();
    if (reply.isError()) {
        m_busy = false;
        m_message = fixedCallFailureMessage(reply.error());
        emit snapshotChanged();
        releaseTransientLease();
        return;
    }
    releaseTransientLease();
    requestSnapshot();
}
