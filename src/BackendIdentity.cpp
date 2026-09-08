// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#include "BackendIdentity.h"
#include "UnsafeBackendEnvironment.generated.h"

#include <algorithm>
#include <QDBusConnection>
#include <QDBusMessage>
#include <QDBusPendingCallWatcher>
#include <QDBusPendingReply>
#include <QDBusReply>
#include <QDBusVariant>
#include <QCoreApplication>
#include <QFile>
#include <QFileInfo>
#include <QTimer>
#include <utility>

#include <unistd.h>

#ifndef PROTON_VPN_KDE_BACKEND_EXECUTABLE_PATH
#define PROTON_VPN_KDE_BACKEND_EXECUTABLE_PATH "/usr/bin/proton-vpn-kde-backend"
#endif

#ifndef PROTON_VPN_KDE_BACKEND_UNIT_PATH
#define PROTON_VPN_KDE_BACKEND_UNIT_PATH "/usr/lib/systemd/user/proton-vpn-kde-backend.service"
#endif

namespace
{
constexpr auto kSystemdService = "org.freedesktop.systemd1";
constexpr auto kSystemdUnitPath =
    "/org/freedesktop/systemd1/unit/proton_2dvpn_2dkde_2dbackend_2eservice";
constexpr auto kPropertiesInterface = "org.freedesktop.DBus.Properties";
constexpr auto kServiceInterface = "org.freedesktop.systemd1.Service";
constexpr auto kUnitInterface = "org.freedesktop.systemd1.Unit";

bool processUsesExpectedLauncher(quint64 pid, const QString &launcher)
{
    QFile cmdline(QStringLiteral("/proc/%1/cmdline").arg(pid));
    if (!cmdline.open(QIODevice::ReadOnly)) {
        return false;
    }
    const QList<QByteArray> arguments = cmdline.readAll().split('\0');
    const QByteArray expected = QFile::encodeName(launcher);
    return std::find(arguments.cbegin(), arguments.cend(), expected)
        != arguments.cend();
}

bool processEnvironmentIsSafe(quint64 pid)
{
    QFile environment(QStringLiteral("/proc/%1/environ").arg(pid));
    if (!environment.open(QIODevice::ReadOnly)) {
        return false;
    }
    return ProtonVpnKde::isBackendEnvironmentSafe(environment.readAll());
}
}

bool ProtonVpnKde::isBackendEnvironmentSafe(const QByteArray &environment)
{
    const QList<QByteArray> entries = environment.split('\0');
    for (const QByteArray &entry : entries) {
        for (const std::string_view prefix : kUnsafeBackendEnvironmentPrefixes) {
            if (entry.size() >= static_cast<qsizetype>(prefix.size())
                && std::equal(prefix.cbegin(), prefix.cend(), entry.cbegin())) {
                return false;
            }
        }
    }
    return true;
}

bool ProtonVpnKde::isRootOwnedImmutableFile(const QString &path)
{
    const QFileInfo info(path);
    if (!info.exists() || !info.isFile() || info.symLinkTarget().size() > 0
        || info.ownerId() != 0) {
        return false;
    }
    const QFileDevice::Permissions permissions = info.permissions();
    return !(permissions & QFileDevice::WriteGroup)
        && !(permissions & QFileDevice::WriteOther);
}

bool ProtonVpnKde::areRootOwnedImmutableFiles(const QStringList &paths)
{
    return std::all_of(paths.cbegin(), paths.cend(), [](const QString &path) {
        return isRootOwnedImmutableFile(path);
    });
}

namespace
{
// One owner-scoped transaction, with one total deadline. No QDBusInterface
// construction/introspection or synchronous RPC runs on the UI thread.
class IdentityCheck final : public QObject
{
public:
    IdentityCheck(const QDBusConnection &bus, QString name, QObject *context,
                  std::function<void(ProtonVpnKde::BackendIdentityResult)> completed)
        : QObject(context), m_bus(bus), m_name(std::move(name)),
          m_completed(std::move(completed))
    {
        QTimer::singleShot(5000, this, [this] { finish(false); });
        request();
    }

private:
    enum Stage { Owner, Uid, Pid, MainPid, Fragment, DropIns, FinalOwner };

    void finish(bool trusted)
    {
        if (m_done) {
            return;
        }
        m_done = true;
        m_result.trusted = trusted;
        if (!trusted) {
            m_result.error = QStringLiteral("The backend identity could not be verified");
        }
        auto completed = std::move(m_completed);
        deleteLater();
        completed(m_result);
    }

    void request()
    {
        QDBusMessage message;
        if (m_step == Owner || m_step == FinalOwner || m_step == Uid || m_step == Pid) {
            const QString method = m_step == Uid
                ? QStringLiteral("GetConnectionUnixUser")
                : m_step == Pid ? QStringLiteral("GetConnectionUnixProcessID")
                              : QStringLiteral("GetNameOwner");
            message = QDBusMessage::createMethodCall(
                QStringLiteral("org.freedesktop.DBus"),
                QStringLiteral("/org/freedesktop/DBus"),
                QStringLiteral("org.freedesktop.DBus"), method);
            message << ((m_step == Owner || m_step == FinalOwner) ? m_name : m_result.uniqueOwner);
        } else {
            message = QDBusMessage::createMethodCall(
                QString::fromLatin1(kSystemdService),
                QString::fromLatin1(kSystemdUnitPath),
                QString::fromLatin1(kPropertiesInterface), QStringLiteral("Get"));
            message << QString::fromLatin1(m_step == MainPid ? kServiceInterface : kUnitInterface)
                    << (m_step == MainPid ? QStringLiteral("MainPID")
                        : m_step == Fragment ? QStringLiteral("FragmentPath")
                                      : QStringLiteral("DropInPaths"));
        }
        auto *watcher = new QDBusPendingCallWatcher(m_bus.asyncCall(message, 5000), this);
        connect(watcher, &QDBusPendingCallWatcher::finished, this,
                [this](QDBusPendingCallWatcher *finished) {
            const QDBusMessage reply = finished->reply();
            finished->deleteLater();
            if (!m_done) {
                accept(reply);
            }
        });
    }

