// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#include "AgentControl.h"
#include "BackendIdentity.h"
#include "InstalledExecutablePaths.h"
#include "RunnerActionRequest.h"

#include <QCoreApplication>
#include <QDBusConnection>
#include <QDBusConnectionInterface>
#include <QDBusError>
#include <QDBusMessage>
#include <QDBusPendingCallWatcher>
#include <QDBusPendingReply>
#include <QDBusReply>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QProcess>
#include <QWindow>

#include <unistd.h>

namespace
{
namespace AgentDbus = ProtonVpnKde::DBusContract::Agent;
namespace ControlCenterDbus = ProtonVpnKde::DBusContract::ControlCenter;

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
                           QDBusConnection::ExportScriptableSlots)) {
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
    if (!callerIsControlCenter()) {
        sendErrorReply(QDBusError::AccessDenied,
                       QStringLiteral("Only the packaged Control Center may "
                                      "stop background controls"));
        return;
    }
    QCoreApplication::quit();
}

bool AgentControl::callerIsControlCenter() const
{
    if (!calledFromDBus()) {
        return false;
    }
    const QDBusConnection bus = connection();
    QDBusConnectionInterface *interface = bus.interface();
    const QString sender = message().service();
    if (!interface || !sender.startsWith(QLatin1Char(':'))) {
        return false;
    }
    const QDBusReply<QString> ownerReply = interface->serviceOwner(
        QString::fromLatin1(ControlCenterDbus::serviceName));
    const QDBusReply<uint> uidReply = interface->serviceUid(sender);
    const QDBusReply<uint> pidReply = interface->servicePid(sender);
    if (!ownerReply.isValid() || ownerReply.value() != sender
        || !uidReply.isValid() || !pidReply.isValid()
        || uidReply.value() != static_cast<uint>(::geteuid())
        || pidReply.value() <= 1) {
        return false;
    }

    const QString runningAgent = QFileInfo(
        QCoreApplication::applicationFilePath()).canonicalFilePath();
    QString expectedControlCenter = ProtonVpnKde::controlCenterExecutablePath();
    if (ProtonVpnKde::isRootOwnedImmutableFile(runningAgent)) {
        if (!ProtonVpnKde::isRootOwnedImmutableFile(expectedControlCenter)) {
            return false;
        }
    } else {
        // Build-tree integration tests use adjacent user-owned executables.
        // Installed agents always take the root-owned packaged path above.
        expectedControlCenter = QFileInfo(runningAgent).dir().filePath(
            QStringLiteral("proton-vpn-kde"));
    }
    const QString callerExecutable = QFileInfo(
        QStringLiteral("/proc/%1/exe").arg(pidReply.value()))
                                         .canonicalFilePath();
    if (callerExecutable.isEmpty()
        || callerExecutable != QFileInfo(expectedControlCenter).canonicalFilePath()) {
        return false;
    }
    QFile environment(QStringLiteral("/proc/%1/environ").arg(pidReply.value()));
    if (!environment.open(QIODevice::ReadOnly)
        || !ProtonVpnKde::isBackendEnvironmentSafe(environment.readAll())) {
        return false;
    }
    const QDBusReply<QString> finalOwner = interface->serviceOwner(
        QString::fromLatin1(ControlCenterDbus::serviceName));
    return finalOwner.isValid() && finalOwner.value() == sender;
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
                           QDBusConnection::ExportScriptableSlots)) {
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
    if (!enabled) {
        QDBusConnection::sessionBus().asyncCall(
            agentCall(QString::fromLatin1(AgentDbus::Method::quit)), 2000);
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
            ProtonVpnKde::agentExecutablePath());
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
            ProtonVpnKde::controlCenterExecutablePath(),
            {settings ? QStringLiteral("--settings")
                      : QStringLiteral("--show")});
    });
}

void ProtonVpnKde::requestConfirmedControlCenterAction(
    const QString &action, const QString &argument)
{
    QDBusMessage message = controlCenterCall(
        QString::fromLatin1(ControlCenterDbus::Method::requestRunnerAction));
    message.setArguments({action, argument});
    auto *watcher = new QDBusPendingCallWatcher(
        QDBusConnection::sessionBus().asyncCall(message, 5000),
        QCoreApplication::instance());
    QObject::connect(watcher, &QDBusPendingCallWatcher::finished,
                     QCoreApplication::instance(),
                     [](QDBusPendingCallWatcher *finished) {
        const QDBusPendingReply<bool> reply = *finished;
        finished->deleteLater();
        if (reply.isError() || !reply.value()) {
            qWarning("Unable to present the VPN action confirmation");
        }
    });
}
