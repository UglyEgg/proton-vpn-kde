// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#include "AgentVpnClient.h"

#include <QDBusConnection>
#include <QDBusConnectionInterface>
#include <QtTest>
#include <memory>

namespace
{
constexpr auto kBackendService = "quest.entropy.PlasmaVPN.Backend";
constexpr auto kBackendPath = "/quest/entropy/PlasmaVPN/Backend";

class AgentBackend final : public QObject
{
    Q_OBJECT
    Q_CLASSINFO("D-Bus Interface", "quest.entropy.PlasmaVPN.Backend1")

public:
    int authorizationCalls = 0;
    int registrationCalls = 0;
    int unregistrationCalls = 0;
    int reconnectCalls = 0;
    int fastestCalls = 0;
    int filteredFastestCalls = 0;
    int countryCalls = 0;
    int serverCalls = 0;
    int groupCalls = 0;
    int disconnectCalls = 0;
    QString state = QStringLiteral("disconnected");
    QString lastTarget;
    QStringList lastFeatures;
    QString lastGroupKind;
    QString lastGroupName;

public slots:
    void AuthorizeClient(const QString &) { ++authorizationCalls; }
    void RegisterClient(const QString &) { ++registrationCalls; }
    void UnregisterClient(const QString &) { ++unregistrationCalls; }
    void SetReconnectionEnabled(bool) { ++reconnectCalls; }

    QString GetSnapshot() const
    {
        return QStringLiteral(R"json({
            "schemaVersion":1,
            "ready":true,
            "loggedIn":true,
            "state":"%1",
            "busy":false,
            "killSwitch":0,
            "forwardedPort":0,
            "serverName":"",
            "message":""
        })json").arg(state);
    }

    void ConnectFastest() { ++fastestCalls; }
    void ConnectFastestWithFeatures(const QStringList &features)
    {
        ++filteredFastestCalls;
        lastFeatures = features;
    }
    void ConnectCountry(const QString &target)
    {
        ++countryCalls;
        lastTarget = target;
    }
    void ConnectServer(const QString &target)
    {
        ++serverCalls;
        lastTarget = target;
    }
    void ConnectGroup(const QString &countryCode, const QString &groupKind,
                      const QString &groupName)
    {
        ++groupCalls;
        lastTarget = countryCode;
        lastGroupKind = groupKind;
        lastGroupName = groupName;
    }
    void Disconnect() { ++disconnectCalls; }

signals:
    void SnapshotChanged(const QString &snapshot);
};
}

class AgentVpnClientTest final : public QObject
{
    Q_OBJECT

private slots:
    void initTestCase();
    void cleanupTestCase();
    void observesLeaseFreeAndUsesTransientActionLeases();

private:
    AgentBackend m_backend;
    std::unique_ptr<QDBusConnection> m_backendBus;
};

void AgentVpnClientTest::initTestCase()
{
    constexpr auto connectionName = "agent-client-test-backend";
    m_backendBus = std::make_unique<QDBusConnection>(
        QDBusConnection::connectToBus(QDBusConnection::SessionBus,
                                      QString::fromLatin1(connectionName)));
    QVERIFY2(m_backendBus->isConnected(), "A session D-Bus is required");
    QVERIFY(m_backendBus->registerService(QString::fromLatin1(kBackendService)));
    QVERIFY(m_backendBus->registerObject(QString::fromLatin1(kBackendPath),
                                         &m_backend,
                                         QDBusConnection::ExportAllSlots
                                             | QDBusConnection::ExportAllSignals));
    const auto owner = QDBusConnection::sessionBus().interface()->serviceOwner(
        QString::fromLatin1(kBackendService));
    QVERIFY(owner.isValid());
    qputenv("PROTON_VPN_KDE_TEST_BACKEND_OWNER", owner.value().toUtf8());
}

