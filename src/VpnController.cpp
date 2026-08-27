#include "VpnController.h"

#include "LocationModels.h"
#include "SecretTransport.h"

#include <QAbstractItemModel>
#include <QDBusConnection>
#include <QDBusConnectionInterface>
#include <QDBusError>
#include <QDBusMessage>
#include <QDBusPendingCallWatcher>
#include <QDBusPendingReply>
#include <QDBusServiceWatcher>
#include <QJsonDocument>
#include <QJsonObject>

namespace
{
constexpr auto kBackendService = "proton.vpn.app.kde.backend";
constexpr auto kBackendPath = "/proton/vpn/app/kde/backend";
constexpr auto kBackendInterface = "proton.vpn.app.kde.Backend1";
}

VpnController::VpnController(QObject *parent)
    : QObject(parent)
    , m_serviceWatcher(new QDBusServiceWatcher(
          QString::fromLatin1(kBackendService),
          QDBusConnection::sessionBus(),
          QDBusServiceWatcher::WatchForRegistration
              | QDBusServiceWatcher::WatchForUnregistration,
          this))
    , m_countryModel(new CountryModel(this))
    , m_serverModel(new ServerModel(this))
    , m_countryFilterModel(new LocationFilterProxyModel(this))
    , m_serverFilterModel(new LocationFilterProxyModel(this))
{
    m_countryFilterModel->setSourceModel(m_countryModel);
    m_countryFilterModel->setSearchRoles({CountryModel::CodeRole, CountryModel::NameRole});
    m_serverFilterModel->setSourceModel(m_serverModel);
    m_serverFilterModel->setSearchRoles({ServerModel::NameRole, ServerModel::LocationRole});
    m_serverFilterModel->sortByRole(ServerModel::LoadRole);

    connect(m_serviceWatcher, &QDBusServiceWatcher::serviceRegistered,
            this, &VpnController::onServiceRegistered);
    connect(m_serviceWatcher, &QDBusServiceWatcher::serviceUnregistered,
            this, &VpnController::onServiceUnregistered);

    QDBusConnection::sessionBus().connect(
        QString::fromLatin1(kBackendService),
        QString::fromLatin1(kBackendPath),
        QString::fromLatin1(kBackendInterface),
        QStringLiteral("SnapshotChanged"),
        this,
        SLOT(onSnapshotChanged(QString)));
    QDBusConnection::sessionBus().connect(
        QString::fromLatin1(kBackendService),
        QString::fromLatin1(kBackendPath),
        QString::fromLatin1(kBackendInterface),
        QStringLiteral("ServerDataChanged"),
        this,
        SLOT(onServerDataChanged(bool)));

    const auto *interface = QDBusConnection::sessionBus().interface();
    setBackendAvailable(interface && interface->isServiceRegistered(
        QString::fromLatin1(kBackendService)));
    // Calling the well-known name also activates the backend through D-Bus on
    // installed systems. In a development tree it simply reports that the
    // service is not installed yet.
    refresh();
}

bool VpnController::backendAvailable() const { return m_backendAvailable; }
bool VpnController::ready() const { return m_ready; }
bool VpnController::loggedIn() const { return m_loggedIn; }
QString VpnController::authState() const { return m_authState; }
QString VpnController::accountName() const { return m_accountName; }
QString VpnController::planTitle() const { return m_planTitle; }
int VpnController::userTier() const { return m_userTier; }
int VpnController::maxConnections() const { return m_maxConnections; }
bool VpnController::fido2Available() const { return m_fido2Available; }
bool VpnController::busy() const { return m_busy; }
bool VpnController::locationsBusy() const { return m_locationsBusy; }
QString VpnController::state() const { return m_state; }
QString VpnController::serverName() const { return m_serverName; }
QString VpnController::message() const { return m_message; }

QString VpnController::primaryActionText() const
{
    if (m_state == QStringLiteral("connected")
        || m_state == QStringLiteral("connecting")) {
        return tr("Disconnect");
    }
    return tr("Connect fastest");
}

