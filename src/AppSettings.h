#pragma once

#include <QObject>

class AppSettings final : public QObject
{
    Q_OBJECT
    Q_PROPERTY(bool notificationsEnabled READ notificationsEnabled WRITE setNotificationsEnabled NOTIFY notificationsEnabledChanged)
    Q_PROPERTY(bool reconnectEnabled READ reconnectEnabled WRITE setReconnectEnabled NOTIFY reconnectEnabledChanged)
    Q_PROPERTY(bool startMinimized READ startMinimized WRITE setStartMinimized NOTIFY startMinimizedChanged)
    Q_PROPERTY(bool closeToTray READ closeToTray WRITE setCloseToTray NOTIFY closeToTrayChanged)

public:
    explicit AppSettings(QObject *parent = nullptr);

    [[nodiscard]] bool notificationsEnabled() const;
    [[nodiscard]] bool reconnectEnabled() const;
    [[nodiscard]] bool startMinimized() const;
    [[nodiscard]] bool closeToTray() const;

    void setNotificationsEnabled(bool enabled);
    void setReconnectEnabled(bool enabled);
    void setStartMinimized(bool enabled);
    void setCloseToTray(bool enabled);

signals:
    void notificationsEnabledChanged();
    void reconnectEnabledChanged();
    void startMinimizedChanged();
    void closeToTrayChanged();

private:
    void writeSetting(const char *key, bool value);

    bool m_notificationsEnabled = true;
    bool m_reconnectEnabled = true;
    bool m_startMinimized = false;
    bool m_closeToTray = true;
};
