// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#pragma once

#include "DbusContract.h"

#include <QDBusContext>
#include <QObject>
#include <QStringList>

class AgentControl final : public QObject, protected QDBusContext
{
    Q_OBJECT
    Q_CLASSINFO("D-Bus Interface", PROTON_VPN_KDE_DBUS_AGENT_INTERFACE)

public:
    explicit AgentControl(QObject *parent = nullptr);
    [[nodiscard]] bool registerOnSessionBus();

public slots:
    Q_SCRIPTABLE void EnsureRunning();
    Q_SCRIPTABLE void ShowControlCenter();
    Q_SCRIPTABLE void ShowSettings();
    Q_SCRIPTABLE void Quit();

private:
    [[nodiscard]] bool callerIsControlCenter() const;
    void launchControlCenter(const QStringList &arguments = {});
};

class QWindow;

class ControlCenterControl final : public QObject
{
    Q_OBJECT
    Q_CLASSINFO("D-Bus Interface", PROTON_VPN_KDE_DBUS_CONTROL_CENTER_INTERFACE)

public:
    explicit ControlCenterControl(QObject *parent = nullptr);
    [[nodiscard]] bool registerOnSessionBus();
    void setWindow(QWindow *window);

public slots:
    Q_SCRIPTABLE void ShowControlCenter();
    Q_SCRIPTABLE void ShowSettings();
    Q_SCRIPTABLE bool RequestRunnerAction(const QString &action,
                                          const QString &argument);

signals:
    void runnerActionRequested(const QString &action, const QString &argument);

private:
    void present(bool settings);

    QWindow *m_window = nullptr;
    bool m_pendingShow = false;
    bool m_pendingSettings = false;
};

namespace ProtonVpnKde
{
void setAgentEnabled(bool enabled);
void requestControlCenter(bool settings = false);
void requestConfirmedControlCenterAction(const QString &action,
                                         const QString &argument = {});
}
