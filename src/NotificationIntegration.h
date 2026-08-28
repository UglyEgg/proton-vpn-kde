#pragma once

#include <QObject>
#include <QString>

class AppSettings;
class VpnController;

class NotificationIntegration final : public QObject
{
    Q_OBJECT

public:
    NotificationIntegration(VpnController *controller, AppSettings *settings,
                            QObject *parent = nullptr);

private:
    void updateState();

    VpnController *m_controller = nullptr;
    AppSettings *m_settings = nullptr;
    QString m_previousState;
    int m_previousForwardedPort = 0;
    bool m_initialized = false;
};
