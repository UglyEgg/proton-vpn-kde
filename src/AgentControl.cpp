// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#include "AgentControl.h"
#include "RunnerActionRequest.h"

#include <QCoreApplication>
#include <QDBusConnection>
#include <QDBusConnectionInterface>
#include <QDBusMessage>
#include <QDBusPendingCallWatcher>
#include <QDBusPendingReply>
#include <QDir>
#include <QFileInfo>
#include <QProcess>
#include <QWindow>

namespace
{
namespace AgentDbus = ProtonVpnKde::DBusContract::Agent;
namespace ControlCenterDbus = ProtonVpnKde::DBusContract::ControlCenter;

QString siblingExecutable(const QString &name)
{
    const QString candidate = QDir(QCoreApplication::applicationDirPath()).filePath(name);
    return QFileInfo(candidate).isExecutable() ? candidate : name;
}

QDBusMessage agentCall(const QString &method)
{
    return QDBusMessage::createMethodCall(
        QString::fromLatin1(AgentDbus::serviceName),
        QString::fromLatin1(AgentDbus::objectPath),
        QString::fromLatin1(AgentDbus::interfaceName), method);
}

QDBusMessage controlCenterCall(const QString &method)
{
    return QDBusMessage::createMethodCall(
        QString::fromLatin1(ControlCenterDbus::serviceName),
        QString::fromLatin1(ControlCenterDbus::objectPath),
        QString::fromLatin1(ControlCenterDbus::interfaceName), method);
}
}

AgentControl::AgentControl(QObject *parent)
    : QObject(parent)
{
}

bool AgentControl::registerOnSessionBus()
{
    QDBusConnection bus = QDBusConnection::sessionBus();
    if (!bus.registerService(QString::fromLatin1(AgentDbus::serviceName))) {
        return false;
    }
    if (bus.registerObject(QString::fromLatin1(AgentDbus::objectPath), this,
                           QDBusConnection::ExportAllSlots)) {
        return true;
    }
    bus.unregisterService(QString::fromLatin1(AgentDbus::serviceName));
    return false;
}

void AgentControl::EnsureRunning()
{
}

void AgentControl::ShowControlCenter()
{
    launchControlCenter();
}

void AgentControl::ShowSettings()
{
    launchControlCenter({QStringLiteral("--settings")});
}

void AgentControl::Quit()
{
    QCoreApplication::quit();
}

void AgentControl::launchControlCenter(const QStringList &arguments)
{
    ProtonVpnKde::requestControlCenter(
        arguments.contains(QStringLiteral("--settings")));
}

ControlCenterControl::ControlCenterControl(QObject *parent)
    : QObject(parent)
{
}

bool ControlCenterControl::registerOnSessionBus()
{
    QDBusConnection bus = QDBusConnection::sessionBus();
    if (!bus.registerService(QString::fromLatin1(ControlCenterDbus::serviceName))) {
        return false;
    }
    if (bus.registerObject(QString::fromLatin1(ControlCenterDbus::objectPath), this,
                           QDBusConnection::ExportAllSlots)) {
        return true;
    }
    bus.unregisterService(QString::fromLatin1(ControlCenterDbus::serviceName));
    return false;
}

void ControlCenterControl::setWindow(QWindow *window)
{
    m_window = window;
    if (m_pendingShow || m_pendingSettings) {
        present(m_pendingSettings);
    }
}

void ControlCenterControl::ShowControlCenter()
{
    present(false);
}

void ControlCenterControl::ShowSettings()
{
    present(true);
}

bool ControlCenterControl::RequestRunnerAction(const QString &action,
                                               const QString &argument)
{
    const auto request = ProtonVpnKde::validatedRunnerActionRequest(
        action, argument);
    if (!request) {
        return false;
    }
    present(false);
    emit runnerActionRequested(request->action, request->argument);
    return true;
}

void ControlCenterControl::Quit()
{
    QCoreApplication::quit();
}

void ControlCenterControl::present(bool settings)
{
    m_pendingShow = true;
    m_pendingSettings = m_pendingSettings || settings;
    if (!m_window) {
        return;
    }
    if (m_pendingSettings) {
        QMetaObject::invokeMethod(m_window, "showSettings");
    }
    m_pendingShow = false;
    m_pendingSettings = false;
    m_window->show();
    m_window->raise();
    m_window->requestActivate();
}

void ProtonVpnKde::setAgentEnabled(bool enabled)
{
    auto *interface = QDBusConnection::sessionBus().interface();
    const bool registered = interface && interface->isServiceRegistered(
        QString::fromLatin1(AgentDbus::serviceName));
    if (!enabled) {
        if (registered) {
            QDBusConnection::sessionBus().asyncCall(
                agentCall(QString::fromLatin1(AgentDbus::Method::quit)), 2000);
        }
        return;
    }

    auto *watcher = new QDBusPendingCallWatcher(
        QDBusConnection::sessionBus().asyncCall(
            agentCall(QString::fromLatin1(AgentDbus::Method::ensureRunning)), 3000),
        QCoreApplication::instance());
    QObject::connect(watcher, &QDBusPendingCallWatcher::finished,
                     QCoreApplication::instance(),
                     [](QDBusPendingCallWatcher *finished) {
        const QDBusPendingReply<> reply = *finished;
        finished->deleteLater();
        if (!reply.isError()) {
            return;
        }
        QProcess::startDetached(
            siblingExecutable(QStringLiteral("proton-vpn-kde-agent")));
    });
}

void ProtonVpnKde::requestControlCenter(bool settings)
{
    const QString method = settings
        ? QString::fromLatin1(ControlCenterDbus::Method::showSettings)
        : QString::fromLatin1(ControlCenterDbus::Method::showControlCenter);
    auto *watcher = new QDBusPendingCallWatcher(
        QDBusConnection::sessionBus().asyncCall(controlCenterCall(method), 5000),
        QCoreApplication::instance());
    QObject::connect(watcher, &QDBusPendingCallWatcher::finished,
                     QCoreApplication::instance(),
                     [settings](QDBusPendingCallWatcher *finished) {
        const QDBusPendingReply<> reply = *finished;
        finished->deleteLater();
        if (!reply.isError()) {
            return;
        }
        QProcess::startDetached(
            siblingExecutable(QStringLiteral("proton-vpn-kde")),
            {settings ? QStringLiteral("--settings")
                      : QStringLiteral("--show")});
    });
}
