#include "AppSettings.h"

#include <KConfigGroup>
#include <QDir>

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
QString AppSettings::packetCaptureDirectory() const
{
    return m_packetCaptureDirectory;
}

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
    const QString captureDirectory = group.readEntry(
        "PacketCaptureDirectory", QDir::tempPath());

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
    if (m_packetCaptureDirectory != captureDirectory) {
        m_packetCaptureDirectory = captureDirectory;
        emit packetCaptureDirectoryChanged();
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
