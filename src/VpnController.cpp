#include "VpnController.h"

#include "InstalledApplicationModel.h"
#include "CustomDnsModel.h"
#include "LocationModels.h"
#include "SecretTransport.h"
#include "SplitTunnelingModel.h"
#include "VpnSettingsModel.h"

#include <QAbstractItemModel>
#include <QDBusConnection>
#include <QDBusConnectionInterface>
#include <QDBusError>
#include <QDBusMessage>
#include <QDBusPendingCallWatcher>
#include <QDBusPendingReply>
#include <QDBusServiceWatcher>
#include <QJsonDocument>
#include <QJsonArray>
#include <QJsonObject>
#include <QMetaType>
#include <QSet>

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
    , m_installedApplicationModel(new InstalledApplicationModel(this))
    , m_settings(new VpnSettingsModel(this))
    , m_splitTunneling(new SplitTunnelingModel(this))
    , m_customDns(new CustomDnsModel(this))
    , m_countryFilterModel(new LocationFilterProxyModel(this))
    , m_serverFilterModel(new LocationFilterProxyModel(this))
    , m_applicationFilterModel(new LocationFilterProxyModel(this))
{
    m_countryFilterModel->setSourceModel(m_countryModel);
    m_countryFilterModel->setSearchRoles({CountryModel::CodeRole, CountryModel::NameRole});
    m_serverFilterModel->setSourceModel(m_serverModel);
    m_serverFilterModel->setSearchRoles({ServerModel::NameRole, ServerModel::LocationRole});
    m_serverFilterModel->sortByRole(ServerModel::LoadRole);
    m_applicationFilterModel->setSourceModel(m_installedApplicationModel);
    m_applicationFilterModel->setSearchRoles({
        InstalledApplicationModel::NameRole,
        InstalledApplicationModel::ExecutableRole,
        InstalledApplicationModel::CommentRole,
    });

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
    QDBusConnection::sessionBus().connect(
        QString::fromLatin1(kBackendService),
        QString::fromLatin1(kBackendPath),
        QString::fromLatin1(kBackendInterface),
        QStringLiteral("SettingsChanged"),
        this,
        SLOT(onSettingsChanged(QString)));
    QDBusConnection::sessionBus().connect(
        QString::fromLatin1(kBackendService),
        QString::fromLatin1(kBackendPath),
        QString::fromLatin1(kBackendInterface),
        QStringLiteral("SplitTunnelingChanged"),
        this,
        SLOT(onSplitTunnelingChanged(QString)));
    QDBusConnection::sessionBus().connect(
        QString::fromLatin1(kBackendService),
        QString::fromLatin1(kBackendPath),
        QString::fromLatin1(kBackendInterface),
        QStringLiteral("CustomDnsChanged"),
        this,
        SLOT(onCustomDnsChanged(QString)));

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
    return m_backendAvailable && m_ready && m_loggedIn
        && (!m_busy || m_state == QStringLiteral("connecting"));
}

QAbstractItemModel *VpnController::countryModel() const { return m_countryFilterModel; }
QAbstractItemModel *VpnController::serverModel() const { return m_serverFilterModel; }
QAbstractItemModel *VpnController::applicationModel() const
{
    return m_applicationFilterModel;
}
VpnSettingsModel *VpnController::settings() const { return m_settings; }
SplitTunnelingModel *VpnController::splitTunneling() const
{
    return m_splitTunneling;
}
CustomDnsModel *VpnController::customDns() const { return m_customDns; }

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
    if (m_state == QStringLiteral("connecting")) {
        callControlOperation(QStringLiteral("Disconnect"));
        return;
    }
    const bool shouldDisconnect = m_state == QStringLiteral("connected")
        || m_state == QStringLiteral("disconnecting");
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

