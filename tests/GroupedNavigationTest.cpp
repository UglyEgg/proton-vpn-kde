// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#include "LocationModels.h"
#include "SnapshotTestData.h"
#include "VpnController.h"
#include "VpnSettingsModel.h"

#include <QAbstractItemModel>
#include <QDBusConnection>
#include <QDBusConnectionInterface>
#include <QDBusContext>
#include <QDBusMessage>
#include <QJsonDocument>
#include <QJsonObject>
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
    int snapshotCalls = 0;
    int settingsCalls = 0;
    int settingsUpdateCalls = 0;
    int searchCalls = 0;
    int loadCalls = 0;
    int packetCaptureStartCalls = 0;
    int packetCaptureStopCalls = 0;
    int countryFailures = 0;
    int searchFailures = 0;
    int loadFailures = 0;
    int emptyGroupResponses = 0;
    int emptyServerResponses = 0;
    int invalidGroupResponses = 0;
    int invalidServerResponses = 0;
    bool rejectRegistration = false;
    bool delayLogout = false;
    bool ready = true;
    bool loggedIn = true;
    bool failNextSettingsUpdateAsNoReply = false;
    bool failNextPacketCaptureOperation = false;
    bool packetCaptureActive = false;
    int settingsNetShield = 0;
    int snapshotNoReplyFailures = 0;
    QString connectionState = QStringLiteral("disconnected");
    QString lastCountry;
    QString lastGroupKind;
    QString lastGroupName;
    QStringList lastCapabilities;
    QStringList browseCallOrder;
    QDBusMessage delayedLogoutMessage;

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

    void Logout()
    {
        if (!delayLogout) {
            return;
        }
        setDelayedReply(true);
        delayedLogoutMessage = message();
    }

    QString GetSnapshot()
    {
        ++snapshotCalls;
        if (snapshotNoReplyFailures > 0) {
            --snapshotNoReplyFailures;
            sendErrorReply(QDBusError::NoReply,
                           QStringLiteral("transient snapshot timeout"));
            return {};
        }
        QJsonDocument document = QJsonDocument::fromJson(
            ProtonVpnKde::TestData::completeSnapshot(
                connectionState, loggedIn, ready).toUtf8());
        QJsonObject snapshot = document.object();
        snapshot.insert(QStringLiteral("packetCaptureActive"),
                        packetCaptureActive);
        return QString::fromUtf8(
            QJsonDocument(snapshot).toJson(QJsonDocument::Compact));
    }

    QString GetCountries()
    {
        ++countryCalls;
        browseCallOrder.append(QStringLiteral("countries"));
        if (countryFailures > 0) {
            --countryFailures;
            sendErrorReply(QDBusError::Failed,
                           QStringLiteral("country read failed"));
            return {};
        }
        return QStringLiteral(R"json({
            "schemaVersion":1,
            "countries":[
                {"code":"CH","serverCount":4,"accessible":true},
                {"code":"US","serverCount":5,"accessible":true}
            ]
        })json");
    }

    QString SearchLocations(const QString &)
    {
        ++searchCalls;
        if (searchFailures > 0) {
            --searchFailures;
            sendErrorReply(QDBusError::Failed,
                           QStringLiteral("location search failed"));
            return {};
        }
        return QStringLiteral(
            R"json({"schemaVersion":1,"results":[]})json");
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

    QString GetSettings()
    {
        ++settingsCalls;
        return QStringLiteral(R"json({
            "schemaVersion":1,
            "protocol":"wireguard",
            "protocols":[{"id":"wireguard","name":"WireGuard"}],
            "killSwitch":0,
            "netShield":%1,
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
        })json").arg(settingsNetShield);
    }

    QString UpdateSettings(const QString &patchJson)
    {
        ++settingsUpdateCalls;
        const QJsonDocument document = QJsonDocument::fromJson(
            patchJson.toUtf8());
        if (document.isObject()
            && document.object().value(QStringLiteral("netShield")).isDouble()) {
            settingsNetShield = document.object()
                                    .value(QStringLiteral("netShield"))
                                    .toInt();
        }
        if (failNextSettingsUpdateAsNoReply) {
            failNextSettingsUpdateAsNoReply = false;
            sendErrorReply(QDBusError::NoReply,
                           QStringLiteral("settings completion unknown"));
            return {};
        }
        return GetSettings();
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
        if (invalidGroupResponses > 0) {
            --invalidGroupResponses;
            return QStringLiteral(
                R"json({"schemaVersion":2,"groups":[]})json");
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
        if (invalidServerResponses > 0) {
            --invalidServerResponses;
            return QStringLiteral(
                R"json({"schemaVersion":2,"servers":[]})json");
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

    QString GetServerLoads(const QString &)
    {
        ++loadCalls;
        if (loadFailures > 0) {
            --loadFailures;
            sendErrorReply(QDBusError::Failed,
                           QStringLiteral("server load read failed"));
            return {};
        }
        return QStringLiteral(R"json({
            "schemaVersion":1,
            "loads":[
                {"name":"CH#101","load":31},
                {"name":"CH#202","load":52}
            ]
        })json");
    }

    void StartPacketCapture(const QString &)
    {
        ++packetCaptureStartCalls;
        if (failNextPacketCaptureOperation) {
            failNextPacketCaptureOperation = false;
            sendErrorReply(QDBusError::Failed,
                           QStringLiteral("packet capture start failed"));
            return;
        }
        packetCaptureActive = true;
    }

    void StopPacketCapture()
    {
        ++packetCaptureStopCalls;
        if (failNextPacketCaptureOperation) {
            failNextPacketCaptureOperation = false;
            sendErrorReply(QDBusError::Failed,
                           QStringLiteral("packet capture stop failed"));
            return;
        }
        packetCaptureActive = false;
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
    void ignoresOperationReplyFromReplacedBackend();
    void retriesSnapshotAfterTransientSameOwnerFailure();
    void invalidSnapshotOwnsGlobalHealthError();
    void packetCaptureFailuresHaveTypedCompletionState();
    void reconcilesSettingsAfterCompletionUnknownMutation();
    void stopsRetryingAnUnresponsiveSameOwner();
    void queuesInitialBrowserLoadUntilBackendIsReady();
    void loadsCountryGroupsAndTheirServersWithoutAFlatEndpoint();
    void retriesTransientEmptyServerGroupResponses();
    void retriesTransientEmptyServerResponse();
    void browserFailuresAreDistinctFromEmptyResults();
    void supplementalLoadFailuresPreserveAuthoritativeEmptyResults();
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

void GroupedNavigationTest::ignoresOperationReplyFromReplacedBackend()
{
    m_backend.delayLogout = true;
    m_backend.delayedLogoutMessage = {};
    VpnController controller(nullptr, false);
    QTRY_VERIFY_WITH_TIMEOUT(controller.backendAvailable(), 2000);
    QTRY_VERIFY_WITH_TIMEOUT(controller.ready(), 2000);
    QTRY_VERIFY_WITH_TIMEOUT(controller.loggedIn(), 2000);

    controller.logout();
    QTRY_COMPARE_WITH_TIMEOUT(
        m_backend.delayedLogoutMessage.type(),
        QDBusMessage::MethodCallMessage, 2000);

    QVERIFY(m_backendBus->unregisterService(
        QString::fromLatin1(kBackendService)));
    QTRY_VERIFY_WITH_TIMEOUT(!controller.backendAvailable(), 2000);

    constexpr auto replacementConnectionName =
        "grouped-navigation-replacement-backend";
    GroupedNavigationBackend replacement;
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
    QTRY_VERIFY_WITH_TIMEOUT(controller.backendAvailable(), 2000);
    QTRY_VERIFY_WITH_TIMEOUT(controller.ready(), 2000);
    const QString replacementMessage = controller.message();

    const QDBusMessage delayedError =
        m_backend.delayedLogoutMessage.createErrorReply(
            QStringLiteral("org.freedesktop.DBus.Error.NoReply"),
            QStringLiteral("old backend reply"));
    QVERIFY(m_backendBus->send(delayedError));
    QTest::qWait(100);
    QVERIFY(controller.backendAvailable());
    QVERIFY(controller.ready());
    QCOMPARE(controller.message(), replacementMessage);

    QVERIFY(replacementBus.unregisterService(
        QString::fromLatin1(kBackendService)));
    replacementBus.unregisterObject(QString::fromLatin1(kBackendPath));
    QDBusConnection::disconnectFromBus(
        QString::fromLatin1(replacementConnectionName));
    qputenv("PROTON_VPN_KDE_TEST_BACKEND_OWNER",
            m_backendBus->baseService().toUtf8());
    QVERIFY(m_backendBus->registerService(QString::fromLatin1(kBackendService)));
    m_backend.delayLogout = false;
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
        QVERIFY(!controller.backendRestartAllowed());
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

void GroupedNavigationTest::retriesSnapshotAfterTransientSameOwnerFailure()
{
    VpnController controller(nullptr, false);
    QTRY_VERIFY_WITH_TIMEOUT(controller.backendAvailable(), 2000);
    QTRY_VERIFY_WITH_TIMEOUT(controller.ready(), 2000);

    const int snapshotCallsBefore = m_backend.snapshotCalls;
    m_backend.snapshotNoReplyFailures = 1;
    controller.refresh();

    QTRY_COMPARE_WITH_TIMEOUT(
        m_backend.snapshotCalls, snapshotCallsBefore + 1, 2000);
    QVERIFY(controller.backendAvailable());
    QTRY_COMPARE_WITH_TIMEOUT(
        m_backend.snapshotCalls, snapshotCallsBefore + 2, 2500);
    QVERIFY(controller.backendAvailable());
    QVERIFY(controller.ready());
    QTRY_VERIFY_WITH_TIMEOUT(controller.snapshotError().isEmpty(), 2000);
}

void GroupedNavigationTest::invalidSnapshotOwnsGlobalHealthError()
{
    VpnController controller(nullptr, false);
    QTRY_VERIFY_WITH_TIMEOUT(controller.backendAvailable(), 2000);
    QTRY_VERIFY_WITH_TIMEOUT(controller.ready(), 2000);

    controller.applySnapshot(ProtonVpnKde::TestData::completeSnapshot(
        QStringLiteral("connected")));
    QCOMPARE(controller.state(), QStringLiteral("connected"));
    QVERIFY(controller.snapshotError().isEmpty());

    const QStringList invalidSnapshots{
        QStringLiteral("{"),
        QStringLiteral(R"json({"schemaVersion":2})json"),
        QStringLiteral(R"json({"schemaVersion":1})json"),
    };
    for (const QString &snapshot : invalidSnapshots) {
        controller.applySnapshot(snapshot);
        QCOMPARE(controller.state(), QStringLiteral("connected"));
        QVERIFY(!controller.snapshotError().isEmpty());

        controller.applySnapshot(ProtonVpnKde::TestData::completeSnapshot(
            QStringLiteral("connected")));
        QVERIFY(controller.snapshotError().isEmpty());
    }
}

void GroupedNavigationTest::packetCaptureFailuresHaveTypedCompletionState()
{
    m_backend.connectionState = QStringLiteral("connected");
    m_backend.packetCaptureActive = false;
    m_backend.failNextPacketCaptureOperation = false;
    m_backend.publishSession(true, true);
    VpnController controller(nullptr, false);

    QTRY_VERIFY_WITH_TIMEOUT(controller.backendAvailable(), 2000);
    QTRY_COMPARE_WITH_TIMEOUT(
        controller.state(), QStringLiteral("connected"), 2000);
    QSignalSpy completion(
        &controller,
        &VpnController::packetCaptureOperationFinished);

    const int startCallsBeforeInvalidPath = m_backend.packetCaptureStartCalls;
    controller.startPacketCapture(QStringLiteral("\n"));
    QCOMPARE(m_backend.packetCaptureStartCalls, startCallsBeforeInvalidPath);
    QCOMPARE(completion.count(), 1);
    QCOMPARE(completion.constLast().at(0).toBool(), true);
    QCOMPARE(completion.constLast().at(1).toBool(), false);
    QVERIFY(!controller.packetCaptureError().isEmpty());
    completion.clear();

    m_backend.failNextPacketCaptureOperation = true;
    controller.startPacketCapture(QStringLiteral("/tmp"));
    QTRY_COMPARE_WITH_TIMEOUT(completion.count(), 1, 2000);
    QCOMPARE(completion.constLast().at(0).toBool(), true);
    QCOMPARE(completion.constLast().at(1).toBool(), false);
    QVERIFY(!controller.packetCaptureError().isEmpty());
    QVERIFY(!controller.packetCaptureActive());

    controller.startPacketCapture(QStringLiteral("/tmp"));
    QTRY_COMPARE_WITH_TIMEOUT(completion.count(), 2, 2000);
    QTRY_VERIFY_WITH_TIMEOUT(controller.packetCaptureActive(), 2000);
    QCOMPARE(completion.constLast().at(0).toBool(), true);
    QCOMPARE(completion.constLast().at(1).toBool(), true);
    QVERIFY(controller.packetCaptureError().isEmpty());

    m_backend.failNextPacketCaptureOperation = true;
    controller.stopPacketCapture();
    QTRY_COMPARE_WITH_TIMEOUT(completion.count(), 3, 2000);
    QCOMPARE(completion.constLast().at(0).toBool(), false);
    QCOMPARE(completion.constLast().at(1).toBool(), false);
    QVERIFY(!controller.packetCaptureError().isEmpty());
    QVERIFY(controller.packetCaptureActive());

    const int stopCallsBeforeBusyTeardown = m_backend.packetCaptureStopCalls;
    controller.m_busy = true;
    controller.stopPacketCapture();
    QCOMPARE(m_backend.packetCaptureStopCalls, stopCallsBeforeBusyTeardown);
    QCOMPARE(completion.count(), 4);
    QCOMPARE(completion.constLast().at(0).toBool(), false);
    QCOMPARE(completion.constLast().at(1).toBool(), false);
    QVERIFY(!controller.packetCaptureError().isEmpty());

    controller.m_busy = false;
    controller.stopPacketCapture();
    QTRY_COMPARE_WITH_TIMEOUT(completion.count(), 5, 2000);
    QTRY_VERIFY_WITH_TIMEOUT(!controller.packetCaptureActive(), 2000);
    QCOMPARE(completion.constLast().at(1).toBool(), true);
    QVERIFY(controller.packetCaptureError().isEmpty());

    m_backend.connectionState = QStringLiteral("disconnected");
    m_backend.packetCaptureActive = false;
}

void GroupedNavigationTest::stopsRetryingAnUnresponsiveSameOwner()
{
    VpnController controller(nullptr, false);
    QTRY_VERIFY_WITH_TIMEOUT(controller.backendAvailable(), 2000);
    QTRY_VERIFY_WITH_TIMEOUT(controller.ready(), 2000);

    const int snapshotCallsBefore = m_backend.snapshotCalls;
    m_backend.snapshotNoReplyFailures = 5;
    controller.refresh();

    QTRY_COMPARE_WITH_TIMEOUT(
        m_backend.snapshotCalls, snapshotCallsBefore + 4, 3000);
    QTRY_COMPARE_WITH_TIMEOUT(
        controller.state(), QStringLiteral("unresponsive"), 3000);
    QVERIFY(controller.backendAvailable());
    QVERIFY(controller.backendRestartAllowed());
    QVERIFY(!controller.ready());
    QVERIFY(controller.message().contains(
        QStringLiteral("not responding"), Qt::CaseInsensitive));

    m_backend.snapshotNoReplyFailures = 0;
    QTest::qWait(1200);
    QCOMPARE(m_backend.snapshotCalls, snapshotCallsBefore + 4);
}

void GroupedNavigationTest::reconcilesSettingsAfterCompletionUnknownMutation()
{
    m_backend.publishSession(true, true);
    m_backend.settingsNetShield = 0;
    VpnController controller(nullptr, false);

    QTRY_VERIFY_WITH_TIMEOUT(controller.backendAvailable(), 2000);
    QTRY_VERIFY_WITH_TIMEOUT(controller.ready(), 2000);
    QTRY_VERIFY_WITH_TIMEOUT(controller.loggedIn(), 2000);
    QTRY_VERIFY_WITH_TIMEOUT(controller.settings()->loaded(), 2000);
    QCOMPARE(controller.settings()->netShield(), 0);

    const int settingsCallsBefore = m_backend.settingsCalls;
    const int updateCallsBefore = m_backend.settingsUpdateCalls;
    m_backend.failNextSettingsUpdateAsNoReply = true;
    controller.updateSetting(QStringLiteral("netShield"), 2);

    QTRY_COMPARE_WITH_TIMEOUT(
        m_backend.settingsUpdateCalls, updateCallsBefore + 1, 2000);
    QTRY_COMPARE_WITH_TIMEOUT(
        m_backend.settingsCalls, settingsCallsBefore + 1, 2000);
    QTRY_COMPARE_WITH_TIMEOUT(controller.settings()->netShield(), 2, 2000);
    QTRY_VERIFY_WITH_TIMEOUT(!controller.settings()->busy(), 2000);
    QVERIFY(controller.backendAvailable());
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

void GroupedNavigationTest::browserFailuresAreDistinctFromEmptyResults()
{
    m_backend.publishSession(true, true);
    VpnController controller(nullptr, false);

    QTRY_VERIFY_WITH_TIMEOUT(controller.backendAvailable(), 2000);
    QTRY_VERIFY_WITH_TIMEOUT(controller.ready(), 2000);
    QTRY_VERIFY_WITH_TIMEOUT(controller.loggedIn(), 2000);
    const QString connectionMessage = controller.message();

    m_backend.countryFailures = 1;
    controller.loadCountries();
    QTRY_VERIFY_WITH_TIMEOUT(!controller.countriesError().isEmpty(), 2000);
    QVERIFY(!controller.locationsBusy());
    QCOMPARE(controller.countryModel()->rowCount(), 0);
    QCOMPARE(controller.message(), connectionMessage);

    controller.loadCountries();
    QTRY_COMPARE_WITH_TIMEOUT(controller.countryModel()->rowCount(), 2, 2000);
    QVERIFY(controller.countriesError().isEmpty());

    m_backend.searchFailures = 1;
    controller.searchLocations(QStringLiteral("ch"));
    QTRY_VERIFY_WITH_TIMEOUT(!controller.locationSearchError().isEmpty(), 2000);
    QVERIFY(!controller.locationSearchBusy());
    controller.searchLocations(QStringLiteral("ch"));
    QTRY_VERIFY_WITH_TIMEOUT(controller.locationSearchError().isEmpty(), 2000);
    QTRY_VERIFY_WITH_TIMEOUT(!controller.locationSearchBusy(), 2000);

    m_backend.invalidGroupResponses = 1;
    controller.loadServerGroups(QStringLiteral("CH"));
    QTRY_VERIFY_WITH_TIMEOUT(!controller.serverGroupsError().isEmpty(), 2000);
    QVERIFY(!controller.locationsBusy());
    controller.loadServerGroups(QStringLiteral("CH"));
    QTRY_COMPARE_WITH_TIMEOUT(controller.serverGroupModel()->rowCount(), 2, 2000);
    QVERIFY(controller.serverGroupsError().isEmpty());

    m_backend.invalidServerResponses = 1;
    controller.loadGroupServers(QStringLiteral("CH"),
                                QStringLiteral("location"),
                                QStringLiteral("Zurich"));
    QTRY_VERIFY_WITH_TIMEOUT(!controller.serversError().isEmpty(), 2000);
    QVERIFY(!controller.locationsBusy());
    QVERIFY(controller.serverLoadsError().isEmpty());

    controller.requestServerLoads();
    QTRY_VERIFY_WITH_TIMEOUT(!controller.locationsBusy(), 2000);
    QVERIFY(!controller.serversError().isEmpty());
    QVERIFY(controller.serverLoadsError().isEmpty());

    controller.loadGroupServers(QStringLiteral("CH"),
                                QStringLiteral("location"),
                                QStringLiteral("Zurich"));
    QTRY_COMPARE_WITH_TIMEOUT(controller.serverModel()->rowCount(), 2, 2000);
    QVERIFY(controller.serversError().isEmpty());
    QVERIFY(controller.serverLoadsError().isEmpty());

    m_backend.loadFailures = 1;
    controller.requestServerLoads();
    QTRY_VERIFY_WITH_TIMEOUT(!controller.serverLoadsError().isEmpty(), 2000);
    QVERIFY(controller.serversError().isEmpty());
    QVERIFY(!controller.locationsBusy());
    controller.requestServerLoads();
    QTRY_VERIFY_WITH_TIMEOUT(controller.serverLoadsError().isEmpty(), 2000);
    QVERIFY(controller.serversError().isEmpty());
    QTRY_VERIFY_WITH_TIMEOUT(!controller.locationsBusy(), 2000);
    QCOMPARE(controller.message(), connectionMessage);
}

void GroupedNavigationTest::supplementalLoadFailuresPreserveAuthoritativeEmptyResults()
{
    m_backend.publishSession(true, true);
    VpnController controller(nullptr, false);

    QTRY_VERIFY_WITH_TIMEOUT(controller.backendAvailable(), 2000);
    QTRY_VERIFY_WITH_TIMEOUT(controller.ready(), 2000);
    QTRY_VERIFY_WITH_TIMEOUT(controller.loggedIn(), 2000);

    m_backend.emptyServerResponses = 3;
    controller.loadGroupServers(QStringLiteral("CH"),
                                QStringLiteral("location"),
                                QStringLiteral("Zurich"));
    QTRY_VERIFY_WITH_TIMEOUT(!controller.locationsBusy(), 3000);
    QCOMPARE(controller.serverModel()->rowCount(), 0);
    QVERIFY(controller.serversError().isEmpty());

    m_backend.loadFailures = 1;
    controller.requestServerLoads();
    QTRY_VERIFY_WITH_TIMEOUT(!controller.serverLoadsError().isEmpty(), 2000);
    QCOMPARE(controller.serverModel()->rowCount(), 0);
    QVERIFY(controller.serversError().isEmpty());

    controller.loadGroupServers(QStringLiteral("CH"),
                                QStringLiteral("location"),
                                QStringLiteral("Zurich"));
    QTRY_COMPARE_WITH_TIMEOUT(controller.serverModel()->rowCount(), 2, 2000);
    controller.setServerFilter(QStringLiteral("no-such-server"));
    QCOMPARE(controller.serverModel()->rowCount(), 0);

    m_backend.loadFailures = 1;
    controller.requestServerLoads();
    QTRY_VERIFY_WITH_TIMEOUT(!controller.serverLoadsError().isEmpty(), 2000);
    QCOMPARE(controller.serverModel()->rowCount(), 0);
    QVERIFY(controller.serversError().isEmpty());
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
    QSignalSpy connectionFinished(
        &controller, &VpnController::connectionOperationFinished);

    controller.setReconnectionEnabled(false);
    QTest::qWait(50);
    QCOMPARE(connectionFinished.count(), 0);

    controller.connectFastestWithFeatures(
        {QStringLiteral(" Streaming "), QStringLiteral("P2P")});
    QTRY_COMPARE_WITH_TIMEOUT(m_backend.capabilityCalls, callsBefore + 1, 2000);
    QCOMPARE(m_backend.lastCapabilities,
             QStringList({QStringLiteral("p2p"),
                          QStringLiteral("streaming")}));
    QTRY_VERIFY_WITH_TIMEOUT(!controller.busy(), 2000);
    QTRY_COMPARE_WITH_TIMEOUT(connectionFinished.count(), 1, 2000);
    QCOMPARE(connectionFinished.at(0).at(0).toString(),
             QStringLiteral("connected"));
    QVERIFY(connectionFinished.at(0).at(1).toBool());

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