bool VpnController::primaryActionEnabled() const
{
    return m_backendAvailable && m_ready && m_loggedIn && !m_busy;
}

QAbstractItemModel *VpnController::countryModel() const { return m_countryFilterModel; }
QAbstractItemModel *VpnController::serverModel() const { return m_serverFilterModel; }

void VpnController::refresh()
{
    QDBusMessage message = QDBusMessage::createMethodCall(
        QString::fromLatin1(kBackendService),
        QString::fromLatin1(kBackendPath),
        QString::fromLatin1(kBackendInterface),
        QStringLiteral("GetSnapshot"));
    auto *watcher = new QDBusPendingCallWatcher(
        QDBusConnection::sessionBus().asyncCall(message, 5000), this);
    connect(watcher, &QDBusPendingCallWatcher::finished,
            this, &VpnController::handleSnapshotReply);
}

void VpnController::activatePrimaryAction()
{
    if (!primaryActionEnabled()) {
        return;
    }
    const bool shouldDisconnect = m_state == QStringLiteral("connected")
        || m_state == QStringLiteral("connecting");
    callOperation(shouldDisconnect ? QStringLiteral("Disconnect")
                                   : QStringLiteral("ConnectFastest"));
}

void VpnController::loadCountries()
{
    if (!m_backendAvailable || !m_ready || !m_loggedIn) {
        return;
    }
    if (m_locationsBusy) {
        m_countryRefreshPending = true;
        return;
    }
    m_countryRefreshPending = false;
    setLocationsBusy(true);
    QDBusMessage message = QDBusMessage::createMethodCall(
        QString::fromLatin1(kBackendService),
        QString::fromLatin1(kBackendPath),
        QString::fromLatin1(kBackendInterface),
        QStringLiteral("GetCountries"));
    auto *watcher = new QDBusPendingCallWatcher(
        QDBusConnection::sessionBus().asyncCall(message, 30000), this);
    connect(watcher, &QDBusPendingCallWatcher::finished,
            this, &VpnController::handleCountriesReply);
}

void VpnController::loadServers(const QString &countryCode)
{
    const QString normalizedCode = countryCode.trimmed().toUpper();
    if (normalizedCode.size() != 2) {
        return;
    }
    const bool countryChanged = m_currentServerCountry != normalizedCode;
    m_currentServerCountry = normalizedCode;
    if (countryChanged) {
        m_serverModel->clear();
    }
    if (!m_backendAvailable || !m_ready || !m_loggedIn) {
        return;
    }
    if (m_locationsBusy) {
        m_serverRefreshPending = true;
        return;
    }
    m_serverRefreshPending = false;
    setLocationsBusy(true);
    QDBusMessage message = QDBusMessage::createMethodCall(
        QString::fromLatin1(kBackendService),
        QString::fromLatin1(kBackendPath),
        QString::fromLatin1(kBackendInterface),
        QStringLiteral("GetServers"));
    message << normalizedCode;
    auto *watcher = new QDBusPendingCallWatcher(
        QDBusConnection::sessionBus().asyncCall(message, 30000), this);
    watcher->setProperty("countryCode", normalizedCode);
    connect(watcher, &QDBusPendingCallWatcher::finished,
            this, &VpnController::handleServersReply);
}

void VpnController::clearServerContext()
{
    m_currentServerCountry.clear();
    m_serverRefreshPending = false;
    m_serverLoadsRefreshPending = false;
    m_serverModel->clear();
}

void VpnController::connectCountry(const QString &countryCode)
{
    if (primaryActionEnabled()) {
        callOperation(QStringLiteral("ConnectCountry"), {countryCode});
    }
}

void VpnController::connectServer(const QString &serverName)
{
    if (primaryActionEnabled()) {
        callOperation(QStringLiteral("ConnectServer"), {serverName});
    }
}

void VpnController::login(const QString &username, const QString &password)
{
    callSecretOperation(
        QStringLiteral("Login"),
        {{QStringLiteral("username"), username},
         {QStringLiteral("password"), password}});
}

