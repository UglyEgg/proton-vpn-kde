// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#pragma once

#include "ConnectionAction.h"

#include <QObject>
#include <QString>

class VpnConnectionController : public QObject
{
    Q_OBJECT
    Q_PROPERTY(bool canConnect READ canConnect NOTIFY snapshotChanged)
    Q_PROPERTY(bool canDisconnect READ canDisconnect NOTIFY snapshotChanged)
    Q_PROPERTY(bool primaryActionDisconnects READ primaryActionDisconnects NOTIFY snapshotChanged)

public:
    using QObject::QObject;
    ~VpnConnectionController() override = default;

    [[nodiscard]] virtual bool backendAvailable() const = 0;
    [[nodiscard]] virtual bool ready() const = 0;
    [[nodiscard]] virtual bool loggedIn() const = 0;
    [[nodiscard]] virtual bool busy() const = 0;
    [[nodiscard]] virtual int killSwitch() const = 0;
    [[nodiscard]] virtual QString state() const = 0;
    [[nodiscard]] virtual QString serverName() const = 0;
    [[nodiscard]] virtual int forwardedPort() const = 0;
    [[nodiscard]] virtual QString message() const = 0;
    [[nodiscard]] virtual QString primaryActionText() const = 0;
    [[nodiscard]] virtual ProtonVpnKde::ConnectionActionCapabilities
    connectionCapabilities() const = 0;
    [[nodiscard]] bool canConnect() const
    {
        const auto capability = connectionCapabilities();
        return capability.connect || capability.activate;
    }
    [[nodiscard]] bool canDisconnect() const { return connectionCapabilities().disconnect; }
    [[nodiscard]] bool primaryActionDisconnects() const
    {
        return connectionCapabilities().primaryDisconnects;
    }
    [[nodiscard]] bool primaryActionEnabled() const
    {
        const auto capability = connectionCapabilities();
        return capability.primaryDisconnects ? capability.disconnect
                                             : capability.connect || capability.activate;
    }

public slots:
    virtual void activatePrimaryAction() = 0;
    virtual void connectTarget(const QString &target) = 0;
    virtual void connectGroup(const QString &countryCode,
                              const QString &groupKind,
                              const QString &groupName) = 0;
    virtual void disconnect() = 0;

signals:
    void backendAvailableChanged();
    void snapshotChanged();
};
