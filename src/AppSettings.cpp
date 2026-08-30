#include "AppSettings.h"

#include <KConfigGroup>
#include <QDir>
#include <QUrl>
#include <algorithm>

namespace
{
constexpr auto kConfigFile = "proton-vpn-kderc";
constexpr auto kGeneralGroup = "General";
}

AppSettings::AppSettings(QObject *parent)
    : QObject(parent)
    , m_config(KSharedConfig::openConfig(QString::fromLatin1(kConfigFile)))
    , m_configWatcher(KConfigWatcher::create(m_config))
{
    reloadSettings();
    connect(m_configWatcher.data(), &KConfigWatcher::configChanged, this,
            [this](const KConfigGroup &group, const QByteArrayList &) {
                if (group.name() == QString::fromLatin1(kGeneralGroup)) {
                    reloadSettings();
                }
            });
}

bool AppSettings::notificationsEnabled() const { return m_notificationsEnabled; }
bool AppSettings::reconnectEnabled() const { return m_reconnectEnabled; }
bool AppSettings::startMinimized() const { return m_startMinimized; }
bool AppSettings::closeToTray() const { return m_closeToTray; }
QString AppSettings::autoConnectTarget() const { return m_autoConnectTarget; }
QString AppSettings::pinnedServersText() const
{
    return m_pinnedServers.join(QStringLiteral(", "));
}
QStringList AppSettings::pinnedServers() const { return m_pinnedServers; }
QString AppSettings::pinnedServerGroupsText() const
{
    QStringList labels;
    labels.reserve(m_pinnedServerGroups.size());
    for (const PinnedServerGroup &group : m_pinnedServerGroups) {
        labels.append(QStringLiteral("%1 — %2").arg(group.countryCode, group.name));
    }
    return labels.join(QStringLiteral(", "));
}
QVector<AppSettings::PinnedServerGroup> AppSettings::pinnedServerGroups() const
{
    return m_pinnedServerGroups;
}
QString AppSettings::packetCaptureDirectory() const
{
    return m_packetCaptureDirectory;
}
QString AppSettings::iconStyle() const { return m_iconStyle; }
QStringList AppSettings::fastestFeatures() const { return m_fastestFeatures; }

void AppSettings::setNotificationsEnabled(bool enabled)
{
    if (m_notificationsEnabled == enabled) {
        return;
    }
    m_notificationsEnabled = enabled;
    writeSetting("NotificationsEnabled", enabled);
    emit notificationsEnabledChanged();
}

void AppSettings::setReconnectEnabled(bool enabled)
{
    if (m_reconnectEnabled == enabled) {
        return;
    }
    m_reconnectEnabled = enabled;
    writeSetting("ReconnectEnabled", enabled);
    emit reconnectEnabledChanged();
}

void AppSettings::setStartMinimized(bool enabled)
{
    if (m_startMinimized == enabled) {
        return;
    }
    m_startMinimized = enabled;
    writeSetting("StartMinimized", enabled);
    emit startMinimizedChanged();
}

void AppSettings::setCloseToTray(bool enabled)
{
    if (m_closeToTray == enabled) {
        return;
    }
    m_closeToTray = enabled;
    writeSetting("CloseToTray", enabled);
    emit closeToTrayChanged();
}

void AppSettings::setAutoConnectTarget(const QString &target)
{
    const QString normalized = normalizeConnectionTarget(target);
    if (m_autoConnectTarget == normalized) {
        return;
    }
    m_autoConnectTarget = normalized;
    writeSetting("AutoConnectTarget", normalized);
    emit autoConnectTargetChanged();
}

void AppSettings::setPinnedServersText(const QString &servers)
{
    const QStringList normalized = normalizePinnedServers(servers);
    if (m_pinnedServers == normalized) {
        return;
    }
    m_pinnedServers = normalized;
    writeSetting("PinnedServers", normalized);
    emit pinnedServersChanged();
}

bool AppSettings::isServerPinned(const QString &server) const
{
    const QString normalized = normalizeConnectionTarget(server);
    return !normalized.isEmpty() && m_pinnedServers.contains(normalized);
}

void AppSettings::togglePinnedServer(const QString &server)
{
    const QString normalized = normalizeConnectionTarget(server);
    if (normalized.isEmpty() || normalized == QStringLiteral("FASTEST")) {
        return;
    }
    QStringList updated = m_pinnedServers;
    if (!updated.removeOne(normalized)) {
        if (updated.size() >= 20) {
            return;
        }
        updated.append(normalized);
    }
    m_pinnedServers = updated;
    writeSetting("PinnedServers", updated);
    emit pinnedServersChanged();
}

bool AppSettings::isServerGroupPinned(const QString &countryCode,
                                      const QString &groupKind,
                                      const QString &groupName) const
{
    const PinnedServerGroup normalized = normalizePinnedServerGroup(
        countryCode, groupKind, groupName);
    return !normalized.countryCode.isEmpty()
        && m_pinnedServerGroups.contains(normalized);
}

