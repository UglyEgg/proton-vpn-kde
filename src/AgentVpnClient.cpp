#include "AgentVpnClient.h"

#include "BackendCallPolicy.h"
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
constexpr auto kBackendService = "proton.vpn.app.kde.backend";
constexpr auto kBackendPath = "/proton/vpn/app/kde/backend";
constexpr auto kBackendInterface = "proton.vpn.app.kde.Backend1";

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
    QDBusConnection::sessionBus().connect(
        QString::fromLatin1(kBackendService),
        QString::fromLatin1(kBackendPath),
        QString::fromLatin1(kBackendInterface),
        QStringLiteral("SnapshotChanged"),
        this, SLOT(onSnapshotChanged(QString)));

    const auto *interface = QDBusConnection::sessionBus().interface();
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
    setBackendAvailable(true);
    m_reconnectionApplied = false;
    applyReconnectionPreference();
    requestSnapshot();
}

void AgentVpnClient::onServiceUnregistered(const QString &)
{
    setBackendAvailable(false);
    m_ready = false;
    m_loggedIn = false;
    m_busy = false;
    m_reconnectionApplied = false;
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

void AgentVpnClient::requestSnapshot(bool allowActivation)
{
    if (!allowActivation && !m_backendAvailable) {
        return;
    }
    QDBusMessage message = QDBusMessage::createMethodCall(
        QString::fromLatin1(kBackendService),
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
        emit snapshotChanged();
        return;
    }
    const QJsonObject snapshot = document.object();
    if (snapshot.value(QStringLiteral("schemaVersion")).toInt() != 1) {
        m_message = tr("The backend uses an unsupported interface version");
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
        QString::fromLatin1(kBackendService),
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
    m_pendingTarget = normalized;
    m_pendingInteractive = interactive;
    m_pendingOnlyWhenDisconnected = onlyWhenDisconnected;
    if (!m_backendAvailable) {
        requestSnapshot(true);
        return;
    }
    dispatchPendingConnection();
}

void AgentVpnClient::dispatchPendingConnection()
{
    if (m_pendingTarget.isEmpty() || !m_backendAvailable || !m_ready
        || !m_reconnectionApplied || m_busy) {
        return;
    }
    if (!m_loggedIn) {
        const bool interactive = m_pendingInteractive;
        m_pendingTarget.clear();
        if (interactive) {
            emit controlCenterRequested();
        }
        return;
    }
    if (m_pendingOnlyWhenDisconnected
        && m_state != QStringLiteral("disconnected")) {
        m_pendingTarget.clear();
        return;
    }

    const QString target = m_pendingTarget;
    m_pendingTarget.clear();
    m_pendingInteractive = false;
    m_pendingOnlyWhenDisconnected = false;
    if (target == QStringLiteral("FASTEST")) {
        callOperation(QStringLiteral("ConnectFastest"));
    } else if (target.contains(QLatin1Char('#'))) {
        callOperation(QStringLiteral("ConnectServer"), {target});
    } else {
        callOperation(QStringLiteral("ConnectCountry"), {target});
    }
}

void AgentVpnClient::callOperation(const QString &method,
                                   const QVariantList &arguments)
{
    m_busy = true;
    m_message.clear();
    emit snapshotChanged();
    QDBusMessage message = QDBusMessage::createMethodCall(
        QString::fromLatin1(kBackendService),
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
        m_pendingTarget.clear();
        emit snapshotChanged();
        if (interactive) {
            emit controlCenterRequested();
        }
        return;
    }
    setBackendAvailable(true);
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
        return;
    }
    requestSnapshot();
}