void VpnController::submitTwoFactor(const QString &code)
{
    callSecretOperation(
        QStringLiteral("SubmitTwoFactor"),
        {{QStringLiteral("code"), code}});
}

void VpnController::cancelLogin()
{
    callOperation(QStringLiteral("CancelLogin"));
}

void VpnController::beginFido2()
{
    callOperation(QStringLiteral("BeginFido2"));
}

void VpnController::submitFido2Pin(const QString &pin)
{
    callSecretOperation(
        QStringLiteral("SubmitFido2Pin"),
        {{QStringLiteral("pin"), pin}},
        false);
}

void VpnController::cancelFido2()
{
    callControlOperation(QStringLiteral("CancelFido2"));
}

void VpnController::logout()
{
    callOperation(QStringLiteral("Logout"));
}

void VpnController::setCountryFilter(const QString &filterText)
{
    m_countryFilterModel->setFilterText(filterText);
}

void VpnController::setServerFilter(const QString &filterText)
{
    m_serverFilterModel->setFilterText(filterText);
}

void VpnController::setServerSortMode(const QString &mode)
{
    if (mode == QStringLiteral("name")) {
        m_serverFilterModel->sortByRole(ServerModel::NameRole);
    } else if (mode == QStringLiteral("location")) {
        m_serverFilterModel->sortByRole(ServerModel::LocationRole);
    } else {
        m_serverFilterModel->sortByRole(ServerModel::LoadRole);
    }
}

void VpnController::setReconnectionEnabled(bool enabled)
{
    m_reconnectionEnabled = enabled;
    if (!m_backendAvailable) {
        return;
    }
    QDBusMessage message = QDBusMessage::createMethodCall(
        QString::fromLatin1(kBackendService),
        QString::fromLatin1(kBackendPath),
        QString::fromLatin1(kBackendInterface),
        QStringLiteral("SetReconnectionEnabled"));
    message << enabled;
    QDBusConnection::sessionBus().asyncCall(message, 5000);
}

void VpnController::onServiceRegistered(const QString &)
{
    setBackendAvailable(true);
    setReconnectionEnabled(m_reconnectionEnabled);
    refresh();
}

void VpnController::onServiceUnregistered(const QString &)
{
    setBackendAvailable(false);
    m_ready = false;
    m_busy = false;
    m_state = QStringLiteral("unavailable");
    m_message = tr("The Proton backend service stopped");
    m_countryModel->clear();
    m_serverModel->clear();
    m_countryRefreshPending = false;
    m_serverRefreshPending = false;
    m_serverLoadsRefreshPending = false;
    m_currentServerCountry.clear();
    emit snapshotChanged();
}

void VpnController::onSnapshotChanged(const QString &snapshotJson)
{
    applySnapshot(snapshotJson);
}

void VpnController::onServerDataChanged(bool topologyChanged)
{
    if (topologyChanged) {
        m_countryRefreshPending = true;
        m_serverRefreshPending = !m_currentServerCountry.isEmpty();
        m_serverLoadsRefreshPending = false;
    } else if (!m_currentServerCountry.isEmpty()) {
        m_serverLoadsRefreshPending = true;
    }
    dispatchPendingLocationRefreshes();
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

    const bool wasLoggedIn = m_loggedIn;
    m_ready = snapshot.value(QStringLiteral("ready")).toBool();
    m_loggedIn = snapshot.value(QStringLiteral("loggedIn")).toBool();
    m_authState = snapshot.value(QStringLiteral("authState")).toString(
        m_loggedIn ? QStringLiteral("signed_in") : QStringLiteral("signed_out"));
    m_accountName = snapshot.value(QStringLiteral("accountName")).toString();
    m_planTitle = snapshot.value(QStringLiteral("planTitle")).toString();
    m_userTier = snapshot.value(QStringLiteral("userTier")).toInt();
    m_maxConnections = snapshot.value(QStringLiteral("maxConnections")).toInt();
    m_fido2Available = snapshot.value(QStringLiteral("fido2Available")).toBool();
    m_busy = snapshot.value(QStringLiteral("busy")).toBool();
    m_state = snapshot.value(QStringLiteral("state")).toString(
        QStringLiteral("unavailable"));
    m_serverName = snapshot.value(QStringLiteral("serverName")).toString();
    m_message = snapshot.value(QStringLiteral("message")).toString();
    if (wasLoggedIn && !m_loggedIn) {
        m_countryModel->clear();
        m_serverModel->clear();
        m_countryRefreshPending = false;
        m_serverRefreshPending = false;
        m_serverLoadsRefreshPending = false;
        m_currentServerCountry.clear();
    }
    emit snapshotChanged();
    if (m_loggedIn && m_countryModel->rowCount() == 0 && !m_locationsBusy) {
        loadCountries();
    }
}

