// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#include <KRunner/AbstractRunnerTest>

#include <QDBusConnection>
#include <QDBusConnectionInterface>
#include <QSignalSpy>
#include <QTest>

class ControlCenterStub final : public QObject
{
    Q_OBJECT
    Q_CLASSINFO("D-Bus Interface", "quest.entropy.PlasmaVPN.ControlCenter1")

public slots:
    void ShowControlCenter()
    {
        emit actionRequested(QStringLiteral("open"), {});
    }
    bool RequestRunnerAction(const QString &action, const QString &argument)
    {
        emit actionRequested(action, argument);
        return true;
    }

signals:
    void actionRequested(const QString &action, const QString &argument);
};

class BackendTrap final : public QObject
{
    Q_OBJECT
    Q_CLASSINFO("D-Bus Interface", "quest.entropy.PlasmaVPN.Backend1")

public:
    int calls = 0;

public slots:
    void AuthorizeClient(const QString &) { ++calls; }
    void ConnectFastest() { ++calls; }
    void ConnectFastestWithFeatures(const QStringList &) { ++calls; }
    void Disconnect() { ++calls; }
    void ConnectCountry(const QString &) { ++calls; }
    void ConnectServer(const QString &) { ++calls; }
};

class ProtonVpnRunnerTest final : public KRunner::AbstractRunnerTest
{
    Q_OBJECT

private slots:
    void initTestCase();
    void showsPrimaryActions();
    void showsCountryAction();
    void ignoresUnrelatedQueries();
    void dispatchesControlCenterActions_data();
    void dispatchesControlCenterActions();

private:
    ControlCenterStub m_controlCenter;
    BackendTrap m_backend;
};

void ProtonVpnRunnerTest::initTestCase()
{
    QDBusConnection bus = QDBusConnection::sessionBus();
    QVERIFY(bus.registerService(
        QStringLiteral("quest.entropy.PlasmaVPN.ControlCenter")));
    QVERIFY(bus.registerObject(
        QStringLiteral("/quest/entropy/PlasmaVPN/ControlCenter"),
        &m_controlCenter, QDBusConnection::ExportAllSlots));
    QVERIFY(bus.registerService(QStringLiteral("quest.entropy.PlasmaVPN.Backend")));
    QVERIFY(bus.registerObject(QStringLiteral("/quest/entropy/PlasmaVPN/Backend"),
                               &m_backend,
                               QDBusConnection::ExportAllSlots));
    initProperties();
}

void ProtonVpnRunnerTest::showsPrimaryActions()
{
    const QList<KRunner::QueryMatch> matches = launchQuery(QStringLiteral("vpn"));
    QCOMPARE(matches.size(), 3);
    QCOMPARE(matches.at(0).text(), QStringLiteral("Open Plasma VPN"));
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

void ProtonVpnRunnerTest::dispatchesControlCenterActions_data()
{
    QTest::addColumn<QString>("query");
    QTest::addColumn<QString>("operation");
    QTest::addColumn<QString>("argument");

    QTest::newRow("open") << QStringLiteral("vpn open")
                           << QStringLiteral("open") << QString();
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

void ProtonVpnRunnerTest::dispatchesControlCenterActions()
{
    QFETCH(QString, query);
    QFETCH(QString, operation);
    QFETCH(QString, argument);

    const QList<KRunner::QueryMatch> matches = launchQuery(query);
    QCOMPARE(matches.size(), 1);
    QSignalSpy spy(&m_controlCenter, &ControlCenterStub::actionRequested);
    const int backendCalls = m_backend.calls;
    KRunner::RunnerContext context;
    runner->run(context, matches.constFirst());
    QTRY_COMPARE(spy.count(), 1);
    QCOMPARE(spy.constFirst().at(0).toString(), operation);
    QCOMPARE(spy.constFirst().at(1).toString(), argument);
    QCOMPARE(m_backend.calls, backendCalls);
}

QTEST_GUILESS_MAIN(ProtonVpnRunnerTest)

#include "ProtonVpnRunnerTest.moc"
