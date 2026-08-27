#include "AppSettings.h"

#include <KConfigGroup>
#include <KSharedConfig>

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
}

bool AppSettings::notificationsEnabled() const { return m_notificationsEnabled; }
bool AppSettings::reconnectEnabled() const { return m_reconnectEnabled; }
bool AppSettings::startMinimized() const { return m_startMinimized; }
bool AppSettings::closeToTray() const { return m_closeToTray; }

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

void AppSettings::writeSetting(const char *key, bool value)
{
    const auto config = KSharedConfig::openConfig(QString::fromLatin1(kConfigFile));
    KConfigGroup group(config, QString::fromLatin1(kGeneralGroup));
    group.writeEntry(key, value);
    config->sync();
}