void AppSettings::togglePinnedServerGroup(const QString &countryCode,
                                          const QString &groupKind,
                                          const QString &groupName)
{
    const PinnedServerGroup normalized = normalizePinnedServerGroup(
        countryCode, groupKind, groupName);
    if (normalized.countryCode.isEmpty()) {
        return;
    }
    QVector<PinnedServerGroup> updated = m_pinnedServerGroups;
    const auto existing = std::find(updated.cbegin(), updated.cend(), normalized);
    if (existing == updated.cend()) {
        if (updated.size() >= 20) {
            return;
        }
        updated.append(normalized);
    } else {
        updated.removeAt(static_cast<qsizetype>(
            std::distance(updated.cbegin(), existing)));
    }
    m_pinnedServerGroups = updated;
    QStringList encoded;
    encoded.reserve(updated.size());
    for (const PinnedServerGroup &group : updated) {
        encoded.append(encodePinnedServerGroup(group));
    }
    writeSetting("PinnedServerGroups", encoded);
    emit pinnedServerGroupsChanged();
}

void AppSettings::setPacketCaptureDirectory(const QString &directory)
{
    const QString normalized = QDir::cleanPath(directory.trimmed());
    if (normalized.isEmpty() || !QDir::isAbsolutePath(normalized)
        || normalized.size() > 4096 || m_packetCaptureDirectory == normalized) {
        return;
    }
    m_packetCaptureDirectory = normalized;
    writeSetting("PacketCaptureDirectory", normalized);
    emit packetCaptureDirectoryChanged();
}

void AppSettings::setPacketCaptureDirectoryUrl(const QUrl &directory)
{
    if (directory.isLocalFile()) {
        setPacketCaptureDirectory(directory.toLocalFile());
    }
}

void AppSettings::setIconStyle(const QString &style)
{
    const QString normalized = normalizeIconStyle(style);
    if (m_iconStyle == normalized) {
        return;
    }
    m_iconStyle = normalized;
    writeSetting("IconStyle", normalized);
    emit iconStyleChanged();
}

void AppSettings::setFastestFeatures(const QStringList &features)
{
    const QStringList normalized = normalizeFastestFeatures(features);
    if (m_fastestFeatures == normalized) {
        return;
    }
    m_fastestFeatures = normalized;
    writeSetting("FastestFeatures", normalized);
    emit fastestFeaturesChanged();
}

bool AppSettings::fastestFeatureEnabled(const QString &feature) const
{
    const QStringList normalized = normalizeFastestFeatures({feature});
    return normalized.size() == 1 && m_fastestFeatures.contains(normalized.first());
}

void AppSettings::setFastestFeatureEnabled(const QString &feature, bool enabled)
{
    const QStringList normalized = normalizeFastestFeatures({feature});
    if (normalized.size() != 1) {
        return;
    }
    QStringList updated = m_fastestFeatures;
    if (enabled) {
        updated.append(normalized.first());
    } else {
        updated.removeAll(normalized.first());
    }
    setFastestFeatures(updated);
}

void AppSettings::reloadSettings()
{
    const KConfigGroup group(m_config, QString::fromLatin1(kGeneralGroup));
    const bool notifications = group.readEntry("NotificationsEnabled", true);
    const bool reconnect = group.readEntry("ReconnectEnabled", true);
    const bool startMinimized = group.readEntry("StartMinimized", false);
    const bool closeToTray = group.readEntry("CloseToTray", true);
    const QString autoConnect = normalizeConnectionTarget(
        group.readEntry("AutoConnectTarget", QString()));
    const QStringList pinned = normalizePinnedServers(
        group.readEntry("PinnedServers", QStringList()).join(QLatin1Char(',')));
    const QVector<PinnedServerGroup> pinnedServerGroups =
        normalizePinnedServerGroups(
            group.readEntry("PinnedServerGroups", QStringList()));
    const QString captureDirectory = group.readEntry(
        "PacketCaptureDirectory", QDir::tempPath());
    const QString iconStyle = normalizeIconStyle(
        group.readEntry("IconStyle", QStringLiteral("color")));
    const QStringList fastestFeatures = normalizeFastestFeatures(
        group.readEntry("FastestFeatures", QStringList()));

    if (m_notificationsEnabled != notifications) {
        m_notificationsEnabled = notifications;
        emit notificationsEnabledChanged();
    }
    if (m_reconnectEnabled != reconnect) {
        m_reconnectEnabled = reconnect;
        emit reconnectEnabledChanged();
    }
    if (m_startMinimized != startMinimized) {
        m_startMinimized = startMinimized;
        emit startMinimizedChanged();
    }
    if (m_closeToTray != closeToTray) {
        m_closeToTray = closeToTray;
        emit closeToTrayChanged();
    }
    if (m_autoConnectTarget != autoConnect) {
        m_autoConnectTarget = autoConnect;
        emit autoConnectTargetChanged();
    }
    if (m_pinnedServers != pinned) {
        m_pinnedServers = pinned;
        emit pinnedServersChanged();
    }
    if (m_pinnedServerGroups != pinnedServerGroups) {
        m_pinnedServerGroups = pinnedServerGroups;
        emit pinnedServerGroupsChanged();
    }
    if (m_packetCaptureDirectory != captureDirectory) {
        m_packetCaptureDirectory = captureDirectory;
        emit packetCaptureDirectoryChanged();
    }
    if (m_iconStyle != iconStyle) {
        m_iconStyle = iconStyle;
        emit iconStyleChanged();
    }
    if (m_fastestFeatures != fastestFeatures) {
        m_fastestFeatures = fastestFeatures;
        emit fastestFeaturesChanged();
    }
}

