// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#include "DesktopReadiness.h"

#include <QDBusConnection>
#include <QDBusMessage>
#include <QDBusPendingCallWatcher>
#include <QDBusPendingReply>
#include <QFileInfo>
#include <QProcess>
#include <QSysInfo>
#include <QTimer>

namespace
{
constexpr auto kSecretService = "org.freedesktop.secrets";
constexpr auto kCoreCapability = "proton-vpn-api-core-plasma-protun-secret";
constexpr auto kKeyringCapability = "proton-keyring-secret-service-owner-pinned";

QDBusMessage busQuery(const QString &method)
{
    return QDBusMessage::createMethodCall(
        QStringLiteral("org.freedesktop.DBus"),
        QStringLiteral("/org/freedesktop/DBus"),
        QStringLiteral("org.freedesktop.DBus"), method);
}
}

DesktopReadiness::DesktopReadiness(QObject *parent)
    : QObject(parent)
    , m_packageQuery(new QProcess(this))
    , m_packageTimeout(new QTimer(this))
{
    m_packageQuery->setProcessChannelMode(QProcess::SeparateChannels);
    m_packageTimeout->setSingleShot(true);
    connect(m_packageTimeout, &QTimer::timeout, this, [this] {
        m_packageTimedOut = true;
        m_packageQuery->kill();
        setPackageCapabilityStates(QStringLiteral("unknown"),
                                   QStringLiteral("unknown"));
    });
    connect(m_packageQuery, &QProcess::finished, this,
            [this](int exitCode, QProcess::ExitStatus exitStatus) {
        m_packageTimeout->stop();
        if (m_packageTimedOut || exitStatus != QProcess::NormalExit) {
            setPackageCapabilityStates(QStringLiteral("unknown"),
                                       QStringLiteral("unknown"));
            return;
        }
        const QByteArray output = m_packageQuery->readAllStandardOutput().left(65536);
        if (exitCode != 0 && output.isEmpty()) {
            setPackageCapabilityStates(QStringLiteral("unknown"),
                                       QStringLiteral("unknown"));
            return;
        }
        setPackageCapabilityStates(
            containsPackageCapability(output, QByteArray(kCoreCapability))
                ? QStringLiteral("present") : QStringLiteral("missing"),
            containsPackageCapability(output, QByteArray(kKeyringCapability))
                ? QStringLiteral("present") : QStringLiteral("missing"));
    });
    connect(m_packageQuery, &QProcess::errorOccurred, this,
            [this](QProcess::ProcessError error) {
        if (error == QProcess::FailedToStart) {
            m_packageTimeout->stop();
            setPackageCapabilityStates(QStringLiteral("unknown"),
                                       QStringLiteral("unknown"));
        }
    });
}

DesktopReadiness::~DesktopReadiness()
{
    if (m_packageQuery->state() != QProcess::NotRunning) {
        m_packageQuery->kill();
        m_packageQuery->waitForFinished(500);
    }
}

QString DesktopReadiness::secretServiceState() const
{
    return m_secretServiceState;
}

QString DesktopReadiness::coreCapabilityState() const
{
    return m_coreCapabilityState;
}

QString DesktopReadiness::keyringCapabilityState() const
{
    return m_keyringCapabilityState;
}

bool DesktopReadiness::containsPackageCapability(
    const QByteArray &output, const QByteArray &capability)
{
    if (capability.isEmpty()) {
        return false;
    }
    const QByteArray rpmPrefix = capability + " = ";
    const QByteArray dpkgPrefix = capability + " (= ";
    for (const QByteArray &line : output.split('\n')) {
        for (const QByteArray &entry : line.split(',')) {
            const QByteArray candidate = entry.trimmed();
            QByteArray version;
            if (candidate.startsWith(rpmPrefix)) {
                version = candidate.mid(rpmPrefix.size());
            } else if (candidate.startsWith(dpkgPrefix)
                       && candidate.endsWith(')')) {
                version = candidate.mid(
                    dpkgPrefix.size(),
                    candidate.size() - dpkgPrefix.size() - 1);
            }
            bool numeric = false;
            const uint revision = version.toUInt(&numeric);
            if (numeric && revision >= 1) {
                return true;
            }
        }
    }
    return false;
}

