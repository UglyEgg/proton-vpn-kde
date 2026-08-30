// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#include "VpnController.h"

#include "DbusContract.h"
#include "LocationModels.h"

#include <QDBusConnection>
#include <QDBusMessage>
#include <QDBusPendingCallWatcher>
#include <QDBusPendingReply>
#include <QTimer>

namespace
{
namespace BackendDbus = ProtonVpnKde::DBusContract::Backend;
}

void VpnController::loadCountries()
{
    if (!m_backendAvailable || !m_ready || !m_loggedIn) {
        if (!m_countryRefreshPending) {
            m_countryRefreshPending = true;
            emit locationsChanged();
        }
        return;
    }
    if (m_locationsBusy) {
        m_countryRefreshPending = true;
        return;
    }
    m_countryRefreshPending = false;
    setLocationsBusy(true);
    QDBusMessage message = QDBusMessage::createMethodCall(
        m_backendDestination,
        QString::fromLatin1(BackendDbus::objectPath),
        QString::fromLatin1(BackendDbus::interfaceName),
        QString::fromLatin1(BackendDbus::Method::getCountries));
    auto *watcher = new QDBusPendingCallWatcher(
        QDBusConnection::sessionBus().asyncCall(message, 30000), this);
    connect(watcher, &QDBusPendingCallWatcher::finished,
            this, &VpnController::handleCountriesReply);
}

void VpnController::searchLocations(const QString &query)
{
    const QString normalizedQuery = query.simplified();
    m_locationSearchQuery = normalizedQuery;
    const quint64 generation = ++m_locationSearchGeneration;
    if (normalizedQuery.isEmpty()) {
        m_locationSearchBusy = false;
        m_locationSearchModel->clear();
        emit locationsChanged();
        return;
    }

    QString errorMessage;
    m_locationSearchModel->resetFromJson(
        QStringLiteral(R"json({"schemaVersion":1,"results":[]})json"),
        *m_countryModel, normalizedQuery, &errorMessage);
    if (!m_backendAvailable || !m_ready || !m_loggedIn) {
        m_locationSearchBusy = false;
        emit locationsChanged();
        return;
    }

    m_locationSearchBusy = true;
    emit locationsChanged();
    QDBusMessage message = QDBusMessage::createMethodCall(
        m_backendDestination,
        QString::fromLatin1(BackendDbus::objectPath),
        QString::fromLatin1(BackendDbus::interfaceName),
        QString::fromLatin1(BackendDbus::Method::searchLocations));
    message << normalizedQuery;
    auto *watcher = new QDBusPendingCallWatcher(
        QDBusConnection::sessionBus().asyncCall(message, 30000), this);
    watcher->setProperty("query", normalizedQuery);
    watcher->setProperty("generation", QVariant::fromValue(generation));
    connect(watcher, &QDBusPendingCallWatcher::finished,
            this, &VpnController::handleLocationSearchReply);
}

void VpnController::clearLocationSearch()
{
    searchLocations({});
}

void VpnController::loadServerGroups(const QString &countryCode)
{
    const QString normalizedCode = countryCode.trimmed().toUpper();
    if (normalizedCode.size() != 2) {
        return;
    }
    const bool countryChanged = m_currentServerCountry != normalizedCode;
    m_currentServerCountry = normalizedCode;
    if (countryChanged) {
        m_serverGroupModel->clear();
        m_serverModel->clear();
        m_currentServerGroupKind.clear();
        m_currentServerGroupName.clear();
    }
    if (!m_backendAvailable || !m_ready || !m_loggedIn) {
        if (!m_serverGroupRefreshPending) {
            m_serverGroupRefreshPending = true;
            emit locationsChanged();
        }
        return;
    }
    if (m_locationsBusy) {
        m_serverGroupRefreshPending = true;
        return;
    }
    m_serverGroupRefreshPending = false;
    setLocationsBusy(true);
    QDBusMessage message = QDBusMessage::createMethodCall(
        m_backendDestination,
        QString::fromLatin1(BackendDbus::objectPath),
        QString::fromLatin1(BackendDbus::interfaceName),
        QString::fromLatin1(BackendDbus::Method::getServerGroups));
    message << normalizedCode;
    auto *watcher = new QDBusPendingCallWatcher(
        QDBusConnection::sessionBus().asyncCall(message, 30000), this);
    watcher->setProperty("countryCode", normalizedCode);
    connect(watcher, &QDBusPendingCallWatcher::finished,
            this, &VpnController::handleServerGroupsReply);
}

