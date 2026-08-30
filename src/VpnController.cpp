// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#include "VpnController.h"

#include "BackendCallPolicy.h"
#include "BackendIdentity.h"
#include "DbusContract.h"
#include "InstalledApplicationModel.h"
#include "CustomDnsModel.h"
#include "LocationModels.h"
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
#include <QJsonObject>
#include <QTimer>
#include <algorithm>

#ifndef PROTON_VPN_KDE_SUPPORT_REPORT_SUBMISSION_ENABLED
#define PROTON_VPN_KDE_SUPPORT_REPORT_SUBMISSION_ENABLED 0
#endif
#ifndef PROTON_VPN_KDE_CRASH_REPORT_SUBMISSION_ENABLED
#define PROTON_VPN_KDE_CRASH_REPORT_SUBMISSION_ENABLED 0
#endif

namespace
{
namespace BackendDbus = ProtonVpnKde::DBusContract::Backend;
}

VpnController::VpnController(QObject *parent)
    : VpnController(parent, true)
{
}

VpnController::VpnController(QObject *parent, bool discoverApplications)
    : VpnConnectionController(parent)
    , m_serviceWatcher(new QDBusServiceWatcher(
          QString::fromLatin1(BackendDbus::serviceName),
          QDBusConnection::sessionBus(),
          QDBusServiceWatcher::WatchForRegistration
              | QDBusServiceWatcher::WatchForUnregistration,
          this))
    , m_clientRegistrationRetryTimer(new QTimer(this))
    , m_countryModel(new CountryModel(this))
    , m_locationSearchModel(new LocationSearchModel(this))
    , m_serverGroupModel(new ServerGroupModel(this))
    , m_serverModel(new ServerModel(this))
    , m_installedApplicationModel(
          new InstalledApplicationModel(this, discoverApplications))
    , m_settings(new VpnSettingsModel(this))
    , m_splitTunneling(new SplitTunnelingModel(this))
    , m_customDns(new CustomDnsModel(this))
    , m_countryFilterModel(new LocationFilterProxyModel(this))
    , m_serverGroupFilterModel(new LocationFilterProxyModel(this))
    , m_serverFilterModel(new LocationFilterProxyModel(this))
    , m_applicationFilterModel(new LocationFilterProxyModel(this))
{
    m_clientRegistrationRetryTimer->setSingleShot(true);
    connect(m_clientRegistrationRetryTimer, &QTimer::timeout,
            this, &VpnController::registerClient);
    m_countryFilterModel->setSourceModel(m_countryModel);
    m_countryFilterModel->setSearchRoles({CountryModel::CodeRole, CountryModel::NameRole});
    m_serverGroupFilterModel->setSourceModel(m_serverGroupModel);
    m_serverGroupFilterModel->setSearchRoles({ServerGroupModel::NameRole});
    m_serverGroupFilterModel->setFeatureRoles({
        {QStringLiteral("p2p"), ServerGroupModel::P2pRole},
        {QStringLiteral("streaming"), ServerGroupModel::StreamingRole},
        {QStringLiteral("tor"), ServerGroupModel::TorRole},
        {QStringLiteral("secure-core"), ServerGroupModel::SecureCoreRole},
    });
    m_serverFilterModel->setSourceModel(m_serverModel);
    m_serverFilterModel->setSearchRoles({ServerModel::NameRole, ServerModel::LocationRole});
    m_serverFilterModel->setFeatureRoles({
        {QStringLiteral("p2p"), ServerModel::P2pRole},
        {QStringLiteral("streaming"), ServerModel::StreamingRole},
        {QStringLiteral("tor"), ServerModel::TorRole},
        {QStringLiteral("secure-core"), ServerModel::SecureCoreRole},
    });
    m_serverFilterModel->setAvailabilityRoles(
        ServerModel::AccessibleRole, ServerModel::UnderMaintenanceRole);
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

    auto *interface = QDBusConnection::sessionBus().interface();
    if (interface && interface->isServiceRegistered(
            QString::fromLatin1(BackendDbus::serviceName))) {
        onServiceRegistered(QString::fromLatin1(BackendDbus::serviceName));
    } else if (interface) {
        // Activation itself carries no application data. No Backend1 method is
        // called until the resulting unique owner has been authenticated.
        static_cast<void>(interface->startService(
            QString::fromLatin1(BackendDbus::serviceName)));
    }
}

VpnController::~VpnController()
{
    unregisterClient();
}

