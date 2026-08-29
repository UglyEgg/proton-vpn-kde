#include "LocationModels.h"
#include "VpnController.h"

#include <QAbstractItemModel>
#include <QDBusConnection>
#include <QtTest>
#include <memory>

namespace
{
constexpr auto kBackendService = "proton.vpn.app.kde.backend";
constexpr auto kBackendPath = "/proton/vpn/app/kde/backend";

class GroupedNavigationBackend final : public QObject
{
    Q_OBJECT
    Q_CLASSINFO("D-Bus Interface", "proton.vpn.app.kde.Backend1")

public:
    int registrationCalls = 0;
    int groupCalls = 0;
    int serverCalls = 0;
    QString lastCountry;
    QString lastGroupKind;
    QString lastGroupName;

public slots:
    void RegisterClient(const QString &)
    {
        ++registrationCalls;
    }

    void UnregisterClient(const QString &)
    {
    }

    QString GetSnapshot() const
    {
        return QStringLiteral(R"json({
            "schemaVersion":1,
            "ready":true,
            "startupCompatible":true,
            "loggedIn":true,
            "authState":"signed_in",
            "coreMemoryOptimized":false,
            "coreVersion":"5.7.0",
            "state":"disconnected",
            "busy":false,
            "message":""
        })json");
    }

    QString GetPendingNpsSurvey() const
    {
        return QStringLiteral(
            R"json({"schemaVersion":1,"available":false})json");
    }

    QString GetSettings() const
    {
        return QStringLiteral(R"json({
            "schemaVersion":1,
            "protocol":"wireguard",
            "protocols":[{"id":"wireguard","name":"WireGuard"}],
            "killSwitch":0,
            "netShield":0,
            "vpnAccelerator":true,
            "moderateNat":false,
            "portForwarding":false,
            "ipv6":true,
            "anonymousCrashReports":true,
            "paidFeaturesAvailable":true,
            "protocolEditable":true,
            "killSwitchEditable":true,
            "splitTunnelingEnabled":false,
            "customDnsEnabled":false,
            "packetCaptureSupported":false
        })json");
    }

    QString GetServerGroups(const QString &countryCode)
    {
        ++groupCalls;
        lastCountry = countryCode;
        return QStringLiteral(R"json({
            "schemaVersion":1,
            "groups":[
                {"kind":"location","name":"Zurich","serverCount":2},
                {"kind":"secure-core","name":"Via Secure Core",
                 "serverCount":1,"secureCore":true}
            ]
        })json");
    }

    QString GetGroupServers(const QString &countryCode,
                            const QString &groupKind,
                            const QString &groupName)
    {
        ++serverCalls;
        lastCountry = countryCode;
        lastGroupKind = groupKind;
        lastGroupName = groupName;
        return QStringLiteral(R"json({
            "schemaVersion":1,
            "servers":[
                {"name":"CH#101","location":"Zurich","load":24},
                {"name":"CH#202","location":"Zurich","load":51}
            ]
        })json");
    }
};
}

class GroupedNavigationTest final : public QObject
{
    Q_OBJECT

private slots:
    void initTestCase();
    void cleanupTestCase();
    void loadsCountryGroupsAndTheirServersWithoutAFlatEndpoint();

private:
    GroupedNavigationBackend m_backend;
    std::unique_ptr<QDBusConnection> m_backendBus;
};

void GroupedNavigationTest::initTestCase()
{
    constexpr auto connectionName = "grouped-navigation-test-backend";
    m_backendBus = std::make_unique<QDBusConnection>(
        QDBusConnection::connectToBus(QDBusConnection::SessionBus,
                                      QString::fromLatin1(connectionName)));
    QVERIFY2(m_backendBus->isConnected(), "A session D-Bus is required");
    QVERIFY(m_backendBus->registerService(QString::fromLatin1(kBackendService)));
    QVERIFY(m_backendBus->registerObject(QString::fromLatin1(kBackendPath),
                                         &m_backend,
                                         QDBusConnection::ExportAllSlots));
}

void GroupedNavigationTest::cleanupTestCase()
{
    if (!m_backendBus) {
        return;
    }
    m_backendBus->unregisterObject(QString::fromLatin1(kBackendPath));
    m_backendBus->unregisterService(QString::fromLatin1(kBackendService));
    m_backendBus.reset();
    QDBusConnection::disconnectFromBus(
        QStringLiteral("grouped-navigation-test-backend"));
}

void GroupedNavigationTest::loadsCountryGroupsAndTheirServersWithoutAFlatEndpoint()
{
    VpnController controller(nullptr, false);

    QTRY_VERIFY_WITH_TIMEOUT(controller.backendAvailable(), 2000);
    QTRY_VERIFY_WITH_TIMEOUT(controller.ready(), 2000);
    QTRY_VERIFY_WITH_TIMEOUT(controller.loggedIn(), 2000);
    QTRY_COMPARE_WITH_TIMEOUT(m_backend.registrationCalls, 1, 2000);
    QVERIFY(!controller.coreMemoryOptimized());
    QCOMPARE(controller.coreVersion(), QStringLiteral("5.7.0"));
    QCOMPARE(controller.metaObject()->indexOfMethod("loadServers(QString)"), -1);

    controller.loadServerGroups(QStringLiteral(" ch "));
    QTRY_COMPARE_WITH_TIMEOUT(controller.serverGroupModel()->rowCount(), 2, 2000);
    QCOMPARE(m_backend.groupCalls, 1);
    QCOMPARE(m_backend.lastCountry, QStringLiteral("CH"));

    controller.loadGroupServers(QStringLiteral("ch"),
                                QStringLiteral("location"),
                                QStringLiteral("Zurich"));
    QTRY_COMPARE_WITH_TIMEOUT(controller.serverModel()->rowCount(), 2, 2000);
    QCOMPARE(m_backend.serverCalls, 1);
    QCOMPARE(m_backend.lastCountry, QStringLiteral("CH"));
    QCOMPARE(m_backend.lastGroupKind, QStringLiteral("location"));
    QCOMPARE(m_backend.lastGroupName, QStringLiteral("Zurich"));
    QCOMPARE(controller.serverModel()
                 ->index(0, 0)
                 .data(ServerModel::NameRole)
                 .toString(),
             QStringLiteral("CH#101"));
    QVERIFY(!controller.locationsBusy());
}

QTEST_MAIN(GroupedNavigationTest)

#include "GroupedNavigationTest.moc"
