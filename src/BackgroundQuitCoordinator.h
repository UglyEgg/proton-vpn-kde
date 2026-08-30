// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#pragma once

#include <QObject>
#include <QTimer>

class VpnConnectionController;

class BackgroundQuitCoordinator final : public QObject
{
    Q_OBJECT

public:
    explicit BackgroundQuitCoordinator(VpnConnectionController *controller,
                                       int disconnectTimeoutMs = 15000,
                                       QObject *parent = nullptr);

    [[nodiscard]] bool pending() const;

public slots:
    void disconnectAndQuit();

signals:
    void pendingChanged();
    void readyToQuit();
    void disconnectTimedOut();

private:
    void finishIfDisconnected();
    void setPending(bool pending);

    VpnConnectionController *m_controller = nullptr;
    QTimer m_disconnectTimeout;
    bool m_pending = false;
};
