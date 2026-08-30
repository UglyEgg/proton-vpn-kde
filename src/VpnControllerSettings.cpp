// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#include "VpnController.h"

#include "CustomDnsModel.h"
#include "DbusContract.h"
#include "InstalledApplicationModel.h"
#include "SplitTunnelingModel.h"
#include "VpnSettingsModel.h"

#include <QDBusConnection>
#include <QDBusError>
#include <QDBusMessage>
#include <QDBusPendingCallWatcher>
#include <QDBusPendingReply>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QLatin1StringView>
#include <QMetaType>
#include <QSet>

namespace
{
namespace BackendDbus = ProtonVpnKde::DBusContract::Backend;
}

void VpnController::loadSettings()
{
    if (!m_backendAvailable || !m_ready || !m_loggedIn || m_settings->busy()) {
        return;
    }
    m_settings->setBusy(true);
    m_settings->setMessage({});
    QDBusMessage message = QDBusMessage::createMethodCall(
        m_backendDestination,
        QString::fromLatin1(BackendDbus::objectPath),
        QString::fromLatin1(BackendDbus::interfaceName),
        QString::fromLatin1(BackendDbus::Method::getSettings));
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
    if (name == QStringLiteral("anonymousCrashReports")
        && !crashReportSubmissionEnabled()) {
        m_settings->setMessage(
            tr("Anonymous crash reporting is disabled in this unofficial community build"));
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
        m_backendDestination,
        QString::fromLatin1(BackendDbus::objectPath),
        QString::fromLatin1(BackendDbus::interfaceName),
        QString::fromLatin1(BackendDbus::Method::updateSettings));
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
        m_backendDestination,
        QString::fromLatin1(BackendDbus::objectPath),
        QString::fromLatin1(BackendDbus::interfaceName),
        QString::fromLatin1(BackendDbus::Method::getSplitTunneling));
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
               || name == QStringLiteral("includeAppPaths")
               || name == QStringLiteral("excludeIpRanges")
               || name == QStringLiteral("includeIpRanges")) {
        const QStringList paths = value.toStringList();
        if (paths.size() > 256) {
            m_splitTunneling->setMessage(
                tr("Too many split-tunneling rules are selected"));
            return;
        }
        const bool ipRanges = name.endsWith(QStringLiteral("IpRanges"));
        QJsonArray pathArray;
        for (const QString &path : paths) {
            if (path.isEmpty() || path.size() > (ipRanges ? 64 : 4096)
                || path.contains(QLatin1Char('\n'))
                || path.contains(QLatin1Char('\r'))) {
                m_splitTunneling->setMessage(
                    ipRanges
                        ? tr("A split-tunneling IP range is invalid")
                        : tr("A split-tunneling application path is invalid"));
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
        m_backendDestination,
        QString::fromLatin1(BackendDbus::objectPath),
        QString::fromLatin1(BackendDbus::interfaceName),
        QString::fromLatin1(BackendDbus::Method::updateSplitTunneling));
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

void VpnController::addSplitTunnelingIpRange(const QString &ipRange)
{
    if (!m_splitTunneling->loaded() || m_splitTunneling->busy()) {
        return;
    }
    const QString normalized = ipRange.trimmed();
    if (normalized.isEmpty() || normalized.size() > 64
        || normalized.contains(QLatin1Char('\n'))
        || normalized.contains(QLatin1Char('\r'))) {
        m_splitTunneling->setMessage(
            tr("Enter a valid IPv4 or IPv6 address or CIDR range"));
        return;
    }
    QStringList ranges = m_splitTunneling->selectedIpRanges();
    if (ranges.contains(normalized)) {
        return;
    }
    ranges.append(normalized);
    const QString field = m_splitTunneling->mode() == QStringLiteral("include")
        ? QStringLiteral("includeIpRanges")
        : QStringLiteral("excludeIpRanges");
    updateSplitTunneling(field, ranges);
}

void VpnController::removeSplitTunnelingIpRange(const QString &ipRange)
{
    if (!m_splitTunneling->loaded() || m_splitTunneling->busy()) {
        return;
    }
    QStringList ranges = m_splitTunneling->selectedIpRanges();
    if (!ranges.removeOne(ipRange)) {
        return;
    }
    const QString field = m_splitTunneling->mode() == QStringLiteral("include")
        ? QStringLiteral("includeIpRanges")
        : QStringLiteral("excludeIpRanges");
    updateSplitTunneling(field, ranges);
}

void VpnController::clearSplitTunnelingIpRanges()
{
    if (!m_splitTunneling->loaded() || m_splitTunneling->busy()) {
        return;
    }
    const QString field = m_splitTunneling->mode() == QStringLiteral("include")
        ? QStringLiteral("includeIpRanges")
        : QStringLiteral("excludeIpRanges");
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
        m_backendDestination,
        QString::fromLatin1(BackendDbus::objectPath),
        QString::fromLatin1(BackendDbus::interfaceName),
        QString::fromLatin1(BackendDbus::Method::getCustomDns));
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
        m_backendDestination,
        QString::fromLatin1(BackendDbus::objectPath),
        QString::fromLatin1(BackendDbus::interfaceName),
        QString::fromLatin1(BackendDbus::Method::updateCustomDns));
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

void VpnController::handleSettingsReply(QDBusPendingCallWatcher *watcher)
{
    const QDBusPendingReply<QString> reply = *watcher;
    watcher->deleteLater();
    m_settings->setBusy(false);
    if (reply.isError()) {
        if (reply.error().name()
            == QLatin1StringView(BackendDbus::Error::invalidSettings)) {
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
            == QLatin1StringView(
                BackendDbus::Error::invalidSplitTunneling)) {
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
            == QLatin1StringView(BackendDbus::Error::invalidCustomDns)) {
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
