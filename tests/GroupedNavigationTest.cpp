// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#include "LocationModels.h"
#include "VpnController.h"
#include "VpnSettingsModel.h"

#include <QAbstractItemModel>
#include <QDBusConnection>
#include <QDBusConnectionInterface>
#include <QDBusContext>
#include <QtTest>
#include <memory>

namespace
{
constexpr auto kBackendService = "quest.entropy.PlasmaVPN.Backend";
constexpr auto kBackendPath = "/quest/entropy/PlasmaVPN/Backend";

class GroupedNavigationBackend final : public QObject, protected QDBusContext
{
    Q_OBJECT
    Q_CLASSINFO("D-Bus Interface", "quest.entropy.PlasmaVPN.Backend1")

public:
    int registrationCalls = 0;
    int countryCalls = 0;
    int groupCalls = 0;
    int serverCalls = 0;
    int capabilityCalls = 0;
    int emptyGroupResponses = 0;
    int emptyServerResponses = 0;
    bool rejectRegistration = false;
    bool ready = true;
    bool loggedIn = true;
    QString lastCountry;
    QString lastGroupKind;
    QString lastGroupName;
    QStringList lastCapabilities;
    QStringList browseCallOrder;

    void publishSession(bool sessionReady, bool sessionLoggedIn)
    {
        ready = sessionReady;
        loggedIn = sessionLoggedIn;
        emit SnapshotChanged(GetSnapshot());
    }

signals:
    void SnapshotChanged(const QString &snapshotJson);

public slots:
    void RegisterClient(const QString &)
    {
        ++registrationCalls;
        if (rejectRegistration) {
            sendErrorReply(
                QStringLiteral("quest.entropy.PlasmaVPN.Error.Unauthorized"),
                QStringLiteral(
                    "This application is not authorized to control the VPN"));
        }
    }

    void UnregisterClient(const QString &)
    {
    }

    void SetReconnectionEnabled(bool)
    {
    }

    QString GetSnapshot() const
    {
        return QStringLiteral(R"json({
            "schemaVersion":1,
            "ready":%1,
            "startupCompatible":true,
            "loggedIn":%2,
            "authState":"signed_in",
            "coreMemoryOptimized":false,
            "coreVersion":"5.7.0",
            "state":"disconnected",
            "busy":false,
            "message":""
        })json")
            .arg(ready ? QStringLiteral("true") : QStringLiteral("false"),
                 loggedIn ? QStringLiteral("true") : QStringLiteral("false"));
    }

    QString GetCountries()
    {
        ++countryCalls;
        browseCallOrder.append(QStringLiteral("countries"));
        return QStringLiteral(R"json({
            "schemaVersion":1,
            "countries":[
                {"code":"CH","serverCount":4,"accessible":true},
                {"code":"US","serverCount":5,"accessible":true}
            ]
        })json");
    }

    void ConnectFastestWithFeature(const QString &feature)
    {
        ++capabilityCalls;
        lastCapabilities = {feature};
    }

    void ConnectFastestWithFeatures(const QStringList &features)
    {
        ++capabilityCalls;
        lastCapabilities = features;
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
        browseCallOrder.append(QStringLiteral("groups"));
        lastCountry = countryCode;
        if (emptyGroupResponses > 0) {
            --emptyGroupResponses;
            return QStringLiteral(
                R"json({"schemaVersion":1,"groups":[]})json");
        }
        return QStringLiteral(R"json({
            "schemaVersion":1,
            "groups":[
                {"kind":"location","name":"Zurich","serverCount":2,
                 "p2p":true,"streaming":true},
                {"kind":"secure-core","name":"Via Secure Core",
                 "serverCount":1,"secureCore":true,"p2p":true}
            ]
        })json");
    }

    QString GetGroupServers(const QString &countryCode,
                            const QString &groupKind,
                            const QString &groupName)
    {
        ++serverCalls;
        browseCallOrder.append(QStringLiteral("servers"));
        lastCountry = countryCode;
        lastGroupKind = groupKind;
        lastGroupName = groupName;
        if (emptyServerResponses > 0) {
            --emptyServerResponses;
            return QStringLiteral(
                R"json({"schemaVersion":1,"servers":[]})json");
        }
        return QStringLiteral(R"json({
            "schemaVersion":1,
            "servers":[
                {"name":"CH#101","location":"Zurich","load":24,
                 "p2p":true,"streaming":true},
                {"name":"CH#202","location":"Zurich","load":51,
                 "p2p":true}
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
    void rejectsAnUnpinnedBackendOwner();
    void explainsRejectedClientIdentityWithoutRetrying();
    void clearsCachedSessionWhenBackendStops();
    void queuesInitialBrowserLoadUntilBackendIsReady();
    void loadsCountryGroupsAndTheirServersWithoutAFlatEndpoint();
    void retriesTransientEmptyServerGroupResponses();
    void retriesTransientEmptyServerResponse();
    void stalePageCleanupCannotClearReplacementContexts();
    void requestsFastestServerByValidatedCapabilities();
    void supportReportSubmissionFollowsBuildPolicy();
    void crashReportSubmissionFollowsBuildPolicy();

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
                                         QDBusConnection::ExportAllSlots
                                             | QDBusConnection::ExportAllSignals));
    const auto owner = QDBusConnection::sessionBus().interface()->serviceOwner(
        QString::fromLatin1(kBackendService));
    QVERIFY(owner.isValid());
    qputenv("PROTON_VPN_KDE_TEST_BACKEND_OWNER", owner.value().toUtf8());
}