void AppSettings::writeSetting(const char *key, bool value)
{
    KConfigGroup group(m_config, QString::fromLatin1(kGeneralGroup));
    group.writeEntry(key, value, KConfigBase::Notify);
    m_config->sync();
}

void AppSettings::writeSetting(const char *key, const QString &value)
{
    KConfigGroup group(m_config, QString::fromLatin1(kGeneralGroup));
    group.writeEntry(key, value, KConfigBase::Notify);
    m_config->sync();
}

void AppSettings::writeSetting(const char *key, const QStringList &value)
{
    KConfigGroup group(m_config, QString::fromLatin1(kGeneralGroup));
    group.writeEntry(key, value, KConfigBase::Notify);
    m_config->sync();
}

QString AppSettings::normalizeConnectionTarget(const QString &target)
{
    QString normalized = target.trimmed().toUpper();
    if (normalized == QStringLiteral("OFF")) {
        return {};
    }
    if (normalized.isEmpty() || normalized.size() > 128
        || normalized.contains(QLatin1Char('\0'))
        || normalized.contains(QLatin1Char('\n'))
        || normalized.contains(QLatin1Char('\r'))) {
        return {};
    }
    return normalized;
}

QStringList AppSettings::normalizePinnedServers(const QString &servers)
{
    QStringList normalized;
    for (const QString &candidate : servers.split(QLatin1Char(','))) {
        const QString target = normalizeConnectionTarget(candidate);
        if (target.isEmpty() || target == QStringLiteral("FASTEST")
            || normalized.contains(target)) {
            continue;
        }
        normalized.append(target);
        if (normalized.size() == 20) {
            break;
        }
    }
    return normalized;
}

AppSettings::PinnedServerGroup AppSettings::normalizePinnedServerGroup(
    const QString &countryCode, const QString &groupKind,
    const QString &groupName)
{
    const QString normalizedCode = countryCode.trimmed().toUpper();
    const QString normalizedKind = groupKind.trimmed().toLower();
    const QString normalizedName = groupName.trimmed();
    if (normalizedCode.size() != 2
        || normalizedCode.at(0) < QLatin1Char('A')
        || normalizedCode.at(0) > QLatin1Char('Z')
        || normalizedCode.at(1) < QLatin1Char('A')
        || normalizedCode.at(1) > QLatin1Char('Z')
        || (normalizedKind != QStringLiteral("location")
            && normalizedKind != QStringLiteral("secure-core"))
        || normalizedName.isEmpty() || normalizedName.size() > 256
        || normalizedName.contains(QLatin1Char('\0'))
        || normalizedName.contains(QLatin1Char('\n'))
        || normalizedName.contains(QLatin1Char('\r'))) {
        return {};
    }
    return {normalizedCode, normalizedKind, normalizedName};
}

QString AppSettings::encodePinnedServerGroup(const PinnedServerGroup &group)
{
    const QByteArray encodedName = QUrl::toPercentEncoding(group.name);
    return QStringLiteral("%1/%2/%3")
        .arg(group.countryCode, group.kind,
             QString::fromLatin1(encodedName));
}

AppSettings::PinnedServerGroup AppSettings::decodePinnedServerGroup(
    const QString &encoded)
{
    const qsizetype firstSeparator = encoded.indexOf(QLatin1Char('/'));
    const qsizetype secondSeparator = encoded.indexOf(
        QLatin1Char('/'), firstSeparator + 1);
    if (firstSeparator <= 0 || secondSeparator <= firstSeparator + 1) {
        return {};
    }
    return normalizePinnedServerGroup(
        encoded.left(firstSeparator),
        encoded.sliced(firstSeparator + 1,
                       secondSeparator - firstSeparator - 1),
        QUrl::fromPercentEncoding(encoded.sliced(secondSeparator + 1).toLatin1()));
}

QVector<AppSettings::PinnedServerGroup> AppSettings::normalizePinnedServerGroups(
    const QStringList &groups)
{
    QVector<PinnedServerGroup> normalized;
    normalized.reserve(std::min<qsizetype>(groups.size(), 20));
    for (const QString &encoded : groups) {
        const PinnedServerGroup group = decodePinnedServerGroup(encoded);
        if (group.countryCode.isEmpty() || normalized.contains(group)) {
            continue;
        }
        normalized.append(group);
        if (normalized.size() == 20) {
            break;
        }
    }
    return normalized;
}

QString AppSettings::normalizeIconStyle(const QString &style)
{
    const QString normalized = style.trimmed().toLower();
    if (normalized == QStringLiteral("light")
        || normalized == QStringLiteral("dark")) {
        return normalized;
    }
    return QStringLiteral("color");
}

QStringList AppSettings::normalizeFastestFeatures(const QStringList &features)
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
