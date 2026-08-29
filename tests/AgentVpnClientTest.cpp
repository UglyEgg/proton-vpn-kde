#include "AgentVpnClient.h"

#include <QDBusConnection>
#include <QtTest>
#include <memory>

namespace
{
constexpr auto kBackendService = "proton.vpn.app.kde.backend";
constexpr auto kBackendPath = "/proton/vpn/app/kde/backend";

class AgentBackend final : public QObject
{
    Q_OBJECT
    Q_CLASSINFO("D-Bus Interface", "proton.vpn.app.kde.Backend1")

public:
    int registrationCalls = 0;
    int reconnectCalls = 0;
    int fastestCalls = 0;
    int countryCalls = 0;
    int serverCalls = 0;
    int disconnectCalls = 0;
    QString state = QStringLiteral("disconnected");
    QString lastTarget;

public slots:
    void RegisterClient(const QString &) { ++registrationCalls; }
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
    void observesAndControlsWithoutTakingABackendLease();

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
}

void AgentVpnClientTest::cleanupTestCase()
{
    if (!m_backendBus) {
        return;
    }
    m_backendBus->unregisterObject(QString::fromLatin1(kBackendPath));
    m_backendBus->unregisterService(QString::fromLatin1(kBackendService));
    m_backendBus.reset();
    QDBusConnection::disconnectFromBus(
        QStringLiteral("agent-client-test-backend"));
}

void AgentVpnClientTest::observesAndControlsWithoutTakingABackendLease()
{
    AgentVpnClient client;
    QTRY_VERIFY_WITH_TIMEOUT(client.backendAvailable(), 2000);
    QTRY_VERIFY_WITH_TIMEOUT(client.ready(), 2000);
    QTRY_VERIFY_WITH_TIMEOUT(client.loggedIn(), 2000);
    QTRY_VERIFY_WITH_TIMEOUT(m_backend.reconnectCalls > 0, 2000);
    QCOMPARE(m_backend.registrationCalls, 0);

    client.connectTarget(QStringLiteral(" ch "));
    QTRY_COMPARE_WITH_TIMEOUT(m_backend.countryCalls, 1, 2000);
    QCOMPARE(m_backend.lastTarget, QStringLiteral("CH"));
    QCOMPARE(m_backend.registrationCalls, 0);

    client.connectTarget(QStringLiteral("ch#101"));
    QTRY_COMPARE_WITH_TIMEOUT(m_backend.serverCalls, 1, 2000);
    QCOMPARE(m_backend.lastTarget, QStringLiteral("CH#101"));

    m_backend.state = QStringLiteral("connected");
    emit m_backend.SnapshotChanged(m_backend.GetSnapshot());
    QTRY_COMPARE_WITH_TIMEOUT(client.state(), QStringLiteral("connected"), 2000);
    client.activatePrimaryAction();
    QTRY_COMPARE_WITH_TIMEOUT(m_backend.disconnectCalls, 1, 2000);
    QCOMPARE(m_backend.registrationCalls, 0);

    m_backendBus->unregisterService(QString::fromLatin1(kBackendService));
    QTRY_VERIFY_WITH_TIMEOUT(!client.backendAvailable(), 2000);
    QCOMPARE(client.state(), QStringLiteral("disconnected"));
}

QTEST_MAIN(AgentVpnClientTest)

#include "AgentVpnClientTest.moc"