QString DesktopReadiness::classifySecretService(
    const QStringList &registeredNames,
    const QStringList &activatableNames)
{
    const QString name = QString::fromLatin1(kSecretService);
    if (registeredNames.contains(name)) {
        return QStringLiteral("running");
    }
    return activatableNames.contains(name) ? QStringLiteral("activatable")
                                           : QStringLiteral("missing");
}

void DesktopReadiness::setSecretServiceState(const QString &state)
{
    if (m_secretServiceState == state) {
        return;
    }
    m_secretServiceState = state;
    emit changed();
}

void DesktopReadiness::setPackageCapabilityStates(const QString &core,
                                                   const QString &keyring)
{
    if (m_coreCapabilityState == core && m_keyringCapabilityState == keyring) {
        return;
    }
    m_coreCapabilityState = core;
    m_keyringCapabilityState = keyring;
    emit changed();
}

void DesktopReadiness::refreshPackageCapabilities()
{
    if (m_packageQuery->state() != QProcess::NotRunning) {
        return;
    }
    QString program;
    QStringList arguments;
    const QString os = QSysInfo::productType();
    if (os == QStringLiteral("fedora")) {
        program = QStringLiteral("/usr/bin/rpm");
        arguments = {QStringLiteral("-q"), QStringLiteral("--provides"),
                     QStringLiteral("python3-proton-vpn-api-core"),
                     QStringLiteral("python3-proton-keyring-linux")};
    } else if (os == QStringLiteral("ubuntu")) {
        program = QStringLiteral("/usr/bin/dpkg-query");
        arguments = {QStringLiteral("-W"),
                     QStringLiteral("-f=${Provides}\\n"),
                     QStringLiteral("python3-proton-vpn-api-core"),
                     QStringLiteral("python3-proton-keyring-linux")};
    }
    if (program.isEmpty() || !QFileInfo(program).isExecutable()) {
        setPackageCapabilityStates(QStringLiteral("unknown"),
                                   QStringLiteral("unknown"));
        return;
    }
    m_packageTimedOut = false;
    setPackageCapabilityStates(QStringLiteral("checking"),
                               QStringLiteral("checking"));
    m_packageQuery->start(program, arguments);
    m_packageTimeout->start(3000);
}

void DesktopReadiness::refresh()
{
    refreshPackageCapabilities();
    const quint64 generation = ++m_generation;
    const QDBusConnection bus = QDBusConnection::sessionBus();
    if (!bus.isConnected()) {
        setSecretServiceState(QStringLiteral("unknown"));
        return;
    }
    setSecretServiceState(QStringLiteral("checking"));

    // Query only the session bus daemon. Never call or activate the Secret
    // Service itself: even a harmless-looking collection read can prompt.
    auto *namesWatcher = new QDBusPendingCallWatcher(
        bus.asyncCall(busQuery(QStringLiteral("ListNames")), 2000), this);
    connect(namesWatcher, &QDBusPendingCallWatcher::finished, this,
            [this, bus, generation](QDBusPendingCallWatcher *finished) {
        const QDBusPendingReply<QStringList> namesReply = *finished;
        finished->deleteLater();
        if (generation != m_generation) {
            return;
        }
        if (namesReply.isError()) {
            setSecretServiceState(QStringLiteral("unknown"));
            return;
        }
        const QStringList registeredNames = namesReply.value();
        if (registeredNames.contains(QString::fromLatin1(kSecretService))) {
            setSecretServiceState(QStringLiteral("running"));
            return;
        }

        auto *activationWatcher = new QDBusPendingCallWatcher(
            bus.asyncCall(busQuery(QStringLiteral("ListActivatableNames")),
                          2000), this);
        connect(activationWatcher, &QDBusPendingCallWatcher::finished, this,
                [this, generation, registeredNames](QDBusPendingCallWatcher *replyWatcher) {
            const QDBusPendingReply<QStringList> activationReply = *replyWatcher;
            replyWatcher->deleteLater();
            if (generation != m_generation) {
                return;
            }
            if (activationReply.isError()) {
                setSecretServiceState(QStringLiteral("unknown"));
                return;
            }
            setSecretServiceState(classifySecretService(
                registeredNames, activationReply.value()));
        });
    });
}