void VpnController::callOperation(const QString &method,
                                  const QVariantList &arguments)
{
    m_busy = true;
    m_message.clear();
    emit snapshotChanged();

    QDBusMessage message = QDBusMessage::createMethodCall(
        QString::fromLatin1(kBackendService),
        QString::fromLatin1(kBackendPath),
        QString::fromLatin1(kBackendInterface),
        method);
    message.setArguments(arguments);
    auto *watcher = new QDBusPendingCallWatcher(
        QDBusConnection::sessionBus().asyncCall(message, 120000), this);
    connect(watcher, &QDBusPendingCallWatcher::finished,
            this, &VpnController::handleOperationReply);
}

void VpnController::callSecretOperation(const QString &method,
                                        const QJsonObject &fields,
                                        bool updateBusy)
{
    if (updateBusy) {
        m_busy = true;
        m_message.clear();
        emit snapshotChanged();
    }

    QDBusMessage keyRequest = QDBusMessage::createMethodCall(
        QString::fromLatin1(kBackendService),
        QString::fromLatin1(kBackendPath),
        QString::fromLatin1(kBackendInterface),
        QStringLiteral("GetAuthPublicKey"));
    auto *watcher = new QDBusPendingCallWatcher(
        QDBusConnection::sessionBus().asyncCall(keyRequest, 5000), this);
    connect(watcher, &QDBusPendingCallWatcher::finished, this,
            [this, method, fields, updateBusy](QDBusPendingCallWatcher *finished) {
        const QDBusPendingReply<QString> reply = *finished;
        finished->deleteLater();
        if (reply.isError()) {
            if (updateBusy) {
                m_busy = false;
            }
            m_message = tr("Unable to initialize protected authentication");
            emit snapshotChanged();
            return;
        }

        QString errorMessage;
        const QByteArray publicKey = QByteArray::fromBase64(reply.value().toLatin1());
        const QDBusUnixFileDescriptor descriptor =
            SecretTransport::createSealedPayload(fields, publicKey, &errorMessage);
        if (!descriptor.isValid()) {
            if (updateBusy) {
                m_busy = false;
            }
            m_message = tr("Unable to protect the authentication data: %1")
                            .arg(errorMessage);
            emit snapshotChanged();
            return;
        }

        const QVariant argument = QVariant::fromValue(descriptor);
        if (updateBusy) {
            callOperation(method, {argument});
        } else {
            callControlOperation(method, {argument});
        }
    });
}

void VpnController::callControlOperation(const QString &method,
                                         const QVariantList &arguments)
{
    QDBusMessage message = QDBusMessage::createMethodCall(
        QString::fromLatin1(kBackendService),
        QString::fromLatin1(kBackendPath),
        QString::fromLatin1(kBackendInterface),
        method);
    message.setArguments(arguments);
    QDBusConnection::sessionBus().asyncCall(message, 5000);
}

