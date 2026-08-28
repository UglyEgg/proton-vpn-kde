#include <KRunner/AbstractRunnerTest>

#include <QDBusConnection>
#include <QSignalSpy>
#include <QTest>

class BackendStub final : public QObject
{
    Q_OBJECT
    Q_CLASSINFO("D-Bus Interface", "proton.vpn.app.kde.Backend1")

public slots:
    void ConnectFastest() { emit operationRequested(QStringLiteral("fastest"), {}); }
    void Disconnect() { emit operationRequested(QStringLiteral("disconnect"), {}); }
    void ConnectCountry(const QString &country)
    {
        emit operationRequested(QStringLiteral("country"), country);
    }
    void ConnectServer(const QString &server)
    {
        emit operationRequested(QStringLiteral("server"), server);
    }

signals:
    void operationRequested(const QString &operation, const QString &argument);
};

class ProtonVpnRunnerTest final : public KRunner::AbstractRunnerTest
{
    Q_OBJECT

private slots:
    void initTestCase();
    void showsPrimaryActions();
    void showsCountryAction();
    void ignoresUnrelatedQueries();
    void dispatchesBackendActions_data();
    void dispatchesBackendActions();

private:
    BackendStub m_backend;
};

void ProtonVpnRunnerTest::initTestCase()
{
    QDBusConnection bus = QDBusConnection::sessionBus();
    QVERIFY(bus.registerService(QStringLiteral("proton.vpn.app.kde.backend")));
    QVERIFY(bus.registerObject(QStringLiteral("/proton/vpn/app/kde/backend"),
                               &m_backend,
                               QDBusConnection::ExportAllSlots));
    initProperties();
}

void ProtonVpnRunnerTest::showsPrimaryActions()
{
    const QList<KRunner::QueryMatch> matches = launchQuery(QStringLiteral("vpn"));
    QCOMPARE(matches.size(), 3);
    QCOMPARE(matches.at(0).text(), QStringLiteral("Open Proton VPN"));
    QCOMPARE(matches.at(1).text(), QStringLiteral("Connect Proton VPN"));
    QCOMPARE(matches.at(2).text(), QStringLiteral("Disconnect Proton VPN"));
}

void ProtonVpnRunnerTest::showsCountryAction()
{
    const QList<KRunner::QueryMatch> matches =
        launchQuery(QStringLiteral("vpn connect ch"));
    QCOMPARE(matches.size(), 1);
    QCOMPARE(matches.constFirst().text(),
             QStringLiteral("Connect Proton VPN to CH"));
}

void ProtonVpnRunnerTest::ignoresUnrelatedQueries()
{
    QVERIFY(launchQuery(QStringLiteral("ordinary search")).isEmpty());
}

void ProtonVpnRunnerTest::dispatchesBackendActions_data()
{
    QTest::addColumn<QString>("query");
    QTest::addColumn<QString>("operation");
    QTest::addColumn<QString>("argument");

    QTest::newRow("fastest") << QStringLiteral("vpn fastest")
                              << QStringLiteral("fastest") << QString();
    QTest::newRow("disconnect") << QStringLiteral("vpn disconnect")
                                 << QStringLiteral("disconnect") << QString();
    QTest::newRow("country") << QStringLiteral("vpn country ch")
                              << QStringLiteral("country") << QStringLiteral("CH");
    QTest::newRow("server") << QStringLiteral("vpn server us-ca#18")
                             << QStringLiteral("server")
                             << QStringLiteral("US-CA#18");
}

void ProtonVpnRunnerTest::dispatchesBackendActions()
{
    QFETCH(QString, query);
    QFETCH(QString, operation);
    QFETCH(QString, argument);

    const QList<KRunner::QueryMatch> matches = launchQuery(query);
    QCOMPARE(matches.size(), 1);
    QSignalSpy spy(&m_backend, &BackendStub::operationRequested);
    KRunner::RunnerContext context;
    runner->run(context, matches.constFirst());
    QTRY_COMPARE(spy.count(), 1);
    QCOMPARE(spy.constFirst().at(0).toString(), operation);
    QCOMPARE(spy.constFirst().at(1).toString(), argument);
}

QTEST_GUILESS_MAIN(ProtonVpnRunnerTest)

#include "ProtonVpnRunnerTest.moc"
