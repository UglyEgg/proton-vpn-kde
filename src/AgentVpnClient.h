// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#pragma once

#include "VpnConnectionController.h"
#include "OperationCompletion.h"

#include <QDBusContext>
#include <QString>
#include <QStringList>
#include <QtTypes>
#include <QVariant>

class QDBusPendingCallWatcher;
class QDBusServiceWatcher;
class QTimer;

class AgentVpnClient final : public VpnConnectionController,
                             protected QDBusContext
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
    [[nodiscard]] ProtonVpnKde::ConnectionActionCapabilities
    connectionCapabilities() const override;

    void setReconnectionEnabled(bool enabled);
    void setFastestFeatures(const QStringList &features);
    void autoConnect(const QString &target);

public slots:
    void activatePrimaryAction() override;
    void connectTarget(const QString &target) override;
    void connectGroup(const QString &countryCode,
                      const QString &groupKind,
                      const QString &groupName) override;
    void disconnect() override;

signals:
    void controlCenterRequested();

private slots:
    void onServiceRegistered(const QString &service);
    void onServiceUnregistered(const QString &service);
    void onSnapshotChanged(const QString &snapshotJson);

private:
    void setBackendAvailable(bool available);
    void stampBackendRequest(QDBusPendingCallWatcher *watcher) const;
    [[nodiscard]] bool backendReplyIsCurrent(
        const QDBusPendingCallWatcher *watcher) const;
    [[nodiscard]] bool backendSignalIsCurrent() const;
    void connectBackendSignals();
    void disconnectBackendSignals();
    void authorizeClient();
    void scheduleRecoveryRead();
    void requestSnapshot(bool allowActivation = false,
                         quint64 operationGeneration = 0);
    void applySnapshot(const QString &snapshotJson);
    void applyReconnectionPreference();
    void acquireTransientLease();
    void releaseTransientLease();
    void queueConnection(const QString &target, bool interactive,
                         bool onlyWhenDisconnected);
    void clearPendingConnection();
    void dispatchPendingConnection();
    void callOperation(const QString &method,
                       const QVariantList &arguments = {});
    void handleSnapshotReply(QDBusPendingCallWatcher *watcher);
    void handleOperationReply(QDBusPendingCallWatcher *watcher);

    QDBusServiceWatcher *m_serviceWatcher = nullptr;
    QTimer *m_recoveryRetryTimer = nullptr;
    int m_recoveryRetryCount = 0;
    bool m_authorizationRejected = false;
    bool m_discoveryPending = false;
    bool m_identityPending = false;
    bool m_backendAvailable = false;
    QString m_backendDestination;
    bool m_authorizationPending = false;
    bool m_ready = false;
    bool m_snapshotHealthy = false;
    bool m_loggedIn = false;
    bool m_busy = false;
    bool m_reconnectionEnabled = true;
    bool m_reconnectionApplied = false;
    bool m_reconnectionPending = false;
    ProtonVpnKde::OperationCompletion m_operationCompletion;
    quint64 m_connectionIntentGeneration = 0;
    quint64 m_transientLeaseRequestGeneration = 0;
    bool m_transientLeasePending = false;
    bool m_transientLeaseActive = false;
    bool m_transientLeaseMayExist = false;
    quint64 m_serviceGeneration = 0;
    quint64 m_reconnectionRequestGeneration = 0;
    int m_killSwitch = 0;
    int m_forwardedPort = 0;
    QString m_state = QStringLiteral("unavailable");
    QString m_authState = QStringLiteral("signed_out");
    QString m_serverName;
    QString m_message;
    QStringList m_fastestFeatures;
    QString m_pendingTarget;
    QStringList m_pendingGroup;
    bool m_pendingInteractive = false;
    bool m_pendingOnlyWhenDisconnected = false;
};