void VpnController::loadGroupServers(const QString &countryCode,
                                     const QString &groupKind,
                                     const QString &groupName)
{
    const QString normalizedCode = countryCode.trimmed().toUpper();
    const QString normalizedKind = groupKind.trimmed();
    const QString normalizedName = groupName.trimmed();
    if (normalizedCode.size() != 2
        || (normalizedKind != QStringLiteral("location")
            && normalizedKind != QStringLiteral("secure-core"))
        || normalizedName.isEmpty()) {
        return;
    }
    const bool groupChanged = m_currentServerCountry != normalizedCode
        || m_currentServerGroupKind != normalizedKind
        || m_currentServerGroupName != normalizedName;
    m_currentServerCountry = normalizedCode;
    m_currentServerGroupKind = normalizedKind;
    m_currentServerGroupName = normalizedName;
    const quint64 requestGeneration = ++m_serverRequestGeneration;
    if (groupChanged) {
        m_serverModel->clear();
    }
    if (!m_backendAvailable || !m_ready || !m_loggedIn) {
        if (!m_serverRefreshPending) {
            m_serverRefreshPending = true;
            emit locationsChanged();
        }
        return;
    }
    if (m_locationsBusy) {
        m_serverRefreshPending = true;
        return;
    }
    m_serverRefreshPending = false;
    setLocationsBusy(true);
    requestGroupServers(normalizedCode, normalizedKind, normalizedName,
                        requestGeneration, 0);
}

void VpnController::requestGroupServers(const QString &countryCode,
                                        const QString &groupKind,
                                        const QString &groupName,
                                        quint64 requestGeneration,
                                        int retryCount)
{
    QDBusMessage message = QDBusMessage::createMethodCall(
        m_backendDestination,
        QString::fromLatin1(BackendDbus::objectPath),
        QString::fromLatin1(BackendDbus::interfaceName),
        QString::fromLatin1(BackendDbus::Method::getGroupServers));
    message << countryCode << groupKind << groupName;
    auto *watcher = new QDBusPendingCallWatcher(
        QDBusConnection::sessionBus().asyncCall(message, 30000), this);
    watcher->setProperty("countryCode", countryCode);
    watcher->setProperty("groupKind", groupKind);
    watcher->setProperty("groupName", groupName);
    watcher->setProperty("requestGeneration",
                         QVariant::fromValue(requestGeneration));
    watcher->setProperty("retryCount", retryCount);
    connect(watcher, &QDBusPendingCallWatcher::finished,
            this, &VpnController::handleServersReply);
}

bool VpnController::scheduleGroupServerRetry(const QString &countryCode,
                                             const QString &groupKind,
                                             const QString &groupName,
                                             quint64 requestGeneration,
                                             int retryCount)
{
    // Proton Core can replace its server-list snapshot between the group and
    // exact-server reads. Retry that short consistency window locally, but keep
    // the bound small so a genuinely removed group still fails promptly.
    if (retryCount >= 2) {
        return false;
    }
    const quint64 backendGeneration = m_backendGeneration;
    QTimer::singleShot(150 * (retryCount + 1), this,
        [this, countryCode, groupKind, groupName, requestGeneration,
         retryCount, backendGeneration] {
            if (backendGeneration != m_backendGeneration
                || requestGeneration != m_serverRequestGeneration
                || countryCode != m_currentServerCountry
                || groupKind != m_currentServerGroupKind
                || groupName != m_currentServerGroupName
                || !m_backendAvailable || !m_ready || !m_loggedIn) {
                setLocationsBusy(false);
                dispatchPendingLocationRefreshes();
                return;
            }
            requestGroupServers(countryCode, groupKind, groupName,
                                requestGeneration, retryCount + 1);
        });
    return true;
}

void VpnController::clearServerContext()
{
    const bool wasBusy = locationsBusy();
    m_currentServerCountry.clear();
    m_currentServerGroupKind.clear();
    m_currentServerGroupName.clear();
    m_serverGroupRefreshPending = false;
    m_serverRefreshPending = false;
    m_serverLoadsRefreshPending = false;
    ++m_serverRequestGeneration;
    m_serverGroupModel->clear();
    m_serverModel->clear();
    if (wasBusy != locationsBusy()) {
        emit locationsChanged();
    }
}

