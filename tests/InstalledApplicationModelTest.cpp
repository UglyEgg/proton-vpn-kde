#include "InstalledApplicationModel.h"

#include <QtTest>

class InstalledApplicationModelTest final : public QObject
{
    Q_OBJECT

private slots:
    void resolvesNativeExecutable();
    void preservesFlatpakLaunchPrefix();
    void convertsSnapLauncherPrefix();
    void rejectsShellSyntaxAndVpnClients();
};

void InstalledApplicationModelTest::resolvesNativeExecutable()
{
    QCOMPARE(
        InstalledApplicationModel::executableFromExecLine(
            QStringLiteral("/usr/bin/firefox %u")),
        QStringLiteral("/usr/bin/firefox"));
}

void InstalledApplicationModelTest::preservesFlatpakLaunchPrefix()
{
    QCOMPARE(
        InstalledApplicationModel::executableFromExecLine(QStringLiteral(
            "/usr/bin/flatpak run --branch=stable org.example.App @@u %U @@")),
        QStringLiteral(
            "/usr/bin/flatpak run --branch=stable org.example.App"));
}

void InstalledApplicationModelTest::convertsSnapLauncherPrefix()
{
    QCOMPARE(
        InstalledApplicationModel::executableFromExecLine(
            QStringLiteral("/snap/bin/firefox.firefox %u")),
        QStringLiteral("/snap/firefox/"));
}

void InstalledApplicationModelTest::rejectsShellSyntaxAndVpnClients()
{
    QVERIFY(InstalledApplicationModel::executableFromExecLine(
                QStringLiteral("/usr/bin/firefox; /usr/bin/other"))
                .isEmpty());
    QVERIFY(!InstalledApplicationModel::isSafeVpnApplicationChoice(
        QStringLiteral("/usr/bin/proton-vpn-kde")));
    QVERIFY(!InstalledApplicationModel::isSafeVpnApplicationChoice(
        QStringLiteral("/usr/bin/protonvpn-app")));
}

QTEST_GUILESS_MAIN(InstalledApplicationModelTest)

#include "InstalledApplicationModelTest.moc"
