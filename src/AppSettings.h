// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#pragma once

#include <KConfigWatcher>
#include <KSharedConfig>
#include <QObject>
#include <QStringList>
#include <QUrl>
#include <QVector>

class AppSettings final : public QObject
{
    Q_OBJECT
    Q_PROPERTY(bool notificationsEnabled READ notificationsEnabled WRITE setNotificationsEnabled NOTIFY notificationsEnabledChanged)
    Q_PROPERTY(bool reconnectEnabled READ reconnectEnabled WRITE setReconnectEnabled NOTIFY reconnectEnabledChanged)
    Q_PROPERTY(bool startMinimized READ startMinimized WRITE setStartMinimized NOTIFY startMinimizedChanged)
    Q_PROPERTY(bool closeToTray READ closeToTray WRITE setCloseToTray NOTIFY closeToTrayChanged)
    Q_PROPERTY(QString autoConnectTarget READ autoConnectTarget WRITE setAutoConnectTarget NOTIFY autoConnectTargetChanged)
    Q_PROPERTY(QString pinnedServersText READ pinnedServersText WRITE setPinnedServersText NOTIFY pinnedServersChanged)
    Q_PROPERTY(QString pinnedServerGroupsText READ pinnedServerGroupsText NOTIFY pinnedServerGroupsChanged)
    Q_PROPERTY(QString packetCaptureDirectory READ packetCaptureDirectory WRITE setPacketCaptureDirectory NOTIFY packetCaptureDirectoryChanged)
    Q_PROPERTY(QString iconStyle READ iconStyle WRITE setIconStyle NOTIFY iconStyleChanged)
    Q_PROPERTY(QStringList fastestFeatures READ fastestFeatures WRITE setFastestFeatures NOTIFY fastestFeaturesChanged)

public:
    struct PinnedServerGroup {
        QString countryCode;
        QString kind;
        QString name;

        bool operator==(const PinnedServerGroup &) const = default;
    };

    explicit AppSettings(QObject *parent = nullptr);

    [[nodiscard]] bool notificationsEnabled() const;
    [[nodiscard]] bool reconnectEnabled() const;
    [[nodiscard]] bool startMinimized() const;
    [[nodiscard]] bool closeToTray() const;
    [[nodiscard]] QString autoConnectTarget() const;
    [[nodiscard]] QString pinnedServersText() const;
    [[nodiscard]] QStringList pinnedServers() const;
    [[nodiscard]] QString pinnedServerGroupsText() const;
    [[nodiscard]] QVector<PinnedServerGroup> pinnedServerGroups() const;
    [[nodiscard]] QString packetCaptureDirectory() const;
    [[nodiscard]] QString iconStyle() const;
    [[nodiscard]] QStringList fastestFeatures() const;

    void setNotificationsEnabled(bool enabled);
    void setReconnectEnabled(bool enabled);
    void setStartMinimized(bool enabled);
    void setCloseToTray(bool enabled);
    void setAutoConnectTarget(const QString &target);
    void setPinnedServersText(const QString &servers);
    void setPacketCaptureDirectory(const QString &directory);
    void setIconStyle(const QString &style);
    void setFastestFeatures(const QStringList &features);

    Q_INVOKABLE bool isServerPinned(const QString &server) const;
    Q_INVOKABLE void togglePinnedServer(const QString &server);
    Q_INVOKABLE bool isServerGroupPinned(const QString &countryCode,
                                         const QString &groupKind,
                                         const QString &groupName) const;
    Q_INVOKABLE void togglePinnedServerGroup(const QString &countryCode,
                                             const QString &groupKind,
                                             const QString &groupName);
    Q_INVOKABLE void setPacketCaptureDirectoryUrl(const QUrl &directory);
    Q_INVOKABLE bool fastestFeatureEnabled(const QString &feature) const;
    Q_INVOKABLE void setFastestFeatureEnabled(const QString &feature,
                                              bool enabled);

signals:
    void notificationsEnabledChanged();
    void reconnectEnabledChanged();
    void startMinimizedChanged();
    void closeToTrayChanged();
    void autoConnectTargetChanged();
    void pinnedServersChanged();
    void pinnedServerGroupsChanged();
    void packetCaptureDirectoryChanged();
    void iconStyleChanged();
    void fastestFeaturesChanged();

private:
    void reloadSettings();
    void writeSetting(const char *key, bool value);
    void writeSetting(const char *key, const QString &value);
    void writeSetting(const char *key, const QStringList &value);
    static QString normalizeConnectionTarget(const QString &target);
    static QStringList normalizePinnedServers(const QString &servers);
    static PinnedServerGroup normalizePinnedServerGroup(
        const QString &countryCode, const QString &groupKind,
        const QString &groupName);
    static QString encodePinnedServerGroup(const PinnedServerGroup &group);
    static PinnedServerGroup decodePinnedServerGroup(const QString &encoded);
    static QVector<PinnedServerGroup> normalizePinnedServerGroups(
        const QStringList &groups);
    static QString normalizeIconStyle(const QString &style);
    static QStringList normalizeFastestFeatures(const QStringList &features);

    KSharedConfig::Ptr m_config;
    KConfigWatcher::Ptr m_configWatcher;
    bool m_notificationsEnabled = true;
    bool m_reconnectEnabled = true;
    bool m_startMinimized = false;
    bool m_closeToTray = true;
    QString m_autoConnectTarget;
    QStringList m_pinnedServers;
    QVector<PinnedServerGroup> m_pinnedServerGroups;
    QString m_packetCaptureDirectory;
    QString m_iconStyle = QStringLiteral("color");
    QStringList m_fastestFeatures;
};