void GroupedNavigationTest::cleanupTestCase()
{
    if (!m_backendBus) {
        return;
    }
    m_backendBus->unregisterObject(QString::fromLatin1(kBackendPath));
    m_backendBus->unregisterService(QString::fromLatin1(kBackendService));
    m_backendBus.reset();
    qunsetenv("PROTON_VPN_KDE_TEST_BACKEND_OWNER");
    QDBusConnection::disconnectFromBus(
        QStringLiteral("grouped-navigation-test-backend"));
}

void GroupedNavigationTest::rejectsAnUnpinnedBackendOwner()
{
    const QByteArray trustedOwner = qgetenv(
        "PROTON_VPN_KDE_TEST_BACKEND_OWNER");
    qunsetenv("PROTON_VPN_KDE_TEST_BACKEND_OWNER");
    const int registrationsBefore = m_backend.registrationCalls;

    VpnController controller(nullptr, false);

    QTest::qWait(100);
    QVERIFY(!controller.backendAvailable());
    QCOMPARE(m_backend.registrationCalls, registrationsBefore);
    qputenv("PROTON_VPN_KDE_TEST_BACKEND_OWNER", trustedOwner);
}

void GroupedNavigationTest::explainsRejectedClientIdentityWithoutRetrying()
{
    m_backend.rejectRegistration = true;
    const int registrationsBefore = m_backend.registrationCalls;
    {
        VpnController controller(nullptr, false);

        QTRY_COMPARE_WITH_TIMEOUT(
            m_backend.registrationCalls, registrationsBefore + 1, 2000);
        QTRY_VERIFY_WITH_TIMEOUT(
            controller.message().contains(
                QStringLiteral("Close and reopen"), Qt::CaseInsensitive),
            2000);
        QVERIFY(!controller.backendAvailable());
        QTest::qWait(1200);
        QCOMPARE(m_backend.registrationCalls, registrationsBefore + 1);
    }
    m_backend.rejectRegistration = false;
}

void GroupedNavigationTest::clearsCachedSessionWhenBackendStops()
{
    VpnController controller(nullptr, false);

    QTRY_VERIFY_WITH_TIMEOUT(controller.backendAvailable(), 2000);
    QTRY_VERIFY_WITH_TIMEOUT(controller.ready(), 2000);
    QTRY_VERIFY_WITH_TIMEOUT(controller.loggedIn(), 2000);
    QCOMPARE(controller.authState(), QStringLiteral("signed_in"));

    controller.onServiceUnregistered(QString::fromLatin1(kBackendService));

    QVERIFY(!controller.backendAvailable());
    QVERIFY(!controller.ready());
    QVERIFY(!controller.loggedIn());
    QCOMPARE(controller.authState(), QStringLiteral("signed_out"));
    QCOMPARE(controller.state(), QStringLiteral("unavailable"));
}

