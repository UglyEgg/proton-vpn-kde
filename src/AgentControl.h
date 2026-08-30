#pragma once

#include <QObject>
#include <QStringList>

class AgentControl final : public QObject
{
    Q_OBJECT
    Q_CLASSINFO("D-Bus Interface", "quest.entropy.PlasmaVPN.Agent1")

public:
    explicit AgentControl(QObject *parent = nullptr);
    [[nodiscard]] bool registerOnSessionBus();

public slots:
    void EnsureRunning();
    void ShowControlCenter();
    void ShowSettings();
    void Quit();

private:
    void launchControlCenter(const QStringList &arguments = {});
};

class QWindow;

class ControlCenterControl final : public QObject
{
    Q_OBJECT
    Q_CLASSINFO("D-Bus Interface", "quest.entropy.PlasmaVPN.ControlCenter1")

public:
    explicit ControlCenterControl(QObject *parent = nullptr);
    [[nodiscard]] bool registerOnSessionBus();
    void setWindow(QWindow *window);

public slots:
    void ShowControlCenter();
    void ShowSettings();
    bool RequestRunnerAction(const QString &action, const QString &argument);
    void Quit();

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
}