void VpnController::setApplicationFilter(const QString &filterText)
{
    m_applicationFilterModel->setFilterText(filterText);
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

void VpnController::loadSettings()
{
    if (!m_backendAvailable || !m_ready || !m_loggedIn || m_settings->busy()) {
        return;
    }
    m_settings->setBusy(true);
    m_settings->setMessage({});
    QDBusMessage message = QDBusMessage::createMethodCall(
        QString::fromLatin1(kBackendService),
        QString::fromLatin1(kBackendPath),
        QString::fromLatin1(kBackendInterface),
        QStringLiteral("GetSettings"));
    auto *watcher = new QDBusPendingCallWatcher(
        QDBusConnection::sessionBus().asyncCall(message, 10000), this);
    connect(watcher, &QDBusPendingCallWatcher::finished,
            this, &VpnController::handleSettingsReply);
}

void VpnController::updateSetting(const QString &name, const QVariant &value)
{
    if (!m_backendAvailable || !m_ready || !m_loggedIn || m_settings->busy()) {
        return;
    }

    static const QSet<QString> booleanSettings{
        QStringLiteral("vpnAccelerator"),
        QStringLiteral("moderateNat"),
        QStringLiteral("portForwarding"),
        QStringLiteral("ipv6"),
        QStringLiteral("anonymousCrashReports"),
    };
    static const QSet<QString> modeSettings{
        QStringLiteral("killSwitch"),
        QStringLiteral("netShield"),
    };

    QJsonValue jsonValue;
    if (name == QStringLiteral("protocol")) {
        const QString protocol = value.toString();
        if (protocol.isEmpty()) {
            m_settings->setMessage(tr("Select a valid VPN protocol"));
            return;
        }
        jsonValue = protocol;
    } else if (booleanSettings.contains(name)) {
        if (value.metaType().id() != QMetaType::Bool) {
            m_settings->setMessage(tr("The setting value is invalid"));
            return;
        }
        jsonValue = value.toBool();
    } else if (modeSettings.contains(name)) {
        bool converted = false;
        const int mode = value.toInt(&converted);
        if (!converted || mode < 0 || mode > 2) {
            m_settings->setMessage(tr("The setting value is invalid"));
            return;
        }
        jsonValue = mode;
    } else {
        m_settings->setMessage(tr("That VPN setting is not supported"));
        return;
    }

    const QString patchJson = QString::fromUtf8(
        QJsonDocument(QJsonObject{{name, jsonValue}}).toJson(
            QJsonDocument::Compact));
    m_settings->setBusy(true);
    m_settings->setMessage({});
    QDBusMessage message = QDBusMessage::createMethodCall(
        QString::fromLatin1(kBackendService),
        QString::fromLatin1(kBackendPath),
        QString::fromLatin1(kBackendInterface),
        QStringLiteral("UpdateSettings"));
    message << patchJson;
    auto *watcher = new QDBusPendingCallWatcher(
        QDBusConnection::sessionBus().asyncCall(message, 30000), this);
    connect(watcher, &QDBusPendingCallWatcher::finished,
            this, &VpnController::handleSettingsReply);
}

void VpnController::loadSplitTunneling()
{
    if (!m_backendAvailable || !m_ready || !m_loggedIn
        || m_splitTunneling->busy()) {
        return;
    }
    m_splitTunneling->setBusy(true);
    m_splitTunneling->setMessage(QString{});
    QDBusMessage message = QDBusMessage::createMethodCall(
        QString::fromLatin1(kBackendService),
        QString::fromLatin1(kBackendPath),
        QString::fromLatin1(kBackendInterface),
        QStringLiteral("GetSplitTunneling"));
    auto *watcher = new QDBusPendingCallWatcher(
        QDBusConnection::sessionBus().asyncCall(message, 10000), this);
    connect(watcher, &QDBusPendingCallWatcher::finished,
            this, &VpnController::handleSplitTunnelingReply);
}

void VpnController::updateSplitTunneling(const QString &name,
                                         const QVariant &value)
{
    if (!m_backendAvailable || !m_ready || !m_loggedIn
        || !m_splitTunneling->loaded() || m_splitTunneling->busy()) {
        return;
    }

    QJsonValue jsonValue;
    if (name == QStringLiteral("enabled")) {
        if (value.metaType().id() != QMetaType::Bool) {
            m_splitTunneling->setMessage(tr("The split-tunneling value is invalid"));
            return;
        }
        jsonValue = value.toBool();
    } else if (name == QStringLiteral("mode")) {
        const QString mode = value.toString();
        if (mode != QStringLiteral("exclude")
            && mode != QStringLiteral("include")) {
            m_splitTunneling->setMessage(tr("Select a valid split-tunneling mode"));
            return;
        }
        jsonValue = mode;
    } else if (name == QStringLiteral("excludeAppPaths")
               || name == QStringLiteral("includeAppPaths")) {
        const QStringList paths = value.toStringList();
        if (paths.size() > 256) {
            m_splitTunneling->setMessage(
                tr("Too many split-tunneling applications are selected"));
            return;
        }
        QJsonArray pathArray;
        for (const QString &path : paths) {
            if (path.isEmpty() || path.size() > 4096
                || path.contains(QLatin1Char('\n'))
                || path.contains(QLatin1Char('\r'))) {
                m_splitTunneling->setMessage(
                    tr("A split-tunneling application path is invalid"));
                return;
            }
            pathArray.append(path);
        }
        jsonValue = pathArray;
    } else {
        m_splitTunneling->setMessage(
            tr("That split-tunneling setting is not supported"));
        return;
    }

    const QString patchJson = QString::fromUtf8(
        QJsonDocument(QJsonObject{{name, jsonValue}}).toJson(
            QJsonDocument::Compact));
    m_splitTunneling->setBusy(true);
    m_splitTunneling->setMessage(QString{});
    QDBusMessage message = QDBusMessage::createMethodCall(
        QString::fromLatin1(kBackendService),
        QString::fromLatin1(kBackendPath),
        QString::fromLatin1(kBackendInterface),
        QStringLiteral("UpdateSplitTunneling"));
    message << patchJson;
    auto *watcher = new QDBusPendingCallWatcher(
        QDBusConnection::sessionBus().asyncCall(message, 30000), this);
    connect(watcher, &QDBusPendingCallWatcher::finished,
            this, &VpnController::handleSplitTunnelingReply);
}

void VpnController::setSplitTunnelingApplication(
    const QString &executable, bool selected)
{
    if (!m_splitTunneling->loaded() || m_splitTunneling->busy()) {
        return;
    }
    if (selected
        && !InstalledApplicationModel::isSafeVpnApplicationChoice(executable)) {
        m_splitTunneling->setMessage(
            tr("The Proton VPN client cannot bypass its own tunnel"));
        return;
    }

    QStringList paths = m_splitTunneling->selectedAppPaths();
    const bool alreadySelected = paths.contains(executable);
    if (selected == alreadySelected) {
        return;
    }
    if (selected) {
        paths.append(executable);
    } else {
        paths.removeAll(executable);
    }
    const QString field = m_splitTunneling->mode() == QStringLiteral("include")
        ? QStringLiteral("includeAppPaths")
        : QStringLiteral("excludeAppPaths");
    updateSplitTunneling(field, paths);
}

void VpnController::clearSplitTunnelingApplications()
{
    if (!m_splitTunneling->loaded() || m_splitTunneling->busy()) {
        return;
    }
    const QString field = m_splitTunneling->mode() == QStringLiteral("include")
        ? QStringLiteral("includeAppPaths")
        : QStringLiteral("excludeAppPaths");
    updateSplitTunneling(field, QStringList{});
}

void VpnController::loadCustomDns()
{
    if (!m_backendAvailable || !m_ready || !m_loggedIn
        || m_customDns->busy()) {
        return;
    }
    m_customDns->setBusy(true);
    m_customDns->setMessage(QString{});
    QDBusMessage message = QDBusMessage::createMethodCall(
        QString::fromLatin1(kBackendService),
        QString::fromLatin1(kBackendPath),
        QString::fromLatin1(kBackendInterface),
        QStringLiteral("GetCustomDns"));
    auto *watcher = new QDBusPendingCallWatcher(
        QDBusConnection::sessionBus().asyncCall(message, 10000), this);
    connect(watcher, &QDBusPendingCallWatcher::finished,
            this, &VpnController::handleCustomDnsReply);
}

void VpnController::updateCustomDns(const QString &name,
                                    const QVariant &value)
{
    if (!m_backendAvailable || !m_ready || !m_loggedIn
        || !m_customDns->loaded() || m_customDns->busy()) {
        return;
    }

    QJsonValue jsonValue;
    if (name == QStringLiteral("enabled")) {
        if (value.metaType().id() != QMetaType::Bool) {
            m_customDns->setMessage(tr("The custom-DNS value is invalid"));
            return;
        }
        jsonValue = value.toBool();
    } else if (name == QStringLiteral("servers")) {
        const QVariantList servers = value.toList();
        if (servers.size() > 256) {
            m_customDns->setMessage(tr("Too many custom DNS servers were provided"));
            return;
        }
        QJsonArray serverArray;
        for (const QVariant &serverValue : servers) {
            const QVariantMap server = serverValue.toMap();
            const QString address = CustomDnsModel::normalizeServerAddress(
                server.value(QStringLiteral("address")).toString());
            if (address.isEmpty()
                || server.value(QStringLiteral("enabled")).metaType().id()
                    != QMetaType::Bool) {
                m_customDns->setMessage(
                    tr("Enter a valid IPv4 or IPv6 DNS server address"));
                return;
            }
            serverArray.append(QJsonObject{
                {QStringLiteral("address"), address},
                {QStringLiteral("enabled"),
                 server.value(QStringLiteral("enabled")).toBool()},
            });
        }
        jsonValue = serverArray;
    } else {
        m_customDns->setMessage(tr("That custom-DNS setting is not supported"));
        return;
    }

    const QString patchJson = QString::fromUtf8(
        QJsonDocument(QJsonObject{{name, jsonValue}}).toJson(
            QJsonDocument::Compact));
    m_customDns->setBusy(true);
    m_customDns->setMessage(QString{});
    QDBusMessage message = QDBusMessage::createMethodCall(
        QString::fromLatin1(kBackendService),
        QString::fromLatin1(kBackendPath),
        QString::fromLatin1(kBackendInterface),
        QStringLiteral("UpdateCustomDns"));
    message << patchJson;
    auto *watcher = new QDBusPendingCallWatcher(
        QDBusConnection::sessionBus().asyncCall(message, 30000), this);
    watcher->setProperty("changedWhileConnected",
                         m_state == QStringLiteral("connected")
                             || m_state == QStringLiteral("connecting"));
    connect(watcher, &QDBusPendingCallWatcher::finished,
            this, &VpnController::handleCustomDnsReply);
}

void VpnController::addCustomDnsServer(const QString &address)
{
    const QString normalized = CustomDnsModel::normalizeServerAddress(address);
    if (normalized.isEmpty()) {
        m_customDns->setMessage(
            tr("Enter a valid IPv4 or IPv6 DNS server address"));
        return;
    }
    if (m_customDns->containsServer(normalized)) {
        m_customDns->setMessage(tr("That custom DNS server is already listed"));
        return;
    }
    QVariantList servers = m_customDns->servers();
    servers.append(QVariantMap{
        {QStringLiteral("address"), normalized},
        {QStringLiteral("enabled"), true},
    });
    updateCustomDns(QStringLiteral("servers"), servers);
}

void VpnController::removeCustomDnsServer(const QString &address)
{
    const QString normalized = CustomDnsModel::normalizeServerAddress(address);
    if (normalized.isEmpty()) {
        return;
    }
    QVariantList servers;
    for (const QVariant &serverValue : m_customDns->servers()) {
        const QVariantMap server = serverValue.toMap();
        if (CustomDnsModel::normalizeServerAddress(
                server.value(QStringLiteral("address")).toString())
            != normalized) {
            servers.append(server);
        }
    }
    if (servers.size() == m_customDns->serverCount()) {
        return;
    }
    updateCustomDns(QStringLiteral("servers"), servers);
}

QString VpnController::applicationName(const QString &executable) const
{
    return m_installedApplicationModel->nameForExecutable(executable);
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
    setLocationsBusy(false);
    m_state = QStringLiteral("unavailable");
    m_message = tr("The Proton backend service stopped");
    m_countryModel->clear();
    m_serverModel->clear();
    m_countryRefreshPending = false;
    m_serverRefreshPending = false;
    m_serverLoadsRefreshPending = false;
    m_currentServerCountry.clear();
    m_settings->reset(tr("The Proton backend service stopped"));
    m_splitTunneling->reset(tr("The Proton backend service stopped"));
    m_customDns->reset(tr("The Proton backend service stopped"));
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
    const QString previousState = m_state;
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
    if (m_state != QStringLiteral("connected")) {
        m_customDns->setRestartRequired(false);
    }
    m_serverName = snapshot.value(QStringLiteral("serverName")).toString();
    m_message = snapshot.value(QStringLiteral("message")).toString();
    if (wasLoggedIn && !m_loggedIn) {
        m_countryModel->clear();
        m_serverModel->clear();
        m_countryRefreshPending = false;
        m_serverRefreshPending = false;
        m_serverLoadsRefreshPending = false;
        m_currentServerCountry.clear();
        m_settings->reset();
        m_splitTunneling->reset();
        m_customDns->reset();
    }
    emit snapshotChanged();
    if (m_loggedIn && m_countryModel->rowCount() == 0 && !m_locationsBusy) {
        loadCountries();
    }
    if (m_loggedIn
        && (!m_settings->loaded() || previousState != m_state)
        && !m_settings->busy()) {
        loadSettings();
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

void VpnController::handleSettingsReply(QDBusPendingCallWatcher *watcher)
{
    const QDBusPendingReply<QString> reply = *watcher;
    watcher->deleteLater();
    m_settings->setBusy(false);
    if (reply.isError()) {
        if (reply.error().name()
            == QStringLiteral("proton.vpn.app.kde.Error.InvalidSettings")) {
            QString message = reply.error().message().trimmed();
            if (message.isEmpty() || message.size() > 256
                || message.contains(QLatin1Char('\n'))) {
                message = tr("The VPN setting could not be changed");
            }
            m_settings->setMessage(message);
        } else {
            m_settings->setMessage(tr("Unable to save VPN settings"));
        }
        return;
    }
    QString errorMessage;
    if (!m_settings->applyJson(reply.value(), &errorMessage)) {
        m_settings->setMessage(errorMessage);
    }
}

void VpnController::handleSplitTunnelingReply(
    QDBusPendingCallWatcher *watcher)
{
    const QDBusPendingReply<QString> reply = *watcher;
    watcher->deleteLater();
    m_splitTunneling->setBusy(false);
    if (reply.isError()) {
        if (reply.error().name()
            == QStringLiteral(
                "proton.vpn.app.kde.Error.InvalidSplitTunneling")) {
            QString message = reply.error().message().trimmed();
            if (message.isEmpty() || message.size() > 256
                || message.contains(QLatin1Char('\n'))) {
                message = tr("The split-tunneling setting could not be changed");
            }
            m_splitTunneling->setMessage(message);
        } else {
            m_splitTunneling->setMessage(
                tr("Unable to save split-tunneling settings"));
        }
        return;
    }
    QString errorMessage;
    if (!m_splitTunneling->applyJson(reply.value(), &errorMessage)) {
        m_splitTunneling->setMessage(errorMessage);
    }
}

void VpnController::handleCustomDnsReply(QDBusPendingCallWatcher *watcher)
{
    const bool changedWhileConnected = watcher->property(
        "changedWhileConnected").toBool();
    const QDBusPendingReply<QString> reply = *watcher;
    watcher->deleteLater();
    m_customDns->setBusy(false);
    if (reply.isError()) {
        if (reply.error().name()
            == QStringLiteral("proton.vpn.app.kde.Error.InvalidCustomDns")) {
            QString message = reply.error().message().trimmed();
            if (message.isEmpty() || message.size() > 256
                || message.contains(QLatin1Char('\n'))) {
                message = tr("The custom-DNS setting could not be changed");
            }
            m_customDns->setMessage(message);
        } else {
            m_customDns->setMessage(tr("Unable to save custom-DNS settings"));
        }
        return;
    }
    QString errorMessage;
    if (!m_customDns->applyJson(reply.value(), &errorMessage)) {
        m_customDns->setMessage(errorMessage);
        return;
    }
    if (changedWhileConnected) {
        m_customDns->setRestartRequired(true);
    }
}
