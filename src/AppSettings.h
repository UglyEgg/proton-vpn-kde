#pragma once

#include <QObject>
#include <QStringList>

class AppSettings final : public QObject
{
    Q_OBJECT
    Q_PROPERTY(bool notificationsEnabled READ notificationsEnabled WRITE setNotificationsEnabled NOTIFY notificationsEnabledChanged)
    Q_PROPERTY(bool reconnectEnabled READ reconnectEnabled WRITE setReconnectEnabled NOTIFY reconnectEnabledChanged)
    Q_PROPERTY(bool startMinimized READ startMinimized WRITE setStartMinimized NOTIFY startMinimizedChanged)
    Q_PROPERTY(bool closeToTray READ closeToTray WRITE setCloseToTray NOTIFY closeToTrayChanged)
    Q_PROPERTY(QString autoConnectTarget READ autoConnectTarget WRITE setAutoConnectTarget NOTIFY autoConnectTargetChanged)
    Q_PROPERTY(QString pinnedServersText READ pinnedServersText WRITE setPinnedServersText NOTIFY pinnedServersChanged)

public:
    explicit AppSettings(QObject *parent = nullptr);

    [[nodiscard]] bool notificationsEnabled() const;
    [[nodiscard]] bool reconnectEnabled() const;
    [[nodiscard]] bool startMinimized() const;
    [[nodiscard]] bool closeToTray() const;
    [[nodiscard]] QString autoConnectTarget() const;
    [[nodiscard]] QString pinnedServersText() const;
    [[nodiscard]] QStringList pinnedServers() const;

    void setNotificationsEnabled(bool enabled);
    void setReconnectEnabled(bool enabled);
    void setStartMinimized(bool enabled);
    void setCloseToTray(bool enabled);
    void setAutoConnectTarget(const QString &target);
    void setPinnedServersText(const QString &servers);

    Q_INVOKABLE bool isServerPinned(const QString &server) const;
    Q_INVOKABLE void togglePinnedServer(const QString &server);

signals:
    void notificationsEnabledChanged();
    void reconnectEnabledChanged();
    void startMinimizedChanged();
    void closeToTrayChanged();
    void autoConnectTargetChanged();
    void pinnedServersChanged();

private:
    void writeSetting(const char *key, bool value);
    void writeSetting(const char *key, const QString &value);
    void writeSetting(const char *key, const QStringList &value);
    static QString normalizeConnectionTarget(const QString &target);
    static QStringList normalizePinnedServers(const QString &servers);

    bool m_notificationsEnabled = true;
    bool m_reconnectEnabled = true;
    bool m_startMinimized = false;
    bool m_closeToTray = true;
    QString m_autoConnectTarget;
    QStringList m_pinnedServers;
};
