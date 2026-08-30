// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#include "UpdateChannel.h"

#include <QFileInfo>
#include <QProcess>

namespace
{
constexpr auto kRpm = "/usr/bin/rpm";
constexpr auto kPkexec = "/usr/bin/pkexec";
constexpr auto kDnf = "/usr/bin/dnf";
constexpr auto kStablePackage = "protonvpn-stable-release";
constexpr auto kBetaPackage = "protonvpn-beta-release";
}

UpdateChannel::UpdateChannel(QObject *parent)
    : QObject(parent)
    , m_process(new QProcess(this))
{
    m_process->setProcessChannelMode(QProcess::SeparateChannels);
    connect(m_process, &QProcess::finished, this,
            [this](int exitCode, QProcess::ExitStatus) {
                onFinished(exitCode);
            });
    connect(m_process, &QProcess::errorOccurred, this,
            [this](QProcess::ProcessError error) {
                if (error == QProcess::FailedToStart
                    && m_operation != Operation::None) {
                    onFinished(-1);
                }
            });
    refresh();
}

bool UpdateChannel::available() const { return m_available; }
bool UpdateChannel::betaEnabled() const { return m_betaEnabled; }
bool UpdateChannel::busy() const { return m_busy; }
bool UpdateChannel::error() const { return m_error; }
QString UpdateChannel::message() const { return m_message; }

void UpdateChannel::refresh()
{
    if (m_busy) {
        return;
    }
    startQuery();
}

void UpdateChannel::setBetaEnabled(bool enabled)
{
    if (m_busy || !m_available || enabled == m_betaEnabled) {
        return;
    }
    if (!QFileInfo(QString::fromLatin1(kPkexec)).isExecutable()
        || !QFileInfo(QString::fromLatin1(kDnf)).isExecutable()) {
        m_message = tr("The Fedora package tools required to change channels are unavailable");
        m_error = true;
        emit changed();
        return;
    }

    m_operation = enabled ? Operation::SwitchToBeta
                          : Operation::SwitchToStable;
    m_message = enabled ? tr("Enabling Proton VPN Beta access…")
                        : tr("Disabling Proton VPN Beta access…");
    m_error = false;
    setBusy(true);
    m_process->start(QString::fromLatin1(kPkexec), switchArguments(enabled));
}

ProtonPackageChannelState UpdateChannel::packageState(
    const QByteArray &packageQueryOutput)
{
    ProtonPackageChannelState result;
    const QList<QByteArray> lines = packageQueryOutput.split('\n');
    for (const QByteArray &rawLine : lines) {
        const QByteArray line = rawLine.trimmed();
        if (line == kStablePackage) {
            result.available = true;
        } else if (line == kBetaPackage) {
            result.available = true;
            result.betaEnabled = true;
        }
    }
    return result;
}

QStringList UpdateChannel::switchArguments(bool enableBeta)
{
    return {
        QString::fromLatin1(kDnf),
        QStringLiteral("swap"),
        QStringLiteral("-y"),
        QString::fromLatin1(enableBeta ? kStablePackage : kBetaPackage),
        QString::fromLatin1(enableBeta ? kBetaPackage : kStablePackage),
    };
}

void UpdateChannel::startQuery()
{
    if (!QFileInfo(QString::fromLatin1(kRpm)).isExecutable()) {
        m_available = false;
        m_betaEnabled = false;
        if (m_message.isEmpty()) {
            m_message = tr("Proton package-channel detection is unavailable");
            m_error = true;
        }
        emit changed();
        return;
    }
    m_operation = Operation::Query;
    setBusy(true);
    m_process->start(
        QString::fromLatin1(kRpm),
        {QStringLiteral("-q"), QStringLiteral("--qf"),
         QStringLiteral("%{NAME}\\n"), QString::fromLatin1(kStablePackage),
         QString::fromLatin1(kBetaPackage)});
}

void UpdateChannel::onFinished(int exitCode)
{
    const Operation finishedOperation = m_operation;
    m_operation = Operation::None;
    if (finishedOperation == Operation::Query) {
        const ProtonPackageChannelState state = packageState(
            m_process->readAllStandardOutput());
        m_available = state.available
            && QFileInfo(QString::fromLatin1(kPkexec)).isExecutable()
            && QFileInfo(QString::fromLatin1(kDnf)).isExecutable();
        m_betaEnabled = state.betaEnabled;
        if (!state.available && m_message.isEmpty()) {
            m_message = tr("This installation is not managed by Proton's Fedora repository packages");
        }
        setBusy(false);
        return;
    }

    const bool enabling = finishedOperation == Operation::SwitchToBeta;
    if (finishedOperation == Operation::None) {
        setBusy(false);
        return;
    }
    if (exitCode == 0) {
        m_error = false;
        m_message = enabling
            ? tr("Beta access is enabled. Install available updates in Discover, then restart Proton VPN.")
            : tr("Beta access is disabled. Install available updates in Discover, then restart Proton VPN.");
    } else {
        m_error = true;
        m_message = enabling
            ? tr("Beta access could not be enabled")
            : tr("Beta access could not be disabled");
    }
    m_busy = false;
    emit changed();
    startQuery();
}

void UpdateChannel::setBusy(bool busy)
{
    if (m_busy == busy) {
        emit changed();
        return;
    }
    m_busy = busy;
    emit changed();
}