void GroupedNavigationTest::loadsCountryGroupsAndTheirServersWithoutAFlatEndpoint()
{
    const int registrationsBefore = m_backend.registrationCalls;
    const int groupCallsBefore = m_backend.groupCalls;
    const int serverCallsBefore = m_backend.serverCalls;
    VpnController controller(nullptr, false);

    QTRY_VERIFY_WITH_TIMEOUT(controller.backendAvailable(), 2000);
    QTRY_VERIFY_WITH_TIMEOUT(controller.ready(), 2000);
    QTRY_VERIFY_WITH_TIMEOUT(controller.loggedIn(), 2000);
    QTRY_COMPARE_WITH_TIMEOUT(
        m_backend.registrationCalls, registrationsBefore + 1, 2000);
    QVERIFY(!controller.coreMemoryOptimized());
    QCOMPARE(controller.coreVersion(), QStringLiteral("5.7.0"));
    QCOMPARE(controller.metaObject()->indexOfMethod("loadServers(QString)"), -1);

    controller.loadServerGroups(QStringLiteral(" ch "));
    QTRY_COMPARE_WITH_TIMEOUT(controller.serverGroupModel()->rowCount(), 2, 2000);
    QCOMPARE(m_backend.groupCalls, groupCallsBefore + 1);
    QCOMPARE(m_backend.lastCountry, QStringLiteral("CH"));

    controller.loadGroupServers(QStringLiteral("ch"),
                                QStringLiteral("location"),
                                QStringLiteral("Zurich"));
    QTRY_COMPARE_WITH_TIMEOUT(controller.serverModel()->rowCount(), 2, 2000);
    QCOMPARE(m_backend.serverCalls, serverCallsBefore + 1);
    QCOMPARE(m_backend.lastCountry, QStringLiteral("CH"));
    QCOMPARE(m_backend.lastGroupKind, QStringLiteral("location"));
    QCOMPARE(m_backend.lastGroupName, QStringLiteral("Zurich"));
    QCOMPARE(controller.serverModel()
                 ->index(0, 0)
                 .data(ServerModel::NameRole)
                 .toString(),
             QStringLiteral("CH#101"));

    controller.setServerFeatureFilter(
        {QStringLiteral("p2p"), QStringLiteral("streaming")});
    QCOMPARE(controller.serverModel()->rowCount(), 1);
    controller.setServerFeatureFilter({QStringLiteral("secure-core")});
    QCOMPARE(controller.serverModel()->rowCount(), 0);
    controller.setServerFeatureFilter({});
    QCOMPARE(controller.serverModel()->rowCount(), 2);

    controller.setServerGroupFeatureFilter(
        {QStringLiteral("secure-core"), QStringLiteral("p2p")});
    QCOMPARE(controller.serverGroupModel()->rowCount(), 1);
    controller.setServerGroupFeatureFilter({});
    QCOMPARE(controller.serverGroupModel()->rowCount(), 2);
    QVERIFY(!controller.locationsBusy());
}

void GroupedNavigationTest::queuesInitialBrowserLoadUntilBackendIsReady()
{
    m_backend.publishSession(false, true);
    const int countryCallsBefore = m_backend.countryCalls;
    const int groupCallsBefore = m_backend.groupCalls;
    const int serverCallsBefore = m_backend.serverCalls;
    VpnController controller(nullptr, false);

    QTRY_VERIFY_WITH_TIMEOUT(controller.backendAvailable(), 2000);
    QTRY_VERIFY_WITH_TIMEOUT(!controller.ready(), 2000);
    controller.loadCountries();
    m_backend.browseCallOrder.clear();
    controller.loadServerGroups(QStringLiteral("CH"));
    controller.loadGroupServers(QStringLiteral("CH"),
                                QStringLiteral("location"),
                                QStringLiteral("Zurich"));

    QCOMPARE(m_backend.countryCalls, countryCallsBefore);
    QCOMPARE(m_backend.groupCalls, groupCallsBefore);
    QCOMPARE(m_backend.serverCalls, serverCallsBefore);
    QVERIFY(controller.locationsBusy());

    m_backend.publishSession(true, true);
    QTRY_VERIFY_WITH_TIMEOUT(controller.ready(), 2000);
    QTRY_COMPARE_WITH_TIMEOUT(controller.countryModel()->rowCount(), 2, 2000);
    QTRY_COMPARE_WITH_TIMEOUT(controller.serverGroupModel()->rowCount(), 2, 2000);
    QTRY_COMPARE_WITH_TIMEOUT(controller.serverModel()->rowCount(), 2, 2000);
    QCOMPARE(m_backend.countryCalls, countryCallsBefore + 1);
    QCOMPARE(m_backend.groupCalls, groupCallsBefore + 1);
    QCOMPARE(m_backend.serverCalls, serverCallsBefore + 1);
    QCOMPARE(m_backend.browseCallOrder,
             QStringList({QStringLiteral("servers"),
                          QStringLiteral("groups"),
                          QStringLiteral("countries")}));
    QTRY_VERIFY_WITH_TIMEOUT(!controller.locationsBusy(), 2000);
}

