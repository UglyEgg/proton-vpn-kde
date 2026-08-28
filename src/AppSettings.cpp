#include "AppSettings.h"

#include <KConfigGroup>
#include <KSharedConfig>
#include <QDir>

namespace
{
constexpr auto kConfigFile = "proton-vpn-kderc";
constexpr auto kGeneralGroup = "General";
}

AppSettings::AppSettings(QObject *parent)
    : QObject(parent)
{
    const KConfigGroup group(KSharedConfig::openConfig(QString::fromLatin1(kConfigFile)),
                             QString::fromLatin1(kGeneralGroup));
    m_notificationsEnabled = group.readEntry("NotificationsEnabled", true);
    m_reconnectEnabled = group.readEntry("ReconnectEnabled", true);
    m_startMinimized = group.readEntry("StartMinimized", false);
    m_closeToTray = group.readEntry("CloseToTray", true);
    m_autoConnectTarget = normalizeConnectionTarget(
        group.readEntry("AutoConnectTarget", QString()));
    m_pinnedServers = normalizePinnedServers(
        group.readEntry("PinnedServers", QStringList()).join(QLatin1Char(',')));
    m_packetCaptureDirectory = group.readEntry(
        "PacketCaptureDirectory", QDir::tempPath());
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

void AppSettings::writeSetting(const char *key, bool value)
{
    const auto config = KSharedConfig::openConfig(QString::fromLatin1(kConfigFile));
    KConfigGroup group(config, QString::fromLatin1(kGeneralGroup));
    group.writeEntry(key, value);
    config->sync();
}

void AppSettings::writeSetting(const char *key, const QString &value)
{
    const auto config = KSharedConfig::openConfig(QString::fromLatin1(kConfigFile));
    KConfigGroup group(config, QString::fromLatin1(kGeneralGroup));
    group.writeEntry(key, value);
    config->sync();
}

void AppSettings::writeSetting(const char *key, const QStringList &value)
{
    const auto config = KSharedConfig::openConfig(QString::fromLatin1(kConfigFile));
    KConfigGroup group(config, QString::fromLatin1(kGeneralGroup));
    group.writeEntry(key, value);
    config->sync();
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
