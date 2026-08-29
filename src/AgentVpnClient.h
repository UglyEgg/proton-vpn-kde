#pragma once

#include "VpnConnectionController.h"

#include <QString>
#include <QVariant>

class QDBusPendingCallWatcher;
class QDBusServiceWatcher;

class AgentVpnClient final : public VpnConnectionController
{
    Q_OBJECT

public:
    explicit AgentVpnClient(QObject *parent = nullptr);

    [[nodiscard]] bool backendAvailable() const override;
    [[nodiscard]] bool ready() const override;
    [[nodiscard]] bool loggedIn() const override;
    [[nodiscard]] bool busy() const override;
    [[nodiscard]] int killSwitch() const override;
    [[nodiscard]] QString state() const override;
    [[nodiscard]] QString serverName() const override;
    [[nodiscard]] int forwardedPort() const override;
    [[nodiscard]] QString message() const override;
    [[nodiscard]] QString primaryActionText() const override;
    [[nodiscard]] bool primaryActionEnabled() const override;

    void setReconnectionEnabled(bool enabled);
    void autoConnect(const QString &target);

public slots:
    void activatePrimaryAction() override;
    void connectTarget(const QString &target) override;
    void disconnect() override;

signals:
    void controlCenterRequested();

private slots:
    void onServiceRegistered(const QString &service);
    void onServiceUnregistered(const QString &service);
    void onSnapshotChanged(const QString &snapshotJson);

private:
    void setBackendAvailable(bool available);
    void requestSnapshot(bool allowActivation = false);
    void applySnapshot(const QString &snapshotJson);
    void applyReconnectionPreference();
    void queueConnection(const QString &target, bool interactive,
                         bool onlyWhenDisconnected);
    void dispatchPendingConnection();
    void callOperation(const QString &method,
                       const QVariantList &arguments = {});
    void handleSnapshotReply(QDBusPendingCallWatcher *watcher);
    void handleOperationReply(QDBusPendingCallWatcher *watcher);

    QDBusServiceWatcher *m_serviceWatcher = nullptr;
    bool m_backendAvailable = false;
    bool m_ready = false;
    bool m_loggedIn = false;
    bool m_busy = false;
    bool m_reconnectionEnabled = true;
    bool m_reconnectionApplied = false;
    int m_killSwitch = 0;
    int m_forwardedPort = 0;
    QString m_state = QStringLiteral("disconnected");
    QString m_serverName;
    QString m_message;
    QString m_pendingTarget;
    bool m_pendingInteractive = false;
    bool m_pendingOnlyWhenDisconnected = false;
};