void GroupedNavigationTest::retriesTransientEmptyServerResponse()
{
    m_backend.publishSession(true, true);
    const int serverCallsBefore = m_backend.serverCalls;
    m_backend.emptyServerResponses = 1;
    VpnController controller(nullptr, false);

    QTRY_VERIFY_WITH_TIMEOUT(controller.backendAvailable(), 2000);
    QTRY_VERIFY_WITH_TIMEOUT(controller.ready(), 2000);
    controller.loadGroupServers(QStringLiteral("CH"),
                                QStringLiteral("location"),
                                QStringLiteral("Zurich"));

    QTRY_COMPARE_WITH_TIMEOUT(controller.serverModel()->rowCount(), 2, 3000);
    QCOMPARE(m_backend.serverCalls, serverCallsBefore + 2);
    QVERIFY(!controller.locationsBusy());
}

void GroupedNavigationTest::retriesTransientEmptyServerGroupResponses()
{
    m_backend.publishSession(true, true);
    const int groupCallsBefore = m_backend.groupCalls;
    m_backend.emptyGroupResponses = 2;
    VpnController controller(nullptr, false);

    QTRY_VERIFY_WITH_TIMEOUT(controller.backendAvailable(), 2000);
    QTRY_VERIFY_WITH_TIMEOUT(controller.ready(), 2000);
    controller.loadServerGroups(QStringLiteral("US"));

    QTRY_COMPARE_WITH_TIMEOUT(controller.serverGroupModel()->rowCount(), 2, 4000);
    QCOMPARE(m_backend.groupCalls, groupCallsBefore + 3);
    QVERIFY(!controller.locationsBusy());
}

void GroupedNavigationTest::stalePageCleanupCannotClearReplacementContexts()
{
    m_backend.publishSession(true, true);
    VpnController controller(nullptr, false);

    QTRY_VERIFY_WITH_TIMEOUT(controller.backendAvailable(), 2000);
    QTRY_VERIFY_WITH_TIMEOUT(controller.ready(), 2000);

    const quint64 oldCountryContext =
        controller.claimServerContext(QStringLiteral("CH"));
    QTRY_COMPARE_WITH_TIMEOUT(controller.serverGroupModel()->rowCount(), 2, 2000);
    const quint64 replacementCountryContext =
        controller.claimServerContext(QStringLiteral("US"));
    controller.setServerGroupFeatureFilter({QStringLiteral("secure-core")});
    controller.releaseServerContext(oldCountryContext);
    QTRY_COMPARE_WITH_TIMEOUT(m_backend.lastCountry, QStringLiteral("US"), 2000);
    QTRY_COMPARE_WITH_TIMEOUT(controller.serverGroupModel()->rowCount(), 1, 2000);

    const quint64 oldGroupContext = controller.claimGroupServerContext(
        QStringLiteral("CH"), QStringLiteral("location"),
        QStringLiteral("Zurich"));
    QTRY_COMPARE_WITH_TIMEOUT(controller.serverModel()->rowCount(), 2, 2000);
    const quint64 replacementGroupContext = controller.claimGroupServerContext(
        QStringLiteral("US"), QStringLiteral("location"),
        QStringLiteral("Arizona"));
    controller.setServerFeatureFilter({QStringLiteral("streaming")});
    controller.releaseGroupServerContext(oldGroupContext);
    QTRY_COMPARE_WITH_TIMEOUT(m_backend.lastCountry, QStringLiteral("US"), 2000);
    QTRY_COMPARE_WITH_TIMEOUT(m_backend.lastGroupName,
                              QStringLiteral("Arizona"), 2000);
    QTRY_COMPARE_WITH_TIMEOUT(controller.serverModel()->rowCount(), 1, 2000);

    controller.releaseGroupServerContext(replacementGroupContext);
    QCOMPARE(controller.serverModel()->rowCount(), 0);
    controller.releaseServerContext(replacementCountryContext);
    QCOMPARE(controller.serverGroupModel()->rowCount(), 0);

    controller.claimServerContext(QStringLiteral("US"));
    QTRY_COMPARE_WITH_TIMEOUT(controller.serverGroupModel()->rowCount(), 2, 2000);
    controller.claimGroupServerContext(QStringLiteral("US"),
                                       QStringLiteral("location"),
                                       QStringLiteral("Arizona"));
    QTRY_COMPARE_WITH_TIMEOUT(controller.serverModel()->rowCount(), 2, 2000);
}

