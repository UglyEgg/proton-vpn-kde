// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#include "VpnController.h"

#include "CustomDnsModel.h"
#include "DbusContract.h"
#include "InstalledApplicationModel.h"
#include "LocationModels.h"
#include "SplitTunnelingModel.h"
#include "VpnSettingsModel.h"

#include <QAbstractItemModel>
#include <QDBusConnection>
#include <QDBusConnectionInterface>
#include <QDBusMessage>
#include <QDBusPendingCallWatcher>
#include <QDBusPendingReply>
#include <QDBusServiceWatcher>
#include <QJsonDocument>
#include <QJsonObject>
#include <QTimer>

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
