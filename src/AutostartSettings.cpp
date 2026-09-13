// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#include "AutostartSettings.h"

#include <KConfig>
#include <KConfigGroup>
#include <QDir>
#include <QFileInfo>
#include <QStandardPaths>

namespace {
constexpr auto managedKey = "X-PlasmaVPN-Managed";
}

AutostartSettings::AutostartSettings(QObject *parent) : QObject(parent)
{
    refresh();
}

QString AutostartSettings::entryPath() const
{
    return QDir(QStandardPaths::writableLocation(QStandardPaths::GenericConfigLocation))
        .filePath(QStringLiteral("autostart/proton-vpn-kde.desktop"));
}

void AutostartSettings::refresh()
{
    m_enabled = false;
    m_configurable = true;
    m_errorMessage.clear();
    const QFileInfo info(entryPath());
    if (info.isSymbolicLink() || (info.exists() && (!info.isFile() || info.size() > 16384))) {
        m_configurable = false;
    } else if (info.exists()) {
        const KConfig file(entryPath(), KConfig::SimpleConfig);
        const KConfigGroup entry(&file, QStringLiteral("Desktop Entry"));
        m_configurable = entry.readEntry(managedKey, false);
        m_enabled = m_configurable && !entry.readEntry("Hidden", false);
    }
    if (!m_configurable) {
        m_errorMessage = tr("An existing Plasma VPN login entry is managed elsewhere. Remove it in Plasma Autostart before using this switch; this client will not overwrite it.");
    }
    emit changed();
}

void AutostartSettings::setEnabled(bool enabled)
{
    // Re-read before writing so an externally replaced entry is not adopted.
    refresh();
    if (!m_configurable || (!enabled && !QFileInfo::exists(entryPath()))) {
        return;
    }
    if (!QDir().mkpath(QFileInfo(entryPath()).absolutePath())) {
        m_errorMessage = tr("Unable to create the Plasma Autostart directory.");
        emit changed();
        return;
    }

    KConfig file(entryPath(), KConfig::SimpleConfig);
    KConfigGroup entry(&file, QStringLiteral("Desktop Entry"));
    // Desktop Exec quoting, not shell quoting. KConfig supplies the file-level
    // backslash escaping. Never persist the development/test executable path.
    QString executable = QStringLiteral(PROTON_VPN_KDE_CONTROL_CENTER_EXECUTABLE_PATH);
    QString quoted = executable;
    quoted.replace(QLatin1Char('\\'), QStringLiteral("\\\\"));
    quoted.replace(QLatin1Char('"'), QStringLiteral("\\\""));
    quoted.replace(QLatin1Char('$'), QStringLiteral("\\$"));
    quoted.replace(QLatin1Char('`'), QStringLiteral("\\`"));
    quoted.replace(QLatin1Char('%'), QStringLiteral("%%"));
    entry.writeEntry("Type", "Application");
    entry.writeEntry("Name", "Plasma VPN");
    entry.writeEntry("Exec", QLatin1Char('"') + quoted + QLatin1Char('"'));
    entry.writeEntry("TryExec", executable);
    entry.writeEntry("Icon", "quest.entropy.PlasmaVPN");
    entry.writeEntry("OnlyShowIn", "KDE;");
    entry.deleteEntry("NotShowIn");
    entry.writeEntry("Terminal", false);
    entry.writeEntry("Hidden", !enabled);
    entry.writeEntry(managedKey, true);
    if (!file.sync()) {
        file.markAsClean(); // Do not retry a failed save during destruction.
        m_errorMessage = tr("Unable to save the Plasma Autostart entry. Check the directory and file permissions.");
        emit changed();
        return;
    }
    refresh();
    if (m_enabled != enabled && m_errorMessage.isEmpty()) {
        m_errorMessage = tr("The login preference was not saved. The autostart entry may be locked by desktop policy.");
        emit changed();
    }
}
