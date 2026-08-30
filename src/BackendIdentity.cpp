#include "BackendIdentity.h"

#include <algorithm>
#include <QDBusConnection>
#include <QDBusConnectionInterface>
#include <QDBusInterface>
#include <QDBusReply>
#include <QDBusVariant>
#include <QCoreApplication>
#include <QFile>
#include <QFileInfo>
#include <QVariantMap>

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

QVariant getProperty(const QDBusConnection &bus, const QString &interface,
                     const QString &name)
{
    QDBusInterface properties(QString::fromLatin1(kSystemdService),
                              QString::fromLatin1(kSystemdUnitPath),
                              QString::fromLatin1(kPropertiesInterface), bus);
    const QDBusReply<QDBusVariant> reply = properties.call(
        QStringLiteral("Get"), interface, name);
    return reply.isValid() ? reply.value().variant() : QVariant{};
}

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
    static const QList<QByteArray> blocked{
        QByteArrayLiteral("LD_PRELOAD="),
        QByteArrayLiteral("LD_AUDIT="),
        QByteArrayLiteral("LD_LIBRARY_PATH="),
        QByteArrayLiteral("PYTHONPATH="),
        QByteArrayLiteral("PYTHONHOME="),
    };
    const QList<QByteArray> entries = environment.readAll().split('\0');
    return std::none_of(entries.cbegin(), entries.cend(), [](const QByteArray &entry) {
        return std::any_of(blocked.cbegin(), blocked.cend(),
                           [&entry](const QByteArray &prefix) {
            return entry.startsWith(prefix);
        });
    });
}
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

ProtonVpnKde::BackendIdentityResult ProtonVpnKde::verifyBackendIdentity(
    const QDBusConnection &bus, const QString &wellKnownName)
{
    BackendIdentityResult result;
    QDBusConnectionInterface *interface = bus.interface();
    if (!interface) {
        result.error = QStringLiteral("The session bus is unavailable");
        return result;
    }

    const QDBusReply<QString> ownerReply = interface->serviceOwner(wellKnownName);
    if (!ownerReply.isValid() || !ownerReply.value().startsWith(QLatin1Char(':'))) {
        result.error = QStringLiteral("The backend has no unique bus owner");
        return result;
    }
    result.uniqueOwner = ownerReply.value();

    const QByteArray testOwner = qgetenv("PROTON_VPN_KDE_TEST_BACKEND_OWNER");
    if (!testOwner.isEmpty()
        && QString::fromUtf8(testOwner) == result.uniqueOwner
        && !isRootOwnedImmutableFile(
            QFileInfo(QCoreApplication::applicationFilePath())
                .canonicalFilePath())) {
        // This pin exists only for user-owned build-tree test executables.
        // Installed root-owned applications always take the systemd trust path.
        result.trusted = true;
        return result;
    }

    const QDBusReply<uint> uidReply = interface->serviceUid(result.uniqueOwner);
    const QDBusReply<uint> pidReply = interface->servicePid(result.uniqueOwner);
    if (!uidReply.isValid() || !pidReply.isValid()
        || uidReply.value() != static_cast<uint>(::geteuid())
        || pidReply.value() <= 1) {
        result.error = QStringLiteral("The backend process identity is unavailable");
        return result;
    }

    const quint64 mainPid = getProperty(
        bus, QString::fromLatin1(kServiceInterface),
        QStringLiteral("MainPID")).toULongLong();
    const QString fragmentPath = getProperty(
        bus, QString::fromLatin1(kUnitInterface),
        QStringLiteral("FragmentPath")).toString();
    const QVariant dropInsProperty = getProperty(
        bus, QString::fromLatin1(kUnitInterface),
        QStringLiteral("DropInPaths"));
    const QStringList dropIns = dropInsProperty.toStringList();
    const QString expectedLauncher = QString::fromUtf8(
        PROTON_VPN_KDE_BACKEND_EXECUTABLE_PATH);
    const QString expectedUnit = QString::fromUtf8(PROTON_VPN_KDE_BACKEND_UNIT_PATH);
    if (mainPid != pidReply.value() || fragmentPath != expectedUnit
        || !dropInsProperty.isValid()
        || !dropInsProperty.canConvert<QStringList>()
        || !areRootOwnedImmutableFiles(dropIns)
        || !isRootOwnedImmutableFile(expectedUnit)
        || !isRootOwnedImmutableFile(expectedLauncher)
        || !processUsesExpectedLauncher(pidReply.value(), expectedLauncher)
        || !processEnvironmentIsSafe(pidReply.value())) {
        result.error = QStringLiteral(
            "The backend is not the packaged systemd service");
        return result;
    }

    // Re-resolve after filesystem and systemd checks to close the owner-change
    // window. Every later application call is addressed to this unique owner.
    const QDBusReply<QString> finalOwner = interface->serviceOwner(wellKnownName);
    if (!finalOwner.isValid() || finalOwner.value() != result.uniqueOwner) {
        result.uniqueOwner.clear();
        result.error = QStringLiteral("The backend changed during verification");
        return result;
    }
    result.trusted = true;
    return result;
}