void AgentVpnClientTest::cleanupTestCase()
{
    if (!m_backendBus) {
        return;
    }
    m_backendBus->unregisterObject(QString::fromLatin1(kBackendPath));
    m_backendBus->unregisterService(QString::fromLatin1(kBackendService));
    m_backendBus.reset();
    qunsetenv("PROTON_VPN_KDE_TEST_BACKEND_OWNER");
    QDBusConnection::disconnectFromBus(
        QStringLiteral("agent-client-test-backend"));
}

void AgentVpnClientTest::observesLeaseFreeAndUsesTransientActionLeases()
{
    AgentVpnClient client;
    QTRY_VERIFY_WITH_TIMEOUT(client.backendAvailable(), 2000);
    QTRY_VERIFY_WITH_TIMEOUT(client.ready(), 2000);
    QTRY_VERIFY_WITH_TIMEOUT(client.loggedIn(), 2000);
    QTRY_VERIFY_WITH_TIMEOUT(m_backend.reconnectCalls > 0, 2000);
    QCOMPARE(m_backend.authorizationCalls, 1);
    QCOMPARE(m_backend.registrationCalls, 0);

    client.setFastestFeatures(
        {QStringLiteral("p2p"), QStringLiteral("streaming")});
    client.connectTarget(QStringLiteral("FASTEST"));
    QTRY_COMPARE_WITH_TIMEOUT(m_backend.filteredFastestCalls, 1, 2000);
    QCOMPARE(m_backend.lastFeatures,
             QStringList({QStringLiteral("p2p"),
                          QStringLiteral("streaming")}));
    QCOMPARE(m_backend.fastestCalls, 0);
    QCOMPARE(m_backend.registrationCalls, 1);
    QTRY_COMPARE_WITH_TIMEOUT(m_backend.unregistrationCalls, 1, 2000);

    client.connectTarget(QStringLiteral(" ch "));
    QTRY_COMPARE_WITH_TIMEOUT(m_backend.countryCalls, 1, 2000);
    QCOMPARE(m_backend.lastTarget, QStringLiteral("CH"));
    QCOMPARE(m_backend.registrationCalls, 2);
    QTRY_COMPARE_WITH_TIMEOUT(m_backend.unregistrationCalls, 2, 2000);

    client.connectTarget(QStringLiteral("ch#101"));
    QTRY_COMPARE_WITH_TIMEOUT(m_backend.serverCalls, 1, 2000);
    QCOMPARE(m_backend.lastTarget, QStringLiteral("CH#101"));
    QCOMPARE(m_backend.registrationCalls, 3);
    QTRY_COMPARE_WITH_TIMEOUT(m_backend.unregistrationCalls, 3, 2000);

    client.connectGroup(QStringLiteral(" us "), QStringLiteral(" LOCATION "),
                        QStringLiteral(" New York "));
    QTRY_COMPARE_WITH_TIMEOUT(m_backend.groupCalls, 1, 2000);
    QCOMPARE(m_backend.lastTarget, QStringLiteral("US"));
    QCOMPARE(m_backend.lastGroupKind, QStringLiteral("location"));
    QCOMPARE(m_backend.lastGroupName, QStringLiteral("New York"));
    QCOMPARE(m_backend.registrationCalls, 4);
    QTRY_COMPARE_WITH_TIMEOUT(m_backend.unregistrationCalls, 4, 2000);

    m_backend.state = QStringLiteral("connected");
    emit m_backend.SnapshotChanged(m_backend.GetSnapshot());
    QTRY_COMPARE_WITH_TIMEOUT(client.state(), QStringLiteral("connected"), 2000);
    client.activatePrimaryAction();
    QTRY_COMPARE_WITH_TIMEOUT(m_backend.disconnectCalls, 1, 2000);
    QCOMPARE(m_backend.registrationCalls, 4);

    m_backendBus->unregisterService(QString::fromLatin1(kBackendService));
    QTRY_VERIFY_WITH_TIMEOUT(!client.backendAvailable(), 2000);
    QCOMPARE(client.state(), QStringLiteral("disconnected"));
}

QTEST_MAIN(AgentVpnClientTest)

#include "AgentVpnClientTest.moc"