void VpnController::requestServerLoads()
{
    if (m_currentServerCountry.isEmpty()
        || !m_backendAvailable || !m_ready || !m_loggedIn) {
        return;
    }
    if (m_locationsBusy) {
        m_serverLoadsRefreshPending = true;
        return;
    }
    m_serverLoadsRefreshPending = false;
    setLocationsBusy(true);
    QDBusMessage message = QDBusMessage::createMethodCall(
        QString::fromLatin1(kBackendService),
        QString::fromLatin1(kBackendPath),
        QString::fromLatin1(kBackendInterface),
        QStringLiteral("GetServerLoads"));
    message << m_currentServerCountry;
    auto *watcher = new QDBusPendingCallWatcher(
        QDBusConnection::sessionBus().asyncCall(message, 30000), this);
    watcher->setProperty("countryCode", m_currentServerCountry);
    connect(watcher, &QDBusPendingCallWatcher::finished,
            this, &VpnController::handleServerLoadsReply);
}

void VpnController::dispatchPendingLocationRefreshes()
{
    if (m_locationsBusy || !m_backendAvailable || !m_ready || !m_loggedIn) {
        return;
    }
    if (m_countryRefreshPending) {
        loadCountries();
    } else if (m_serverRefreshPending && !m_currentServerCountry.isEmpty()) {
        loadServers(m_currentServerCountry);
    } else if (m_serverLoadsRefreshPending) {
        requestServerLoads();
    }
}

void VpnController::setLocationsBusy(bool busy)
{
    if (m_locationsBusy == busy) {
        return;
    }
    m_locationsBusy = busy;
    emit locationsChanged();
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
        if (reply.error().name()
            == QStringLiteral("proton.vpn.app.kde.Error.InvalidSecretPayload")) {
            m_message = tr("Protected authentication data was rejected; try again");
        } else {
            m_message = tr("The VPN operation could not be completed");
        }
        emit snapshotChanged();
        return;
    }
    refresh();
}

void VpnController::handleCountriesReply(QDBusPendingCallWatcher *watcher)
{
    const QDBusPendingReply<QString> reply = *watcher;
    watcher->deleteLater();
    setLocationsBusy(false);
    if (reply.isError()) {
        m_message = tr("Unable to load countries");
        emit snapshotChanged();
        dispatchPendingLocationRefreshes();
        return;
    }
    QString errorMessage;
    if (!m_countryModel->resetFromJson(reply.value(), &errorMessage)) {
        m_message = errorMessage;
        emit snapshotChanged();
    }
    dispatchPendingLocationRefreshes();
}

void VpnController::handleServersReply(QDBusPendingCallWatcher *watcher)
{
    const QDBusPendingReply<QString> reply = *watcher;
    const QString requestedCountry = watcher->property("countryCode").toString();
    watcher->deleteLater();
    setLocationsBusy(false);
    if (requestedCountry != m_currentServerCountry) {
        dispatchPendingLocationRefreshes();
        return;
    }
    if (reply.isError()) {
        m_message = tr("Unable to load servers");
        emit snapshotChanged();
        dispatchPendingLocationRefreshes();
        return;
    }
    QString errorMessage;
    if (!m_serverModel->resetFromJson(reply.value(), &errorMessage)) {
        m_message = errorMessage;
        emit snapshotChanged();
    }
    dispatchPendingLocationRefreshes();
}

void VpnController::handleServerLoadsReply(QDBusPendingCallWatcher *watcher)
{
    const QDBusPendingReply<QString> reply = *watcher;
    const QString requestedCountry = watcher->property("countryCode").toString();
    watcher->deleteLater();
    setLocationsBusy(false);
    if (requestedCountry != m_currentServerCountry) {
        dispatchPendingLocationRefreshes();
        return;
    }
    if (reply.isError()) {
        m_message = tr("Unable to update server loads");
        emit snapshotChanged();
        dispatchPendingLocationRefreshes();
        return;
    }
    QString errorMessage;
    if (!m_serverModel->updateLoadsFromJson(reply.value(), &errorMessage)) {
        m_message = errorMessage;
        emit snapshotChanged();
    }
    dispatchPendingLocationRefreshes();
}
