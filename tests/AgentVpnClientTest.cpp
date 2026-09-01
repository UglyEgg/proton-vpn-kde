// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#include "AgentVpnClient.h"
#include "SnapshotTestData.h"

#include <QDBusConnection>
#include <QDBusContext>
#include <QDBusConnectionInterface>
#include <QDBusError>
#include <QDBusMessage>
#include <QtTest>
#include <memory>

namespace
{
constexpr auto kBackendService = "quest.entropy.PlasmaVPN.Backend";
constexpr auto kBackendPath = "/quest/entropy/PlasmaVPN/Backend";

class AgentBackend final : public QObject, protected QDBusContext
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
    bool failReconnection = false;
    bool delayNextSnapshot = false;
    bool delayNextRegistration = false;
    QString state = QStringLiteral("disconnected");
    QString lastTarget;
    QStringList lastFeatures;
    QString lastGroupKind;
    QString lastGroupName;
    QDBusMessage delayedSnapshotMessage;
    QDBusMessage delayedRegistrationMessage;

    void resetCounters()
    {
        authorizationCalls = 0;
        registrationCalls = 0;
        unregistrationCalls = 0;
        reconnectCalls = 0;
        fastestCalls = 0;
        filteredFastestCalls = 0;
        countryCalls = 0;
        serverCalls = 0;
        groupCalls = 0;
        disconnectCalls = 0;
        state = QStringLiteral("disconnected");
        lastTarget.clear();
        lastFeatures.clear();
        lastGroupKind.clear();
        lastGroupName.clear();
    }

public slots:
    void AuthorizeClient(const QString &) { ++authorizationCalls; }
    void RegisterClient(const QString &)
    {
        ++registrationCalls;
        if (delayNextRegistration) {
            delayNextRegistration = false;
            setDelayedReply(true);
            delayedRegistrationMessage = message();
        }
    }
    void UnregisterClient(const QString &) { ++unregistrationCalls; }
    void SetReconnectionEnabled(bool)
    {
        ++reconnectCalls;
        if (failReconnection) {
            sendErrorReply(QDBusError::Failed,
                           QStringLiteral("reconnection policy failed"));
        }
    }

    QString GetSnapshot()
    {
        if (delayNextSnapshot) {
            delayNextSnapshot = false;
            setDelayedReply(true);
            delayedSnapshotMessage = message();
            return {};
        }
        return ProtonVpnKde::TestData::completeSnapshot(state);
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
    void failedReconnectionPolicyBlocksQueuedConnect();
    void staleSnapshotCannotClearReplacementAction();
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

void AgentVpnClientTest::failedReconnectionPolicyBlocksQueuedConnect()
{
    m_backend.failReconnection = true;
    const int reconnectBaseline = m_backend.reconnectCalls;
    const int registrationBaseline = m_backend.registrationCalls;
    const int unregistrationBaseline = m_backend.unregistrationCalls;
    AgentVpnClient client;
    QTRY_VERIFY_WITH_TIMEOUT(client.backendAvailable(), 2000);
    QTRY_VERIFY_WITH_TIMEOUT(client.ready(), 2000);
    QTRY_VERIFY_WITH_TIMEOUT(client.loggedIn(), 2000);
    QTRY_VERIFY_WITH_TIMEOUT(
        m_backend.reconnectCalls > reconnectBaseline, 2000);

    client.connectTarget(QStringLiteral("FASTEST"));
    QTRY_VERIFY_WITH_TIMEOUT(
        m_backend.reconnectCalls > reconnectBaseline + 1, 2000);
    QTest::qWait(50);
    QCOMPARE(m_backend.fastestCalls, 0);
    QCOMPARE(m_backend.registrationCalls, registrationBaseline + 1);
    QTRY_COMPARE_WITH_TIMEOUT(
        m_backend.unregistrationCalls, unregistrationBaseline + 1, 2000);

    m_backend.failReconnection = false;
    client.connectTarget(QStringLiteral("FASTEST"));
    QTRY_COMPARE_WITH_TIMEOUT(m_backend.fastestCalls, 1, 2000);
}

void AgentVpnClientTest::staleSnapshotCannotClearReplacementAction()
{
    m_backend.failReconnection = false;
    m_backend.resetCounters();
    m_backend.delayedSnapshotMessage = {};
    AgentVpnClient client;
    QTRY_VERIFY_WITH_TIMEOUT(client.backendAvailable(), 2000);
    QTRY_VERIFY_WITH_TIMEOUT(client.ready(), 2000);
    QTRY_VERIFY_WITH_TIMEOUT(client.loggedIn(), 2000);

    m_backend.delayNextSnapshot = true;
    client.connectTarget(QStringLiteral("FASTEST"));
    QTRY_COMPARE_WITH_TIMEOUT(
        m_backend.delayedSnapshotMessage.type(),
        QDBusMessage::MethodCallMessage, 2000);

    QVERIFY(m_backendBus->unregisterService(
        QString::fromLatin1(kBackendService)));
    QTRY_VERIFY_WITH_TIMEOUT(!client.backendAvailable(), 2000);

    constexpr auto replacementConnectionName =
        "agent-client-test-replacement-backend";
    AgentBackend replacement;
    QDBusConnection replacementBus = QDBusConnection::connectToBus(
        QDBusConnection::SessionBus,
        QString::fromLatin1(replacementConnectionName));
    QVERIFY(replacementBus.isConnected());
    QVERIFY(replacementBus.registerObject(
        QString::fromLatin1(kBackendPath), &replacement,
        QDBusConnection::ExportAllSlots | QDBusConnection::ExportAllSignals));
    qputenv("PROTON_VPN_KDE_TEST_BACKEND_OWNER",
            replacementBus.baseService().toUtf8());
    QVERIFY(replacementBus.registerService(
        QString::fromLatin1(kBackendService)));
    QTRY_VERIFY_WITH_TIMEOUT(client.backendAvailable(), 2000);
    QTRY_VERIFY_WITH_TIMEOUT(client.ready(), 2000);

    replacement.delayNextRegistration = true;
    client.connectTarget(QStringLiteral("CH"));
    QTRY_COMPARE_WITH_TIMEOUT(
        replacement.delayedRegistrationMessage.type(),
        QDBusMessage::MethodCallMessage, 2000);

    QVERIFY(m_backendBus->send(
        m_backend.delayedSnapshotMessage.createErrorReply(
            QStringLiteral("org.freedesktop.DBus.Error.NoReply"),
            QStringLiteral("old backend reply"))));
    QVERIFY(replacementBus.send(
        replacement.delayedRegistrationMessage.createReply()));
    QTRY_COMPARE_WITH_TIMEOUT(replacement.countryCalls, 1, 2000);
    QVERIFY(client.backendAvailable());
    QVERIFY(client.ready());

    QVERIFY(replacementBus.unregisterService(
        QString::fromLatin1(kBackendService)));
    replacementBus.unregisterObject(QString::fromLatin1(kBackendPath));
    QDBusConnection::disconnectFromBus(
        QString::fromLatin1(replacementConnectionName));
    qputenv("PROTON_VPN_KDE_TEST_BACKEND_OWNER",
            m_backendBus->baseService().toUtf8());
    QVERIFY(m_backendBus->registerService(QString::fromLatin1(kBackendService)));
}

void AgentVpnClientTest::observesLeaseFreeAndUsesTransientActionLeases()
{
    m_backend.failReconnection = false;
    m_backend.resetCounters();
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