bool VpnController::backendAvailable() const { return m_backendAvailable; }
bool VpnController::ready() const { return m_ready; }
bool VpnController::startupCompatible() const { return m_startupCompatible; }
bool VpnController::loggedIn() const { return m_loggedIn; }
QString VpnController::authState() const { return m_authState; }
QString VpnController::accountName() const { return m_accountName; }
QString VpnController::planTitle() const { return m_planTitle; }
int VpnController::userTier() const { return m_userTier; }
int VpnController::maxConnections() const { return m_maxConnections; }
bool VpnController::fido2Available() const { return m_fido2Available; }
int VpnController::killSwitch() const { return m_killSwitch; }
bool VpnController::busy() const { return m_busy; }
bool VpnController::locationsBusy() const
{
    return m_locationsBusy || m_countryRefreshPending
        || m_serverGroupRefreshPending || m_serverRefreshPending;
}
bool VpnController::locationSearchBusy() const { return m_locationSearchBusy; }
bool VpnController::npsSurveyAvailable() const { return m_npsSurveyAvailable; }
bool VpnController::supportReportSubmissionEnabled() const
{
    return PROTON_VPN_KDE_SUPPORT_REPORT_SUBMISSION_ENABLED != 0;
}
bool VpnController::crashReportSubmissionEnabled() const
{
    return PROTON_VPN_KDE_CRASH_REPORT_SUBMISSION_ENABLED != 0;
}
QString VpnController::state() const { return m_state; }
QString VpnController::errorCode() const { return m_errorCode; }
QString VpnController::serverName() const { return m_serverName; }
QString VpnController::serverLocation() const { return m_serverLocation; }
QString VpnController::exitCountry() const { return m_exitCountry; }
QString VpnController::entryCountry() const { return m_entryCountry; }
int VpnController::forwardedPort() const { return m_forwardedPort; }
bool VpnController::secureCore() const { return m_secureCore; }
bool VpnController::tor() const { return m_tor; }
bool VpnController::p2p() const { return m_p2p; }
bool VpnController::streaming() const { return m_streaming; }
bool VpnController::smartRouting() const { return m_smartRouting; }
bool VpnController::packetCaptureActive() const { return m_packetCaptureActive; }
bool VpnController::coreMemoryOptimized() const { return m_coreMemoryOptimized; }
QString VpnController::coreVersion() const { return m_coreVersion; }
QString VpnController::message() const { return m_message; }

QString VpnController::primaryActionText() const
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

bool VpnController::primaryActionEnabled() const
{
    return m_backendAvailable && m_ready && m_loggedIn
        && (!m_busy || m_state == QStringLiteral("connecting"));
}

QAbstractItemModel *VpnController::countryModel() const { return m_countryFilterModel; }
QAbstractItemModel *VpnController::locationSearchModel() const
{
    return m_locationSearchModel;
}
QAbstractItemModel *VpnController::serverGroupModel() const
{
    return m_serverGroupFilterModel;
}
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
    if (m_backendDestination.isEmpty()) {
        return;
    }
    QDBusMessage message = QDBusMessage::createMethodCall(
        m_backendDestination,
        QString::fromLatin1(BackendDbus::objectPath),
        QString::fromLatin1(BackendDbus::interfaceName),
        QString::fromLatin1(BackendDbus::Method::getSnapshot));
    auto *watcher = new QDBusPendingCallWatcher(
        QDBusConnection::sessionBus().asyncCall(message, 5000), this);
    connect(watcher, &QDBusPendingCallWatcher::finished,
            this, &VpnController::handleSnapshotReply);
}

void VpnController::submitNpsSurvey(int score, const QString &comments)
{
    if (!m_npsSurveyAvailable || score < 0 || score > 10) {
        return;
    }
    m_npsSurveyAvailable = false;
    emit npsSurveyChanged();
    callSecretOperation(
        QString::fromLatin1(BackendDbus::Method::submitNpsSurvey),
        {{QStringLiteral("score"), QString::number(score)},
         {QStringLiteral("comments"), comments.left(250)},
         {QStringLiteral("responseType"), QStringLiteral("submit")}},
        false);
}

void VpnController::dismissNpsSurvey()
{
    if (!m_npsSurveyAvailable) {
        return;
    }
    m_npsSurveyAvailable = false;
    emit npsSurveyChanged();
    callSecretOperation(
        QString::fromLatin1(BackendDbus::Method::submitNpsSurvey),
        {{QStringLiteral("score"), QStringLiteral("0")},
         {QStringLiteral("comments"), QString()},
         {QStringLiteral("responseType"), QStringLiteral("dismiss")}},
        false);
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

void VpnController::loadPendingNpsSurvey()
{
    if (m_npsSurveyChecked || !m_backendAvailable || !m_ready || !m_loggedIn) {
        return;
    }
    m_npsSurveyChecked = true;
    QDBusMessage message = QDBusMessage::createMethodCall(
        m_backendDestination,
        QString::fromLatin1(BackendDbus::objectPath),
        QString::fromLatin1(BackendDbus::interfaceName),
        QString::fromLatin1(BackendDbus::Method::getPendingNpsSurvey));
    auto *watcher = new QDBusPendingCallWatcher(
        QDBusConnection::sessionBus().asyncCall(message, 10000), this);
    connect(watcher, &QDBusPendingCallWatcher::finished,
            this, &VpnController::handlePendingNpsSurveyReply);
}

void VpnController::handlePendingNpsSurveyReply(
    QDBusPendingCallWatcher *watcher)
{
    const QDBusPendingReply<QString> reply = *watcher;
    watcher->deleteLater();
    if (reply.isError() || !m_loggedIn) {
        return;
    }
    QJsonParseError parseError;
    const QJsonDocument document = QJsonDocument::fromJson(
        reply.value().toUtf8(), &parseError);
    if (parseError.error != QJsonParseError::NoError || !document.isObject()
        || document.object().value(QStringLiteral("schemaVersion")).toInt() != 1) {
        return;
    }
    const bool available = document.object()
                               .value(QStringLiteral("available")).toBool();
    if (m_npsSurveyAvailable != available) {
        m_npsSurveyAvailable = available;
        emit npsSurveyChanged();
    }
}