void VpnController::clearGroupServerContext()
{
    const bool wasBusy = locationsBusy();
    m_currentServerGroupKind.clear();
    m_currentServerGroupName.clear();
    m_serverRefreshPending = false;
    m_serverLoadsRefreshPending = false;
    ++m_serverRequestGeneration;
    m_serverModel->clear();
    if (wasBusy != locationsBusy()) {
        emit locationsChanged();
    }
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

void VpnController::setServerGroupFeatureFilter(const QStringList &features)
{
    m_serverGroupFilterModel->setRequiredFeatures(features);
}

void VpnController::setServerFeatureFilter(const QStringList &features)
{
    m_serverFilterModel->setRequiredFeatures(features);
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
        m_backendDestination,
        QString::fromLatin1(BackendDbus::objectPath),
        QString::fromLatin1(BackendDbus::interfaceName),
        QString::fromLatin1(BackendDbus::Method::getServerLoads));
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
    // Honor the deepest page first. A country or load refresh that was already
    // in flight must not strand a newer exact-server request behind obsolete
    // upper-level work while the user drills through the browser.
    if (m_serverRefreshPending && !m_currentServerCountry.isEmpty()
               && !m_currentServerGroupKind.isEmpty()
               && !m_currentServerGroupName.isEmpty()) {
        loadGroupServers(m_currentServerCountry,
                         m_currentServerGroupKind,
                         m_currentServerGroupName);
    } else if (m_serverGroupRefreshPending
               && !m_currentServerCountry.isEmpty()) {
        loadServerGroups(m_currentServerCountry);
    } else if (m_countryRefreshPending) {
        loadCountries();
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
    if (!m_locationSearchQuery.isEmpty()) {
        searchLocations(m_locationSearchQuery);
    }
    dispatchPendingLocationRefreshes();
}
void VpnController::handleLocationSearchReply(QDBusPendingCallWatcher *watcher)
{
    const QDBusPendingReply<QString> reply = *watcher;
    const QString requestedQuery = watcher->property("query").toString();
    const quint64 generation = watcher->property("generation").toULongLong();
    watcher->deleteLater();
    if (generation != m_locationSearchGeneration
        || requestedQuery != m_locationSearchQuery) {
        return;
    }

    m_locationSearchBusy = false;
    if (reply.isError()) {
        m_message = tr("Unable to search locations and servers");
        emit snapshotChanged();
        emit locationsChanged();
        return;
    }
    QString errorMessage;
    if (!m_locationSearchModel->resetFromJson(
            reply.value(), *m_countryModel, requestedQuery, &errorMessage)) {
        m_message = errorMessage;
        emit snapshotChanged();
    }
    emit locationsChanged();
}

void VpnController::handleServerGroupsReply(QDBusPendingCallWatcher *watcher)
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
        m_message = tr("Unable to load locations");
        emit snapshotChanged();
        dispatchPendingLocationRefreshes();
        return;
    }
    QString errorMessage;
    if (!m_serverGroupModel->resetFromJson(reply.value(), &errorMessage)) {
        m_message = errorMessage;
        emit snapshotChanged();
    }
    dispatchPendingLocationRefreshes();
}

void VpnController::handleServersReply(QDBusPendingCallWatcher *watcher)
{
    const QDBusPendingReply<QString> reply = *watcher;
    const QString requestedCountry = watcher->property("countryCode").toString();
    const QString requestedKind = watcher->property("groupKind").toString();
    const QString requestedName = watcher->property("groupName").toString();
    const quint64 requestGeneration =
        watcher->property("requestGeneration").toULongLong();
    const int retryCount = watcher->property("retryCount").toInt();
    watcher->deleteLater();
    if (requestedCountry != m_currentServerCountry
        || requestedKind != m_currentServerGroupKind
        || requestedName != m_currentServerGroupName
        || requestGeneration != m_serverRequestGeneration) {
        setLocationsBusy(false);
        dispatchPendingLocationRefreshes();
        return;
    }
    if (reply.isError()) {
        if (scheduleGroupServerRetry(
                requestedCountry, requestedKind, requestedName,
                requestGeneration, retryCount)) {
            return;
        }
        setLocationsBusy(false);
        m_message = tr("Unable to load servers");
        emit snapshotChanged();
        dispatchPendingLocationRefreshes();
        return;
    }
    QString errorMessage;
    if (!m_serverModel->resetFromJson(reply.value(), &errorMessage)) {
        setLocationsBusy(false);
        m_message = errorMessage;
        emit snapshotChanged();
        dispatchPendingLocationRefreshes();
        return;
    }
    if (m_serverModel->rowCount() == 0
        && scheduleGroupServerRetry(
            requestedCountry, requestedKind, requestedName,
            requestGeneration, retryCount)) {
        return;
    }
    setLocationsBusy(false);
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
