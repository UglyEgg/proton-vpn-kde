#include "BackendIdentity.h"

#include <QFile>
#include <QTemporaryDir>
#include <QTest>

class BackendIdentityTest : public QObject
{
    Q_OBJECT

private Q_SLOTS:
    void emptyDropInListIsTrusted()
    {
        QVERIFY(ProtonVpnKde::areRootOwnedImmutableFiles({}));
    }

    void rootOwnedImmutableDropInIsTrusted()
    {
        const QString systemdDropIn = QStringLiteral(
            "/usr/lib/systemd/user/service.d/10-timeout-abort.conf");
        if (!QFile::exists(systemdDropIn)) {
            QSKIP("Fedora's systemd user-service drop-in is not installed");
        }

        if (!ProtonVpnKde::isRootOwnedImmutableFile(systemdDropIn)) {
            QSKIP("Host ownership is remapped in this test environment");
        }
        QVERIFY(ProtonVpnKde::areRootOwnedImmutableFiles({systemdDropIn}));
    }

    void userOwnedDropInIsRejected()
    {
        QTemporaryDir directory;
        QVERIFY(directory.isValid());
        const QString path = directory.filePath(QStringLiteral("override.conf"));
        QFile file(path);
        QVERIFY(file.open(QIODevice::WriteOnly));
        QVERIFY(file.write("[Service]\nExecStart=/tmp/impostor\n") > 0);
        file.close();

        QVERIFY(!ProtonVpnKde::isRootOwnedImmutableFile(path));
        QVERIFY(!ProtonVpnKde::areRootOwnedImmutableFiles({path}));
    }

    void mixedDropInListIsRejected()
    {
        const QString systemdDropIn = QStringLiteral(
            "/usr/lib/systemd/user/service.d/10-timeout-abort.conf");
        if (!QFile::exists(systemdDropIn)) {
            QSKIP("Fedora's systemd user-service drop-in is not installed");
        }

        QTemporaryDir directory;
        QVERIFY(directory.isValid());
        const QString userDropIn = directory.filePath(QStringLiteral("override.conf"));
        QFile file(userDropIn);
        QVERIFY(file.open(QIODevice::WriteOnly));
        file.close();

        QVERIFY(!ProtonVpnKde::areRootOwnedImmutableFiles(
            {systemdDropIn, userDropIn}));
    }
};

QTEST_GUILESS_MAIN(BackendIdentityTest)

#include "BackendIdentityTest.moc"