    void accept(const QDBusMessage &message)
    {
        if (message.type() != QDBusMessage::ReplyMessage) {
            finish(false);
            return;
        }
        if (m_step == Owner || m_step == FinalOwner) {
            const QDBusReply<QString> reply(message);
            if (!reply.isValid() || !reply.value().startsWith(QLatin1Char(':'))) {
                finish(false);
                return;
            }
            if (m_step == FinalOwner) {
                finish(reply.value() == m_result.uniqueOwner);
                return;
            }
            m_result.uniqueOwner = reply.value();
            const QByteArray testOwner = qgetenv("PROTON_VPN_KDE_TEST_BACKEND_OWNER");
            if (!testOwner.isEmpty()
                && QString::fromUtf8(testOwner) == m_result.uniqueOwner
                && !ProtonVpnKde::isRootOwnedImmutableFile(
                    QFileInfo(QCoreApplication::applicationFilePath()).canonicalFilePath())) {
                // Installed, root-owned applications cannot take this test path.
                finish(true);
                return;
            }
        } else if (m_step == Uid || m_step == Pid) {
            const QDBusReply<uint> reply(message);
            if (!reply.isValid()
                || (m_step == Uid && reply.value() != static_cast<uint>(::geteuid()))
                || (m_step == Pid && reply.value() <= 1)) {
                finish(false);
                return;
            }
            if (m_step == Pid) {
                m_pid = reply.value();
            }
        } else {
            const QDBusReply<QDBusVariant> reply(message);
            if (!reply.isValid()) {
                finish(false);
                return;
            }
            const QVariant value = reply.value().variant();
            if (m_step == MainPid) {
                m_mainPid = value.toULongLong();
            } else if (m_step == Fragment) {
                m_fragment = value.toString();
            } else {
                const QString launcher = QString::fromUtf8(PROTON_VPN_KDE_BACKEND_EXECUTABLE_PATH);
                const QString unit = QString::fromUtf8(PROTON_VPN_KDE_BACKEND_UNIT_PATH);
                if (m_mainPid != m_pid || m_fragment != unit || !value.isValid()
                    || !value.canConvert<QStringList>()
                    || !ProtonVpnKde::areRootOwnedImmutableFiles(value.toStringList())
                    || !ProtonVpnKde::isRootOwnedImmutableFile(unit)
                    || !ProtonVpnKde::isRootOwnedImmutableFile(launcher)
                    || !processUsesExpectedLauncher(m_pid, launcher)
                    || !processEnvironmentIsSafe(m_pid)) {
                    finish(false);
                    return;
                }
            }
        }
        m_step = static_cast<Stage>(m_step + 1);
        request();
    }

    QDBusConnection m_bus;
    QString m_name;
    std::function<void(ProtonVpnKde::BackendIdentityResult)> m_completed;
    ProtonVpnKde::BackendIdentityResult m_result;
    quint64 m_pid = 0;
    quint64 m_mainPid = 0;
    QString m_fragment;
    Stage m_step = Owner;
    bool m_done = false;
};
}

void ProtonVpnKde::verifyBackendIdentity(
    const QDBusConnection &bus, const QString &wellKnownName, QObject *context,
    std::function<void(BackendIdentityResult)> completed)
{
    new IdentityCheck(bus, wellKnownName, context, std::move(completed));
}

void ProtonVpnKde::discoverBackendService(
    const QDBusConnection &bus, const QString &wellKnownName, bool activate,
    QObject *context, std::function<void(bool)> completed)
{
    QDBusMessage query = QDBusMessage::createMethodCall(
        QStringLiteral("org.freedesktop.DBus"), QStringLiteral("/org/freedesktop/DBus"),
        QStringLiteral("org.freedesktop.DBus"), QStringLiteral("NameHasOwner"));
    query << wellKnownName;
    auto *watcher = new QDBusPendingCallWatcher(bus.asyncCall(query, 5000), context);
    QObject::connect(watcher, &QDBusPendingCallWatcher::finished, context,
        [bus, wellKnownName, activate, context, completed = std::move(completed)]
        (QDBusPendingCallWatcher *finished) {
            const QDBusPendingReply<bool> reply = *finished;
            finished->deleteLater();
            if (reply.isError() || reply.value() || !activate) {
                completed(!reply.isError() && reply.value());
                return;
            }
            // A manually started owner need not have an activation file.
            // Ask for activation only when the read confirmed it is absent.
            QDBusMessage start = QDBusMessage::createMethodCall(
                QStringLiteral("org.freedesktop.DBus"), QStringLiteral("/org/freedesktop/DBus"),
                QStringLiteral("org.freedesktop.DBus"), QStringLiteral("StartServiceByName"));
            start << wellKnownName << uint{0};
            auto *activation = new QDBusPendingCallWatcher(bus.asyncCall(start, 5000), context);
            QObject::connect(activation, &QDBusPendingCallWatcher::finished, context,
                [completed = std::move(completed)](QDBusPendingCallWatcher *activated) {
                    const QDBusPendingReply<uint> result = *activated;
                    activated->deleteLater();
                    completed(!result.isError() && (result.value() == 1 || result.value() == 2));
                });
        });
}