void GroupedNavigationTest::requestsFastestServerByValidatedCapabilities()
{
    m_backend.publishSession(true, true);
    const int callsBefore = m_backend.capabilityCalls;
    VpnController controller(nullptr, false);

    QTRY_VERIFY_WITH_TIMEOUT(controller.backendAvailable(), 2000);
    QTRY_VERIFY_WITH_TIMEOUT(controller.ready(), 2000);
    QTRY_VERIFY_WITH_TIMEOUT(controller.loggedIn(), 2000);

    controller.connectFastestWithFeatures(
        {QStringLiteral(" Streaming "), QStringLiteral("P2P")});
    QTRY_COMPARE_WITH_TIMEOUT(m_backend.capabilityCalls, callsBefore + 1, 2000);
    QCOMPARE(m_backend.lastCapabilities,
             QStringList({QStringLiteral("p2p"),
                          QStringLiteral("streaming")}));
    QTRY_VERIFY_WITH_TIMEOUT(!controller.busy(), 2000);

    controller.setFastestFeatures(
        {QStringLiteral("secure-core"), QStringLiteral("p2p")});
    controller.activatePrimaryAction();
    QTRY_COMPARE_WITH_TIMEOUT(m_backend.capabilityCalls, callsBefore + 2, 2000);
    QCOMPARE(m_backend.lastCapabilities,
             QStringList({QStringLiteral("p2p"),
                          QStringLiteral("secure-core")}));

    controller.connectFastestWithFeatures({QStringLiteral("unsupported")});
    QTest::qWait(50);
    QCOMPARE(m_backend.capabilityCalls, callsBefore + 2);
}

void GroupedNavigationTest::supportReportSubmissionFollowsBuildPolicy()
{
    VpnController controller(nullptr, false);
    QSignalSpy finished(&controller, &VpnController::supportReportFinished);

    const bool submissionEnabled =
        PROTON_VPN_KDE_SUPPORT_REPORT_SUBMISSION_ENABLED != 0;
    QCOMPARE(controller.supportReportSubmissionEnabled(), submissionEnabled);
    if (submissionEnabled) {
        return;
    }

    controller.submitSupportReport(
        QStringLiteral("community-user"),
        QStringLiteral("user@example.test"),
        QStringLiteral("This description is intentionally long enough to pass validation."),
        true);

    QCOMPARE(finished.count(), 1);
    const QList<QVariant> arguments = finished.takeFirst();
    QVERIFY(!arguments.at(0).toBool());
    QVERIFY(arguments.at(1).toString().contains(
        QStringLiteral("disabled"), Qt::CaseInsensitive));
}

void GroupedNavigationTest::crashReportSubmissionFollowsBuildPolicy()
{
    VpnController controller(nullptr, false);

    const bool submissionEnabled =
        PROTON_VPN_KDE_CRASH_REPORT_SUBMISSION_ENABLED != 0;
    QCOMPARE(controller.crashReportSubmissionEnabled(), submissionEnabled);
    if (submissionEnabled) {
        return;
    }

    QTRY_VERIFY_WITH_TIMEOUT(controller.backendAvailable(), 2000);
    QTRY_VERIFY_WITH_TIMEOUT(controller.ready(), 2000);
    QTRY_VERIFY_WITH_TIMEOUT(controller.loggedIn(), 2000);
    QTRY_VERIFY_WITH_TIMEOUT(controller.settings()->loaded(), 2000);
    controller.updateSetting(QStringLiteral("anonymousCrashReports"), true);

    QVERIFY(controller.settings()->message().contains(
        QStringLiteral("disabled"), Qt::CaseInsensitive));
}

QTEST_MAIN(GroupedNavigationTest)

#include "GroupedNavigationTest.moc"
