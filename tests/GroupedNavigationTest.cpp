// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#include "LocationModels.h"
#include "SnapshotTestData.h"
#include "VpnController.h"
#include "VpnSettingsModel.h"
#include "CustomDnsModel.h"
#include "SplitTunnelingModel.h"

#include <QAbstractItemModel>
#include <QDBusConnection>
#include <QDBusConnectionInterface>
#include <QDBusContext>
#include <QDBusMessage>
#include <QDBusUnixFileDescriptor>
#include <QJsonDocument>
#include <QJsonObject>
#include <QScopeGuard>
#include <QtTest>
#include <memory>
#include <openssl/evp.h>

namespace
{
constexpr auto kBackendService = "quest.entropy.PlasmaVPN.Backend";
constexpr auto kBackendPath = "/quest/entropy/PlasmaVPN/Backend";

class AccountRestartManager final : public QObject
{
    Q_OBJECT
    Q_CLASSINFO("D-Bus Interface", "org.freedesktop.systemd1.Manager")
public:
    QStringList units;
public slots:
    QDBusObjectPath RestartUnit(const QString &unit, const QString &mode)
    {
        if (mode == QStringLiteral("replace")) {
            units.append(unit);
        }
        return QDBusObjectPath(QStringLiteral("/org/freedesktop/systemd1/job/1"));
    }
};

using PKey = std::unique_ptr<EVP_PKEY, decltype(&EVP_PKEY_free)>;
using PKeyContext = std::unique_ptr<EVP_PKEY_CTX,
                                    decltype(&EVP_PKEY_CTX_free)>;

QByteArray backendPublicKey()
{
    PKeyContext context(EVP_PKEY_CTX_new_id(EVP_PKEY_X25519, nullptr),
                        EVP_PKEY_CTX_free);
    EVP_PKEY *generatedKey = nullptr;
    if (!context
        || EVP_PKEY_keygen_init(context.get()) <= 0
        || EVP_PKEY_keygen(context.get(), &generatedKey) <= 0) {
        return {};
    }
    PKey key(generatedKey, EVP_PKEY_free);
    QByteArray publicKey(32, '\0');
    size_t size = static_cast<size_t>(publicKey.size());
    if (EVP_PKEY_get_raw_public_key(
            key.get(), reinterpret_cast<unsigned char *>(publicKey.data()),
            &size) <= 0
        || size != 32) {
        return {};
    }
    return publicKey;
}

class GroupedNavigationBackend final : public QObject, protected QDBusContext
{
    Q_OBJECT
    Q_CLASSINFO("D-Bus Interface", "quest.entropy.PlasmaVPN.Backend1")

public:
    int registrationCalls = 0;
    int authPublicKeyCalls = 0;
    int disconnectCalls = 0;
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
    int npsSubmissionCalls = 0;
    int delayedCapabilityOperationCount = 0;
    int countryFailures = 0;
    int searchFailures = 0;
    int loadFailures = 0;
    int emptyGroupResponses = 0;
    int emptyServerResponses = 0;
    int invalidGroupResponses = 0;
    int invalidServerResponses = 0;
    bool rejectRegistration = false;
    bool delayDisconnect = false;
    bool delayReconnection = false;
    bool delayLogout = false;
    bool ready = true;
    bool loggedIn = true;
    bool failNextSettingsUpdateAsNoReply = false;
    bool delaySettings = false;
    bool delaySettingsUpdate = false;
    bool delaySearch = false;
    bool delaySnapshot = false;
    QList<QDBusMessage> delayedSettingsMessages;
    QList<QDBusMessage> delayedSettingsUpdateMessages;
    QList<QDBusMessage> delayedSearchMessages;
    QList<QDBusMessage> delayedSnapshotMessages;
    QStringList searchQueries;
    bool failNextPacketCaptureOperation = false;
    bool delayPacketCaptureStart = false;
    bool delayPacketCaptureStop = false;
    bool delayCountries = false;
    bool delayAuthPublicKey = false;
    bool delayNpsSubmission = false;
    bool failNextNpsSubmission = false;
    bool packetCaptureActive = false;
    bool operationBusy = false;
    int settingsNetShield = 0;
    int snapshotNoReplyFailures = 0;
    QString connectionState = QStringLiteral("disconnected");
    QString authStateOverride;
    QString statusMessage;
    QString lastCountry;
    QString lastGroupKind;
    QString lastGroupName;
    QStringList lastCapabilities;
    QStringList browseCallOrder;
    QDBusMessage delayedLogoutMessage;
    QDBusMessage delayedDisconnectMessage;
    QDBusMessage delayedReconnectionMessage;
    QDBusMessage delayedPacketCaptureStartMessage;
    QDBusMessage delayedPacketCaptureStopMessage;
    QDBusMessage delayedCountriesMessage;
    QDBusMessage delayedAuthPublicKeyMessage;
    QDBusMessage delayedNpsSubmissionMessage;
    QList<QDBusMessage> delayedCapabilityMessages;
    QByteArray authPublicKey = backendPublicKey();

    void publishSession(bool sessionReady, bool sessionLoggedIn)
    {
        ready = sessionReady;
        loggedIn = sessionLoggedIn;
        emit SnapshotChanged(GetSnapshot());
    }

    void holdConnectionReply()
    {
        if (delayedCapabilityOperationCount > 0) {
            --delayedCapabilityOperationCount;
            setDelayedReply(true);
            delayedCapabilityMessages.append(message());
        }
    }

signals:
    void SnapshotChanged(const QString &snapshotJson);
    void SettingsChanged(const QString &settingsJson);
    void SplitTunnelingChanged(const QString &settingsJson);
    void CustomDnsChanged(const QString &settingsJson);

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
        if (delayReconnection) {
            setDelayedReply(true);
            delayedReconnectionMessage = message();
        }
    }

    void Disconnect()
    {
        ++disconnectCalls;
        if (delayDisconnect) {
            setDelayedReply(true);
            delayedDisconnectMessage = message();
        }
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
        if (delaySnapshot && calledFromDBus()) {
            setDelayedReply(true);
            delayedSnapshotMessages.append(message());
            return {};
        }
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
        snapshot.insert(QStringLiteral("busy"), operationBusy);
        snapshot.insert(QStringLiteral("message"), statusMessage);
        if (!authStateOverride.isEmpty()) {
            snapshot.insert(QStringLiteral("authState"), authStateOverride);
        }
        snapshot.insert(QStringLiteral("packetCaptureActive"),
                        packetCaptureActive);
        return QString::fromUtf8(
            QJsonDocument(snapshot).toJson(QJsonDocument::Compact));
    }

    QString GetCountries()
    {
        ++countryCalls;
        browseCallOrder.append(QStringLiteral("countries"));
        if (delayCountries) {
            setDelayedReply(true);
            delayedCountriesMessage = message();
            return {};
        }
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

    QString SearchLocations(const QString &query)
    {
        ++searchCalls;
        searchQueries.append(query);
        if (delaySearch) {
            setDelayedReply(true);
            delayedSearchMessages.append(message());
            return {};
        }
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
        holdConnectionReply();
    }

    void ConnectFastest() { holdConnectionReply(); }
    void ConnectCountry(const QString &) { holdConnectionReply(); }
    void ConnectCountryWithFeatures(const QString &, const QStringList &) { holdConnectionReply(); }
    void ConnectGroup(const QString &, const QString &, const QString &) { holdConnectionReply(); }
    void ConnectGroupWithFeatures(const QString &, const QString &, const QString &, const QStringList &) { holdConnectionReply(); }
    void ConnectServer(const QString &) { holdConnectionReply(); }

    QString GetPendingNpsSurvey() const
    {
        return QStringLiteral(
            R"json({"schemaVersion":1,"available":false})json");
    }

    QString GetAuthPublicKey(const QString &)
    {
        ++authPublicKeyCalls;
        if (delayAuthPublicKey) {
            setDelayedReply(true);
            delayedAuthPublicKeyMessage = message();
            return {};
        }
        return QString::fromLatin1(authPublicKey.toBase64());
    }

    void SubmitNpsSurvey(const QDBusUnixFileDescriptor &)
    {
        ++npsSubmissionCalls;
        if (failNextNpsSubmission) {
            failNextNpsSubmission = false;
            sendErrorReply(QDBusError::Failed,
                           QStringLiteral("survey submission rejected"));
            return;
        }
        if (delayNpsSubmission) {
            setDelayedReply(true);
            delayedNpsSubmissionMessage = message();
        }
    }

    QString GetSettings()
    {
        ++settingsCalls;
        if (delaySettings && calledFromDBus()) {
            setDelayedReply(true);
            delayedSettingsMessages.append(message());
            return {};
        }
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
        if (delaySettingsUpdate) {
            setDelayedReply(true);
            delayedSettingsUpdateMessages.append(message());
            return {};
        }
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

    QString GetSplitTunneling()
    {
        if (delaySettings && calledFromDBus()) {
            setDelayedReply(true);
            delayedSettingsMessages.append(message());
            return {};
        }
        return QStringLiteral(R"({"schemaVersion":1,"available":true,
            "paidFeaturesAvailable":true,"enabled":false,"mode":"exclude",
            "excludeAppPaths":[],"includeAppPaths":[],"excludeIpRanges":[],
            "includeIpRanges":[],"excludeIpRangeCount":0,"includeIpRangeCount":0})");
    }

    QString UpdateSplitTunneling(const QString &)
    {
        if (delaySettingsUpdate) {
            setDelayedReply(true);
            delayedSettingsUpdateMessages.append(message());
            return {};
        }
        return GetSplitTunneling();
    }

    QString GetCustomDns()
    {
        if (delaySettings && calledFromDBus()) {
            setDelayedReply(true);
            delayedSettingsMessages.append(message());
            return {};
        }
        return QStringLiteral(R"({"schemaVersion":1,"paidFeaturesAvailable":true,
            "enabled":false,"servers":[]})");
    }

    QString UpdateCustomDns(const QString &)
    {
        if (delaySettingsUpdate) {
            setDelayedReply(true);
            delayedSettingsUpdateMessages.append(message());
            return {};
        }
        return GetCustomDns();
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
        if (delayPacketCaptureStart) {
            setDelayedReply(true);
            delayedPacketCaptureStartMessage = message();
            return;
        }
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
        if (delayedPacketCaptureStartMessage.type()
            == QDBusMessage::MethodCallMessage) {
            connection().send(
                delayedPacketCaptureStartMessage.createErrorReply(
                    QDBusError::Failed,
                    QStringLiteral("packet capture start cancelled by stop")));
            delayedPacketCaptureStartMessage = {};
        }
        if (delayPacketCaptureStop) {
            setDelayedReply(true);
            delayedPacketCaptureStopMessage = message();
            return;
        }
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
    void loggedOutActiveTunnelCanBeDisconnected();
    void connectionAdmissionAcrossDirectRoutes_data();
    void connectionAdmissionAcrossDirectRoutes();
    void accountRecoveryWaitsForRetirement_data();
    void accountRecoveryWaitsForRetirement();
    void invalidSnapshotStillAllowsCaptureStopAndRestart();
    void packetCaptureFailuresHaveTypedState();
    void rejectedCaptureStartAllowsShutdownAfterIdleSnapshot();
    void captureStartTimeoutStillAllowsShutdownStop();
    void captureStopPreemptsPendingStart();
    void captureSignalBeforeStartReplyPreservesStopOwnership();
    void shutdownWaitsForDeferredCaptureStop();
    void lateCaptureStopReplySurvivesReplacementForegroundOperation();
    void activeCaptureCanStopAfterSessionExpiry();
    void recoveryStateStillAllowsCaptureStop();
    void duplicateCaptureStopPreservesReconciliation();
    void reconcilesSettingsAfterCompletionUnknownMutation();
    void settingsSignalsDoNotCompleteRequests_data();
    void settingsSignalsDoNotCompleteRequests();
    void foregroundTimeoutWaitsForFreshIdleRead_data();
    void foregroundTimeoutWaitsForFreshIdleRead();
    void captureStateDoesNotAcknowledgeStart_data();
    void captureStateDoesNotAcknowledgeStart();
    void searchCoalescesToLatestQuery();
    void stopsRetryingAnUnresponsiveSameOwner();
    void queuesInitialBrowserLoadUntilBackendIsReady();
    void staleCountryReplyCannotMutateReplacementSession();
    void pageRetirementDispatchesPendingParentRefresh();
    void controlTimeoutDoesNotInventBackendLoss();
    void loadsCountryGroupsAndTheirServersWithoutAFlatEndpoint();
    void retriesTransientEmptyServerGroupResponses();
    void retriesTransientEmptyServerResponse();
    void supersededServerGroupRetryReleasesBrowserOwnership();
    void supersededExactServerRetryReleasesBrowserOwnership();
    void browserFailuresAreDistinctFromEmptyResults();
    void supplementalLoadFailuresPreserveAuthoritativeEmptyResults();
    void stalePageCleanupCannotClearReplacementContexts();
    void requestsFastestServerByValidatedCapabilities();
    void staleConnectionReplyCannotCompleteReplacementOperation();
    void staleConnectionReplyCannotCompleteAfterLogout();
    void staleForegroundAuthReplyCannotCorruptReplacementOperation();
    void staleControlDisconnectReplyCannotCorruptSignedOutState();
    void staleReconnectionReplyCannotCorruptForegroundOperation();
    void supportReportSubmissionFollowsBuildPolicy();
    void crashReportSubmissionFollowsBuildPolicy();
    void npsSubmissionWaitsForBackendAcceptance();
    void npsCompletionUnknownCannotBeRetried();
    void npsDismissalDoesNotOwnVpnOperationsOrGlobalGuidance();
    void rejectedNpsSubmissionCanBeRetried();
    void staleNpsKeyCannotSubmitForReplacementSession();
    void staleNpsDismissalCannotCompleteReplacementSubmission();

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
    QTRY_VERIFY_WITH_TIMEOUT(controller.snapshotError().isEmpty(), 2000);
    QVERIFY(controller.ready());
}

void GroupedNavigationTest::invalidSnapshotOwnsGlobalHealthError()
{
    VpnController controller(nullptr, false);
    QTRY_VERIFY_WITH_TIMEOUT(controller.backendAvailable(), 2000);
    QTRY_VERIFY_WITH_TIMEOUT(controller.ready(), 2000);

    controller.applySnapshot(ProtonVpnKde::TestData::completeSnapshot(
        QStringLiteral("connected")));
    QCOMPARE(controller.state(), QStringLiteral("connected"));
    QVERIFY(controller.ready());
    QVERIFY(controller.primaryActionEnabled());
    QVERIFY(controller.snapshotError().isEmpty());

    const QStringList invalidSnapshots{
        QStringLiteral("{"),
        QStringLiteral(R"json({"schemaVersion":2})json"),
        QStringLiteral(R"json({"schemaVersion":1})json"),
    };
    for (const QString &snapshot : invalidSnapshots) {
        controller.applySnapshot(snapshot);
        QCOMPARE(controller.state(), QStringLiteral("connected"));
        QVERIFY(!controller.ready());
        QVERIFY(!controller.primaryActionEnabled());
        QVERIFY(!controller.snapshotError().isEmpty());

        controller.applySnapshot(ProtonVpnKde::TestData::completeSnapshot(
            QStringLiteral("connected")));
        QVERIFY(controller.ready());
        QVERIFY(controller.primaryActionEnabled());
        QVERIFY(controller.snapshotError().isEmpty());
    }
}

void GroupedNavigationTest::loggedOutActiveTunnelCanBeDisconnected()
{
    m_backend.connectionState = QStringLiteral("connected");
    m_backend.loggedIn = false;
    VpnController controller(nullptr, false);
    QTRY_VERIFY_WITH_TIMEOUT(controller.backendAvailable(), 2000);
    QTRY_VERIFY_WITH_TIMEOUT(controller.ready(), 2000);
    QTRY_VERIFY_WITH_TIMEOUT(!controller.loggedIn(), 2000);
    QCOMPARE(controller.state(), QStringLiteral("connected"));
    QVERIFY(controller.primaryActionEnabled());

    const int disconnectBaseline = m_backend.disconnectCalls;
    controller.activatePrimaryAction();
    QTRY_COMPARE_WITH_TIMEOUT(
        m_backend.disconnectCalls, disconnectBaseline + 1, 2000);

    m_backend.connectionState = QStringLiteral("disconnected");
    m_backend.loggedIn = true;
}

void GroupedNavigationTest::connectionAdmissionAcrossDirectRoutes_data()
{
    QTest::addColumn<QString>("state");
    QTest::addColumn<bool>("busy");
    QTest::addColumn<bool>("loggedIn");
    QTest::addColumn<QString>("authState");
    QTest::addColumn<bool>("healthy");
    QTest::addColumn<bool>("disconnectAllowed");
    QTest::newRow("pending-lookup") << QStringLiteral("disconnected") << true << true
        << QStringLiteral("signed_in") << true << true;
    QTest::newRow("connecting") << QStringLiteral("connecting") << true << true
        << QStringLiteral("signed_in") << true << true;
    QTest::newRow("expired-tunnel") << QStringLiteral("connected") << false << false
        << QStringLiteral("expired") << true << true;
    QTest::newRow("unknown-account") << QStringLiteral("connected") << false << true
        << QStringLiteral("authentication_unknown") << true << true;
    QTest::newRow("bad-snapshot") << QStringLiteral("connected") << false << true
        << QStringLiteral("signed_in") << false << false;
    QTest::newRow("already-disconnecting") << QStringLiteral("disconnecting") << true << true
        << QStringLiteral("signed_in") << true << false;
}

void GroupedNavigationTest::connectionAdmissionAcrossDirectRoutes()
{
    QFETCH(QString, state);
    QFETCH(bool, busy);
    QFETCH(bool, loggedIn);
    QFETCH(QString, authState);
    QFETCH(bool, healthy);
    QFETCH(bool, disconnectAllowed);
    m_backend.connectionState = state;
    m_backend.operationBusy = busy;
    m_backend.loggedIn = loggedIn;
    m_backend.authStateOverride = authState;
    const auto cleanup = qScopeGuard([&] {
        m_backend.connectionState = QStringLiteral("disconnected");
        m_backend.operationBusy = false;
        m_backend.loggedIn = true;
        m_backend.authStateOverride.clear();
    });
    VpnController controller(nullptr, false);
    QTRY_VERIFY_WITH_TIMEOUT(controller.backendAvailable(), 2000);
    QTRY_VERIFY_WITH_TIMEOUT(controller.ready(), 2000);
    QCOMPARE(controller.busy(), busy);
    if (!healthy) {
        controller.applySnapshot(QStringLiteral("{"));
    }
    QVERIFY(!controller.canConnect());
    QCOMPARE(controller.canDisconnect(), disconnectAllowed);
    // Every direct connection route must guard Up, not borrow permission to
    // cancel Down from the primary action.
    QSignalSpy operations(&controller, &VpnController::connectionOperationStarted);
    controller.connectTarget(QStringLiteral("FASTEST"));
    controller.connectCountry(QStringLiteral("CH"));
    controller.connectCountryWithFeatures(QStringLiteral("CH"), {QStringLiteral("p2p")});
    controller.connectServer(QStringLiteral("CH#1"));
    controller.connectFastestWithFeatures({});
    controller.connectFastestWithFeature(QStringLiteral("p2p"));
    controller.connectGroup(QStringLiteral("US"), QStringLiteral("location"), QStringLiteral("NY"));
    controller.connectGroupWithFeatures(
        QStringLiteral("US"), QStringLiteral("location"), QStringLiteral("NY"), {});
    QCOMPARE(operations.count(), 0);

    const int before = m_backend.disconnectCalls;
    controller.disconnect();
    if (disconnectAllowed) {
        QTRY_COMPARE_WITH_TIMEOUT(m_backend.disconnectCalls, before + 1, 2000);
        QCOMPARE(operations.count(), 1);
        QCOMPARE(operations.first().at(1).toString(), QStringLiteral("disconnected"));
    } else {
        QCOMPARE(operations.count(), 0);
        QCOMPARE(m_backend.disconnectCalls, before);
    }
}

void GroupedNavigationTest::accountRecoveryWaitsForRetirement_data()
{
    QTest::addColumn<bool>("succeeds");
    QTest::newRow("confirmed") << true;
    QTest::newRow("unconfirmed") << false;
}

void GroupedNavigationTest::accountRecoveryWaitsForRetirement()
{
    QFETCH(bool, succeeds);
    AccountRestartManager manager;
    auto bus = QDBusConnection::sessionBus();
    QVERIFY(bus.registerService(QStringLiteral("org.freedesktop.systemd1")));
    const auto cleanup = qScopeGuard([&] {
        bus.unregisterObject(QStringLiteral("/org/freedesktop/systemd1"));
        bus.unregisterService(QStringLiteral("org.freedesktop.systemd1"));
        m_backend.delayLogout = false;
        m_backend.delayedLogoutMessage = {};
        m_backend.authStateOverride.clear();
        m_backend.connectionState = QStringLiteral("disconnected");
        m_backend.loggedIn = true;
    });
    QVERIFY(bus.registerObject(QStringLiteral("/org/freedesktop/systemd1"),
                               &manager, QDBusConnection::ExportAllSlots));
    m_backend.loggedIn = false;
    m_backend.authStateOverride = QStringLiteral("expired");
    m_backend.connectionState = QStringLiteral("connected");
    m_backend.delayLogout = true;
    VpnController controller(nullptr, false);
    QTRY_VERIFY_WITH_TIMEOUT(controller.ready(), 2000);
    QTRY_COMPARE(controller.authState(), QStringLiteral("expired"));
    const int keyReads = m_backend.authPublicKeyCalls;
    controller.login(QStringLiteral("unused"), QStringLiteral("unused"));
    QVERIFY(!controller.busy());
    controller.restartBackend();
    QTRY_COMPARE(m_backend.delayedLogoutMessage.type(), QDBusMessage::MethodCallMessage);
    QVERIFY(manager.units.isEmpty());
    // A snapshot alone cannot authorize restart before the accepted operation
    // has returned. No password is queued for replay into the next owner.
    m_backend.authStateOverride = QStringLiteral("account_restart_required");
    m_backend.publishSession(true, false);
    QTRY_COMPARE(controller.authState(), QStringLiteral("account_restart_required"));
    QVERIFY(manager.units.isEmpty());
    if (succeeds) {
        QVERIFY(bus.send(m_backend.delayedLogoutMessage.createReply()));
        QTRY_COMPARE(manager.units.size(), 1);
        QCOMPARE(manager.units.first(), QStringLiteral("proton-vpn-kde-backend.service"));
    } else {
        QVERIFY(bus.send(m_backend.delayedLogoutMessage.createErrorReply(
            QDBusError::Failed, QStringLiteral("Tunnel retirement unconfirmed"))));
        QTRY_VERIFY(!controller.busy());
        QVERIFY(manager.units.isEmpty());
    }
    controller.login(QStringLiteral("unused"), QStringLiteral("unused"));
    QCOMPARE(m_backend.authPublicKeyCalls, keyReads);
}

void GroupedNavigationTest::invalidSnapshotStillAllowsCaptureStopAndRestart()
{
    m_backend.connectionState = QStringLiteral("connected");
    m_backend.packetCaptureActive = true;
    m_backend.publishSession(true, true);
    VpnController controller(nullptr, false);

    QTRY_VERIFY_WITH_TIMEOUT(controller.packetCaptureActive(), 2000);
    const int startsBefore = m_backend.packetCaptureStartCalls;
    const int settingsUpdatesBefore = m_backend.settingsUpdateCalls;
    const int stopsBefore = m_backend.packetCaptureStopCalls;

    controller.applySnapshot(QStringLiteral("{"));
    QVERIFY(!controller.ready());
    controller.startPacketCapture(QStringLiteral("/tmp"));
    controller.updateSetting(QStringLiteral("netShield"), 2);
    QCOMPARE(m_backend.packetCaptureStartCalls, startsBefore);
    QCOMPARE(m_backend.settingsUpdateCalls, settingsUpdatesBefore);

    controller.restartBackend();
    QVERIFY(controller.message().contains(
        QStringLiteral("Restarting"), Qt::CaseInsensitive));

    controller.stopPacketCapture();
    QTRY_COMPARE_WITH_TIMEOUT(
        m_backend.packetCaptureStopCalls, stopsBefore + 1, 2000);
    QTRY_VERIFY_WITH_TIMEOUT(!controller.packetCaptureActive(), 2000);
    QVERIFY(controller.snapshotError().isEmpty());

    m_backend.connectionState = QStringLiteral("disconnected");
    m_backend.packetCaptureActive = false;
}

void GroupedNavigationTest::packetCaptureFailuresHaveTypedState()
{
    m_backend.connectionState = QStringLiteral("connected");
    m_backend.packetCaptureActive = false;
    m_backend.failNextPacketCaptureOperation = false;
    m_backend.publishSession(true, true);
    VpnController controller(nullptr, false);

    QTRY_VERIFY_WITH_TIMEOUT(controller.backendAvailable(), 2000);
    QTRY_COMPARE_WITH_TIMEOUT(
        controller.state(), QStringLiteral("connected"), 2000);
    const int startCallsBeforeInvalidPath = m_backend.packetCaptureStartCalls;
    controller.startPacketCapture(QStringLiteral("\n"));
    QCOMPARE(m_backend.packetCaptureStartCalls, startCallsBeforeInvalidPath);
    QVERIFY(!controller.packetCaptureError().isEmpty());

    m_backend.failNextPacketCaptureOperation = true;
    controller.startPacketCapture(QStringLiteral("/tmp"));
    QTRY_VERIFY_WITH_TIMEOUT(!controller.packetCaptureError().isEmpty(), 2000);
    QVERIFY(!controller.packetCaptureActive());

    controller.startPacketCapture(QStringLiteral("/tmp"));
    QTRY_VERIFY_WITH_TIMEOUT(controller.packetCaptureActive(), 2000);
    QVERIFY(controller.packetCaptureError().isEmpty());

    m_backend.failNextPacketCaptureOperation = true;
    controller.stopPacketCapture();
    QTRY_VERIFY_WITH_TIMEOUT(!controller.packetCaptureError().isEmpty(), 2000);
    QVERIFY(controller.packetCaptureActive());

    m_backend.packetCaptureActive = false;
    m_backend.publishSession(true, true);
    QTRY_VERIFY_WITH_TIMEOUT(!controller.packetCaptureActive(), 2000);
    QVERIFY(controller.packetCaptureError().isEmpty());

    controller.startPacketCapture(QStringLiteral("/tmp"));
    QTRY_VERIFY_WITH_TIMEOUT(controller.packetCaptureActive(), 2000);
    m_backend.failNextPacketCaptureOperation = true;
    controller.stopPacketCapture();
    QTRY_VERIFY_WITH_TIMEOUT(!controller.packetCaptureError().isEmpty(), 2000);
    QVERIFY(controller.packetCaptureActive());
    QVERIFY(!controller.m_packetCaptureOperationPending);

    const int stopCallsBeforeRetry = m_backend.packetCaptureStopCalls;
    controller.stopPacketCapture();
    QTRY_COMPARE_WITH_TIMEOUT(
        m_backend.packetCaptureStopCalls, stopCallsBeforeRetry + 1, 2000);
    QTRY_VERIFY_WITH_TIMEOUT(!controller.packetCaptureActive(), 2000);
    QVERIFY(controller.packetCaptureError().isEmpty());

    m_backend.failNextPacketCaptureOperation = true;
    controller.startPacketCapture(QStringLiteral("/tmp"));
    QTRY_VERIFY_WITH_TIMEOUT(!controller.packetCaptureError().isEmpty(), 2000);
    m_backend.publishSession(true, false);
    QTRY_VERIFY_WITH_TIMEOUT(!controller.loggedIn(), 2000);
    QVERIFY(controller.packetCaptureError().isEmpty());
    QVERIFY(!controller.m_packetCaptureExpectedActive.has_value());
    QVERIFY(!controller.m_packetCaptureOperationPending);
    QVERIFY(!controller.m_packetCaptureStopRequested);

    m_backend.connectionState = QStringLiteral("disconnected");
    m_backend.packetCaptureActive = false;
    m_backend.publishSession(true, true);
}

void GroupedNavigationTest::rejectedCaptureStartAllowsShutdownAfterIdleSnapshot()
{
    m_backend.connectionState = QStringLiteral("connected");
    m_backend.packetCaptureActive = false;
    m_backend.failNextPacketCaptureOperation = true;
    m_backend.publishSession(true, true);
    VpnController controller(nullptr, false);

    QTRY_VERIFY_WITH_TIMEOUT(controller.ready(), 2000);
    controller.startPacketCapture(QStringLiteral("/tmp"));
    QTRY_VERIFY_WITH_TIMEOUT(!controller.packetCaptureError().isEmpty(), 2000);
    QTRY_VERIFY_WITH_TIMEOUT(!controller.m_packetCaptureOperationPending, 2000);

    m_backend.publishSession(true, true);
    QTRY_VERIFY_WITH_TIMEOUT(
        !controller.m_packetCaptureExpectedActive.has_value(), 2000);
    QVERIFY(controller.requestShutdown());

    m_backend.connectionState = QStringLiteral("disconnected");
    m_backend.packetCaptureActive = false;
}

void GroupedNavigationTest::captureStartTimeoutStillAllowsShutdownStop()
{
    m_backend.connectionState = QStringLiteral("connected");
    m_backend.packetCaptureActive = false;
    m_backend.operationBusy = false;
    m_backend.delayPacketCaptureStart = true;
    m_backend.delayedPacketCaptureStartMessage = {};
    m_backend.publishSession(true, true);
    VpnController controller(nullptr, false);
    QSignalSpy shutdownSpy(&controller, &VpnController::shutdownReady);

    QTRY_VERIFY_WITH_TIMEOUT(controller.ready(), 2000);
    const int stopsBefore = m_backend.packetCaptureStopCalls;
    controller.startPacketCapture(QStringLiteral("/tmp"));
    QTRY_COMPARE_WITH_TIMEOUT(
        m_backend.delayedPacketCaptureStartMessage.type(),
        QDBusMessage::MethodCallMessage, 2000);

    const QDBusMessage delayedStart =
        m_backend.delayedPacketCaptureStartMessage;
    m_backend.delayedPacketCaptureStartMessage = {};
    m_backend.operationBusy = true;
    QVERIFY(m_backendBus->send(delayedStart.createErrorReply(
        QDBusError::NoReply,
        QStringLiteral("packet capture completion unknown"))));
    QTRY_VERIFY_WITH_TIMEOUT(
        !controller.m_packetCaptureOperationPending, 2000);
    QVERIFY(controller.m_packetCaptureExpectedActive.value_or(false));

    QVERIFY(!controller.requestShutdown());
    QTRY_COMPARE_WITH_TIMEOUT(
        m_backend.packetCaptureStopCalls, stopsBefore + 1, 2000);
    QTRY_COMPARE_WITH_TIMEOUT(shutdownSpy.count(), 1, 2000);
    QTRY_VERIFY_WITH_TIMEOUT(
        !controller.m_packetCaptureExpectedActive.has_value(), 2000);
    QVERIFY(!controller.m_packetCaptureStopRequested);
    QVERIFY(controller.requestShutdown());

    m_backend.operationBusy = false;
    m_backend.delayPacketCaptureStart = false;
    m_backend.connectionState = QStringLiteral("disconnected");
    m_backend.packetCaptureActive = false;
}

void GroupedNavigationTest::captureStopPreemptsPendingStart()
{
    m_backend.connectionState = QStringLiteral("connected");
    m_backend.packetCaptureActive = false;
    m_backend.delayPacketCaptureStart = true;
    m_backend.delayPacketCaptureStop = false;
    m_backend.delayedPacketCaptureStartMessage = {};
    m_backend.publishSession(true, true);
    VpnController controller(nullptr, false);

    QTRY_VERIFY_WITH_TIMEOUT(controller.backendAvailable(), 2000);
    QTRY_COMPARE_WITH_TIMEOUT(
        controller.state(), QStringLiteral("connected"), 2000);
    const int startCallsBefore = m_backend.packetCaptureStartCalls;
    const int stopCallsBefore = m_backend.packetCaptureStopCalls;
    controller.startPacketCapture(QStringLiteral("/tmp"));
    QTRY_COMPARE_WITH_TIMEOUT(
        m_backend.packetCaptureStartCalls, startCallsBefore + 1, 2000);
    QTRY_COMPARE_WITH_TIMEOUT(
        m_backend.delayedPacketCaptureStartMessage.type(),
        QDBusMessage::MethodCallMessage, 2000);

    controller.stopPacketCapture();
    QVERIFY(controller.m_packetCaptureStopRequested);
    QVERIFY(controller.m_packetCaptureOperationPending);
    QTRY_COMPARE_WITH_TIMEOUT(
        m_backend.packetCaptureStopCalls, stopCallsBefore + 1, 2000);
    QTRY_VERIFY_WITH_TIMEOUT(!controller.m_packetCaptureStopRequested, 3000);
    QVERIFY(!controller.packetCaptureActive());
    QVERIFY(!controller.m_packetCaptureStopRequested);
    QVERIFY(!controller.m_packetCaptureOperationPending);
    QVERIFY(!controller.m_packetCaptureExpectedActive.has_value());
    QVERIFY(controller.packetCaptureError().isEmpty());

    m_backend.connectionState = QStringLiteral("disconnected");
    m_backend.packetCaptureActive = false;
}

void GroupedNavigationTest::captureSignalBeforeStartReplyPreservesStopOwnership()
{
    m_backend.connectionState = QStringLiteral("connected");
    m_backend.packetCaptureActive = false;
    m_backend.delayPacketCaptureStart = true;
    m_backend.delayPacketCaptureStop = true;
    m_backend.delayedPacketCaptureStartMessage = {};
    m_backend.delayedPacketCaptureStopMessage = {};
    m_backend.publishSession(true, true);
    VpnController controller(nullptr, false);

    QTRY_VERIFY_WITH_TIMEOUT(controller.ready(), 2000);
    const int startsBefore = m_backend.packetCaptureStartCalls;
    const int stopsBefore = m_backend.packetCaptureStopCalls;
    controller.startPacketCapture(QStringLiteral("/tmp"));
    QTRY_COMPARE_WITH_TIMEOUT(
        m_backend.packetCaptureStartCalls, startsBefore + 1, 2000);

    m_backend.packetCaptureActive = true;
    m_backend.publishSession(true, true);
    controller.stopPacketCapture();
    QTRY_COMPARE_WITH_TIMEOUT(
        m_backend.packetCaptureStopCalls, stopsBefore + 1, 2000);
    QVERIFY(controller.m_packetCaptureOperationPending);
    QVERIFY(controller.m_packetCaptureExpectedActive.has_value());
    QVERIFY(!*controller.m_packetCaptureExpectedActive);

    m_backend.packetCaptureActive = false;
    QVERIFY(m_backendBus->send(
        m_backend.delayedPacketCaptureStopMessage.createReply()));
    QTRY_VERIFY_WITH_TIMEOUT(!controller.packetCaptureActive(), 2000);
    QVERIFY(!controller.m_packetCaptureOperationPending);
    QVERIFY(!controller.m_packetCaptureExpectedActive.has_value());
    QVERIFY(!controller.m_packetCaptureStopRequested);

    m_backend.delayPacketCaptureStart = false;
    m_backend.delayPacketCaptureStop = false;
    m_backend.connectionState = QStringLiteral("disconnected");
}

void GroupedNavigationTest::shutdownWaitsForDeferredCaptureStop()
{
    m_backend.connectionState = QStringLiteral("connected");
    m_backend.packetCaptureActive = false;
    m_backend.delayPacketCaptureStart = true;
    m_backend.delayPacketCaptureStop = true;
    m_backend.delayedPacketCaptureStartMessage = {};
    m_backend.delayedPacketCaptureStopMessage = {};
    m_backend.publishSession(true, true);
    VpnController controller(nullptr, false);
    QSignalSpy shutdownSpy(&controller, &VpnController::shutdownReady);

    QTRY_VERIFY_WITH_TIMEOUT(controller.ready(), 2000);
    const int stopsBefore = m_backend.packetCaptureStopCalls;
    controller.startPacketCapture(QStringLiteral("/tmp"));
    QTRY_COMPARE_WITH_TIMEOUT(
        m_backend.delayedPacketCaptureStartMessage.type(),
        QDBusMessage::MethodCallMessage, 2000);
    QVERIFY(!controller.requestShutdown());
    QVERIFY(controller.shutdownPending());
    QCOMPARE(shutdownSpy.count(), 0);

    QTRY_COMPARE_WITH_TIMEOUT(
        m_backend.packetCaptureStopCalls, stopsBefore + 1, 2000);
    QCOMPARE(shutdownSpy.count(), 0);

    m_backend.packetCaptureActive = false;
    QVERIFY(m_backendBus->send(
        m_backend.delayedPacketCaptureStopMessage.createReply()));
    QTRY_COMPARE_WITH_TIMEOUT(shutdownSpy.count(), 1, 2000);
    QVERIFY(!controller.shutdownPending());
    QVERIFY(!controller.packetCaptureActive());
    QVERIFY(controller.requestShutdown());

    m_backend.delayPacketCaptureStart = false;
    m_backend.delayPacketCaptureStop = false;
    m_backend.connectionState = QStringLiteral("disconnected");
}

void GroupedNavigationTest::lateCaptureStopReplySurvivesReplacementForegroundOperation()
{
    m_backend.connectionState = QStringLiteral("connected");
    m_backend.packetCaptureActive = true;
    m_backend.delayPacketCaptureStop = true;
    m_backend.delayedPacketCaptureStopMessage = {};
    m_backend.delayedCapabilityOperationCount = 1;
    m_backend.delayedCapabilityMessages.clear();
    m_backend.publishSession(true, true);
    VpnController controller(nullptr, false);
    QSignalSpy shutdownSpy(&controller, &VpnController::shutdownReady);

    QTRY_VERIFY_WITH_TIMEOUT(controller.packetCaptureActive(), 2000);
    QVERIFY(!controller.requestShutdown());
    QTRY_COMPARE_WITH_TIMEOUT(
        m_backend.delayedPacketCaptureStopMessage.type(),
        QDBusMessage::MethodCallMessage, 2000);

    // The backend publishes its authoritative idle state before the Stop
    // method reply, then the user starts another foreground operation.
    m_backend.packetCaptureActive = false;
    m_backend.publishSession(true, true);
    QTRY_VERIFY_WITH_TIMEOUT(!controller.busy(), 2000);
    controller.connectFastestWithFeatures({QStringLiteral("p2p")});
    QTRY_COMPARE_WITH_TIMEOUT(
        m_backend.delayedCapabilityMessages.size(), 1, 2000);
    m_backend.operationBusy = true;
    QVERIFY(controller.busy());

    QVERIFY(m_backendBus->send(
        m_backend.delayedPacketCaptureStopMessage.createReply()));
    QTRY_COMPARE_WITH_TIMEOUT(shutdownSpy.count(), 1, 2000);
    QVERIFY(!controller.m_packetCaptureOperationPending);
    QVERIFY(!controller.m_packetCaptureExpectedActive.has_value());
    QVERIFY(!controller.m_packetCaptureStopRequested);
    QVERIFY(controller.busy());

    m_backend.operationBusy = false;
    QVERIFY(m_backendBus->send(
        m_backend.delayedCapabilityMessages.at(0).createReply()));
    QTRY_VERIFY_WITH_TIMEOUT(!controller.busy(), 2000);

    m_backend.delayPacketCaptureStop = false;
    m_backend.delayedPacketCaptureStopMessage = {};
    m_backend.delayedCapabilityOperationCount = 0;
    m_backend.delayedCapabilityMessages.clear();
    m_backend.operationBusy = false;
    m_backend.connectionState = QStringLiteral("disconnected");
    m_backend.packetCaptureActive = false;
}

void GroupedNavigationTest::activeCaptureCanStopAfterSessionExpiry()
{
    m_backend.connectionState = QStringLiteral("connected");
    m_backend.packetCaptureActive = true;
    m_backend.delayPacketCaptureStop = false;
    m_backend.publishSession(true, true);
    VpnController controller(nullptr, false);

    QTRY_VERIFY_WITH_TIMEOUT(controller.packetCaptureActive(), 2000);
    const int stopsBefore = m_backend.packetCaptureStopCalls;
    m_backend.publishSession(true, false);
    QTRY_VERIFY_WITH_TIMEOUT(!controller.loggedIn(), 2000);
    controller.stopPacketCapture();

    QTRY_COMPARE_WITH_TIMEOUT(
        m_backend.packetCaptureStopCalls, stopsBefore + 1, 2000);
    QTRY_VERIFY_WITH_TIMEOUT(!controller.packetCaptureActive(), 2000);
    QVERIFY(controller.requestShutdown());

    m_backend.connectionState = QStringLiteral("disconnected");
    m_backend.packetCaptureActive = false;
    m_backend.publishSession(true, true);
}

void GroupedNavigationTest::recoveryStateStillAllowsCaptureStop()
{
    m_backend.connectionState = QStringLiteral("connected");
    m_backend.packetCaptureActive = true;
    m_backend.authStateOverride = QStringLiteral("protection_unknown");
    m_backend.publishSession(true, false);
    VpnController controller(nullptr, false);

    QTRY_VERIFY_WITH_TIMEOUT(controller.packetCaptureActive(), 2000);
    QCOMPARE(controller.authState(), QStringLiteral("protection_unknown"));
    const int stopsBefore = m_backend.packetCaptureStopCalls;
    controller.stopPacketCapture();

    QTRY_COMPARE_WITH_TIMEOUT(
        m_backend.packetCaptureStopCalls, stopsBefore + 1, 2000);
    QTRY_VERIFY_WITH_TIMEOUT(!controller.packetCaptureActive(), 2000);
    QVERIFY(controller.requestShutdown());

    m_backend.authStateOverride.clear();
    m_backend.connectionState = QStringLiteral("disconnected");
    m_backend.packetCaptureActive = false;
    m_backend.publishSession(true, true);
}

void GroupedNavigationTest::duplicateCaptureStopPreservesReconciliation()
{
    m_backend.connectionState = QStringLiteral("connected");
    m_backend.packetCaptureActive = true;
    m_backend.delayPacketCaptureStart = false;
    m_backend.delayPacketCaptureStop = true;
    m_backend.delayedPacketCaptureStopMessage = {};
    m_backend.publishSession(true, true);
    VpnController controller(nullptr, false);

    QTRY_VERIFY_WITH_TIMEOUT(controller.packetCaptureActive(), 2000);
    const int stopCallsBefore = m_backend.packetCaptureStopCalls;
    controller.stopPacketCapture();
    QTRY_COMPARE_WITH_TIMEOUT(
        m_backend.packetCaptureStopCalls, stopCallsBefore + 1, 2000);
    QTRY_COMPARE_WITH_TIMEOUT(
        m_backend.delayedPacketCaptureStopMessage.type(),
        QDBusMessage::MethodCallMessage, 2000);
    QVERIFY(controller.m_packetCaptureExpectedActive.has_value());
    QVERIFY(!*controller.m_packetCaptureExpectedActive);
    QVERIFY(controller.m_packetCaptureOperationPending);

    controller.stopPacketCapture();
    QCOMPARE(m_backend.packetCaptureStopCalls, stopCallsBefore + 1);
    QVERIFY(controller.m_packetCaptureExpectedActive.has_value());
    QVERIFY(!*controller.m_packetCaptureExpectedActive);
    QVERIFY(controller.m_packetCaptureOperationPending);

    m_backend.delayPacketCaptureStop = false;
    const QDBusMessage delayedError =
        m_backend.delayedPacketCaptureStopMessage.createErrorReply(
            QDBusError::NoReply,
            QStringLiteral("packet capture completion unknown"));
    QVERIFY(m_backendBus->send(delayedError));
    QTRY_VERIFY_WITH_TIMEOUT(!controller.packetCaptureError().isEmpty(), 2000);
    QVERIFY(controller.m_packetCaptureExpectedActive.has_value());
    QVERIFY(!*controller.m_packetCaptureExpectedActive);
    QVERIFY(!controller.m_packetCaptureOperationPending);

    m_backend.packetCaptureActive = false;
    m_backend.publishSession(true, true);
    QTRY_VERIFY_WITH_TIMEOUT(!controller.packetCaptureActive(), 2000);
    QVERIFY(controller.packetCaptureError().isEmpty());
    QVERIFY(!controller.m_packetCaptureExpectedActive.has_value());

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

void GroupedNavigationTest::settingsSignalsDoNotCompleteRequests_data()
{
    QTest::addColumn<int>("family");
    QTest::newRow("VPN") << 0;
    QTest::newRow("split tunneling") << 1;
    QTest::newRow("custom DNS") << 2;
}

void GroupedNavigationTest::settingsSignalsDoNotCompleteRequests()
{
    QFETCH(int, family);
    const auto cleanup = qScopeGuard([this] {
        m_backend.delaySettings = false;
        m_backend.delaySettingsUpdate = false;
        m_backend.delayedSettingsMessages.clear();
        m_backend.delayedSettingsUpdateMessages.clear();
    });
    m_backend.publishSession(true, true);
    VpnController controller(nullptr, false);
    QTRY_VERIFY(controller.ready());
    QTRY_VERIFY(controller.settings()->loaded());
    controller.loadSplitTunneling();
    controller.loadCustomDns();
    QTRY_VERIFY(controller.splitTunneling()->loaded());
    QTRY_VERIFY(controller.customDns()->loaded());
    QObject *model = family == 0 ? static_cast<QObject *>(controller.settings())
        : family == 1 ? static_cast<QObject *>(controller.splitTunneling())
                      : static_cast<QObject *>(controller.customDns());
    const auto update = [&controller, family] {
        if (family == 0) {
            controller.updateSetting(QStringLiteral("netShield"), 1);
        } else if (family == 1) {
            controller.updateSplitTunneling(QStringLiteral("enabled"), true);
        } else {
            controller.updateCustomDns(QStringLiteral("enabled"), true);
        }
    };
    const QString payload = family == 0 ? m_backend.GetSettings()
        : family == 1 ? m_backend.GetSplitTunneling() : m_backend.GetCustomDns();
    m_backend.delaySettingsUpdate = true;
    update();
    QTRY_COMPARE(m_backend.delayedSettingsUpdateMessages.size(), 1);
    emit m_backend.SettingsChanged(m_backend.GetSettings());
    emit m_backend.SplitTunnelingChanged(m_backend.GetSplitTunneling());
    emit m_backend.CustomDnsChanged(m_backend.GetCustomDns());
    QTest::qWait(30);
    QVERIFY(model->property("busy").toBool());
    update();
    QTest::qWait(30);
    QCOMPARE(m_backend.delayedSettingsUpdateMessages.size(), 1);

    // A timeout is not a write failure. Even a failed readback must retain
    // ownership, and another settings signal is not a readback receipt.
    m_backend.delaySettings = true;
    QVERIFY(m_backendBus->send(m_backend.delayedSettingsUpdateMessages.at(0)
        .createErrorReply(QDBusError::NoReply, QStringLiteral("unknown"))));
    QTRY_COMPARE(m_backend.delayedSettingsMessages.size(), 1);
    QVERIFY(m_backendBus->send(m_backend.delayedSettingsMessages.at(0)
        .createErrorReply(QDBusError::Failed, QStringLiteral("read failed"))));
    QTRY_VERIFY(!model->property("message").toString().isEmpty());
    QVERIFY(model->property("busy").toBool());
    update();
    QCOMPARE(m_backend.delayedSettingsUpdateMessages.size(), 1);
    m_backend.publishSession(true, true);
    QTRY_COMPARE(m_backend.delayedSettingsMessages.size(), 2);
    QVERIFY(m_backendBus->send(m_backend.delayedSettingsMessages.at(1)
        .createReply(QVariantList{payload})));
    QTRY_VERIFY(!model->property("busy").toBool());
    QVERIFY(model->property("message").toString().contains(QStringLiteral("could not be confirmed")));
    emit m_backend.SettingsChanged(m_backend.GetSettings());
    emit m_backend.SplitTunnelingChanged(m_backend.GetSplitTunneling());
    emit m_backend.CustomDnsChanged(m_backend.GetCustomDns());
    QTest::qWait(30);
    QVERIFY(model->property("message").toString().contains(QStringLiteral("could not be confirmed")));
    m_backend.delaySettings = false;
    controller.loadSettings();
    controller.loadSplitTunneling();
    controller.loadCustomDns();
    QTRY_VERIFY(!controller.settings()->busy());
    QTRY_VERIFY(!controller.splitTunneling()->busy());
    QTRY_VERIFY(!controller.customDns()->busy());
    QVERIFY(model->property("message").toString().contains(QStringLiteral("could not be confirmed")));
    update();
    QTRY_COMPARE(m_backend.delayedSettingsUpdateMessages.size(), 2);
    QVERIFY(m_backendBus->send(m_backend.delayedSettingsUpdateMessages.at(1)
        .createReply(QVariantList{payload})));
    QTRY_VERIFY(!model->property("busy").toBool());
    QVERIFY(model->property("message").toString().isEmpty());
}

void GroupedNavigationTest::foregroundTimeoutWaitsForFreshIdleRead_data()
{
    QTest::addColumn<QString>("route");
    QTest::addColumn<QString>("initialState");
    QTest::addColumn<QString>("finalState");
    QTest::addColumn<bool>("hasDiagnostic");
    const QStringList routes{QStringLiteral("fastest"), QStringLiteral("features"),
        QStringLiteral("country"), QStringLiteral("country-features"),
        QStringLiteral("group"), QStringLiteral("group-features"),
        QStringLiteral("server"), QStringLiteral("disconnect")};
    for (const auto &route : routes) {
        const QStringList startingStates{QStringLiteral("connected"),
            route == QStringLiteral("disconnect") ? QStringLiteral("error")
                                                   : QStringLiteral("disconnected")};
        for (const auto &initialState : startingStates) {
            for (const auto &finalState : {QStringLiteral("connected"), QStringLiteral("disconnected")}) {
                for (const bool diagnostic : {false, true}) {
                    const QString name = route + u'-' + initialState + u'-' + finalState
                        + (diagnostic ? QStringLiteral("-diagnostic") : QStringLiteral("-silent"));
                    QTest::newRow(qPrintable(name)) << route << initialState << finalState << diagnostic;
                }
            }
        }
    }
}

void GroupedNavigationTest::foregroundTimeoutWaitsForFreshIdleRead()
{
    QFETCH(QString, route);
    QFETCH(QString, initialState);
    QFETCH(QString, finalState);
    QFETCH(bool, hasDiagnostic);
    const bool disconnecting = route == QStringLiteral("disconnect");
    const auto cleanup = qScopeGuard([this] {
        m_backend.delayDisconnect = false;
        m_backend.delaySnapshot = false;
        m_backend.operationBusy = false;
        m_backend.statusMessage.clear();
        m_backend.connectionState = QStringLiteral("disconnected");
        m_backend.delayedDisconnectMessage = {};
        m_backend.delayedSnapshotMessages.clear();
        m_backend.delayedCapabilityOperationCount = 0;
        m_backend.delayedCapabilityMessages.clear();
    });
    m_backend.connectionState = initialState;
    m_backend.publishSession(true, true);
    VpnController controller(nullptr, false);
    QSignalSpy finished(&controller, &VpnController::connectionOperationFinished);
    QTRY_VERIFY(controller.ready());
    QTRY_VERIFY(controller.settings()->loaded());
    m_backend.delayDisconnect = true;
    m_backend.delayedCapabilityOperationCount = 1;
    if (disconnecting) {
        controller.disconnect();
        QTRY_COMPARE(m_backend.delayedDisconnectMessage.type(), QDBusMessage::MethodCallMessage);
    } else {
        if (route == QStringLiteral("fastest")) {
            controller.connectFastestWithFeatures({});
        } else if (route == QStringLiteral("features")) {
            controller.connectFastestWithFeatures({QStringLiteral("p2p")});
        } else if (route == QStringLiteral("country")) {
            controller.connectCountry(QStringLiteral("CH"));
        } else if (route == QStringLiteral("country-features")) {
            controller.connectCountryWithFeatures(QStringLiteral("CH"), {QStringLiteral("p2p")});
        } else if (route == QStringLiteral("group")) {
            controller.connectGroup(QStringLiteral("CH"), QStringLiteral("location"), QStringLiteral("Zurich"));
        } else if (route == QStringLiteral("group-features")) {
            controller.connectGroupWithFeatures(QStringLiteral("CH"), QStringLiteral("location"),
                QStringLiteral("Zurich"), {QStringLiteral("p2p")});
        } else {
            controller.connectServer(QStringLiteral("CH#1"));
        }
        QTRY_COMPARE(m_backend.delayedCapabilityMessages.size(), 1);
    }
    m_backend.delaySnapshot = true;
    controller.refresh();
    QTRY_COMPARE(m_backend.delayedSnapshotMessages.size(), 1);
    const QString staleIdle = m_backend.GetSnapshot();
    const auto operation = disconnecting ? m_backend.delayedDisconnectMessage
                                         : m_backend.delayedCapabilityMessages.at(0);
    QVERIFY(m_backendBus->send(operation.createErrorReply(
        QDBusError::NoReply, QStringLiteral("completion unknown"))));
    QTRY_VERIFY(controller.message().contains(QStringLiteral("completing")));
    QVERIFY(controller.busy());
    QVERIFY(!controller.canConnect());
    QCOMPARE(finished.count(), 0);
    QVERIFY(m_backendBus->send(m_backend.delayedSnapshotMessages.at(0)
        .createReply(QVariantList{staleIdle})));
    QTRY_COMPARE(m_backend.delayedSnapshotMessages.size(), 2);
    QVERIFY(controller.busy());
    QCOMPARE(finished.count(), 0);
    m_backend.operationBusy = true;
    QVERIFY(m_backendBus->send(m_backend.delayedSnapshotMessages.at(1)
        .createReply(QVariantList{m_backend.GetSnapshot()})));
    QTest::qWait(30);
    QVERIFY(controller.busy());
    QCOMPARE(finished.count(), 0);
    m_backend.operationBusy = false;
    m_backend.connectionState = finalState;
    m_backend.statusMessage = hasDiagnostic ? QStringLiteral("Target lookup failed") : QString{};
    m_backend.publishSession(true, true);
    QTRY_VERIFY(!controller.busy());
    QTRY_COMPARE(finished.count(), 1);
    QVERIFY(!finished.at(0).at(2).toBool());
    QVERIFY(finished.at(0).at(3).toString().contains(QStringLiteral("could not be confirmed")));
    m_backend.publishSession(true, true);
    QTest::qWait(30);
    QCOMPARE(finished.count(), 1);
}

void GroupedNavigationTest::captureStateDoesNotAcknowledgeStart_data()
{
    QTest::addColumn<bool>("timedOut");
    QTest::newRow("failed") << false;
    QTest::newRow("unconfirmed") << true;
}

void GroupedNavigationTest::captureStateDoesNotAcknowledgeStart()
{
    QFETCH(bool, timedOut);
    const auto cleanup = qScopeGuard([this] {
        m_backend.connectionState = QStringLiteral("disconnected");
        m_backend.operationBusy = false;
        m_backend.packetCaptureActive = false;
        m_backend.delayPacketCaptureStart = false;
        m_backend.delayedPacketCaptureStartMessage = {};
    });
    m_backend.connectionState = QStringLiteral("connected");
    m_backend.publishSession(true, true);
    VpnController controller(nullptr, false);
    QTRY_VERIFY(controller.ready());
    m_backend.delayPacketCaptureStart = true;
    controller.startPacketCapture(QStringLiteral("/tmp"));
    QTRY_COMPARE(m_backend.delayedPacketCaptureStartMessage.type(), QDBusMessage::MethodCallMessage);
    const auto start = m_backend.delayedPacketCaptureStartMessage;
    m_backend.delayedPacketCaptureStartMessage = {};
    // Active is a retained cleanup obligation, including an unconfirmed Start;
    // it is not evidence that this request began writing a capture successfully.
    m_backend.packetCaptureActive = true;
    m_backend.operationBusy = true;
    m_backend.publishSession(true, true);
    QVERIFY(m_backendBus->send(start.createErrorReply(
        timedOut ? QDBusError::NoReply : QDBusError::Failed,
        QStringLiteral("capture start did not acknowledge"))));
    QTRY_VERIFY(!controller.packetCaptureError().isEmpty());
    m_backend.operationBusy = false;
    m_backend.publishSession(true, true);
    QTest::qWait(50);
    QVERIFY(!controller.packetCaptureError().isEmpty());
    QVERIFY(controller.packetCaptureActive());
    controller.stopPacketCapture();
    QTRY_VERIFY(!controller.packetCaptureActive());
    QTRY_VERIFY(controller.packetCaptureError().isEmpty());
}

void GroupedNavigationTest::searchCoalescesToLatestQuery()
{
    const auto cleanup = qScopeGuard([this] {
        m_backend.delaySearch = false;
        m_backend.delayedSearchMessages.clear();
        m_backend.searchQueries.clear();
    });
    m_backend.publishSession(true, true);
    VpnController controller(nullptr, false);
    QTRY_VERIFY(controller.ready());
    m_backend.delaySearch = true;
    m_backend.searchQueries.clear();
    controller.searchLocations(QStringLiteral("ca"));
    QTRY_COMPARE(m_backend.delayedSearchMessages.size(), 1);
    controller.searchLocations(QStringLiteral("can"));
    controller.searchLocations(QStringLiteral("canad"));
    controller.searchLocations(QString{});
    QVERIFY(!controller.locationSearchBusy());
    controller.searchLocations(QStringLiteral("canada"));
    QTest::qWait(30);
    QCOMPARE(m_backend.delayedSearchMessages.size(), 1);
    QVERIFY(m_backendBus->send(m_backend.delayedSearchMessages.at(0)
        .createErrorReply(QDBusError::NoReply, QStringLiteral("old query timeout"))));
    QTRY_COMPARE(m_backend.delayedSearchMessages.size(), 2);
    QCOMPARE(m_backend.searchQueries, (QStringList{QStringLiteral("ca"), QStringLiteral("canada")}));
    QVERIFY(controller.locationSearchBusy());
    QVERIFY(m_backendBus->send(m_backend.delayedSearchMessages.at(1).createReply(
        QVariantList{QStringLiteral(R"({"schemaVersion":1,"results":[]})")})));
    QTRY_VERIFY(!controller.locationSearchBusy());
    QVERIFY(controller.locationSearchError().isEmpty());
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

void GroupedNavigationTest::staleCountryReplyCannotMutateReplacementSession()
{
    m_backend.publishSession(true, true);
    m_backend.delayCountries = true;
    m_backend.delayedCountriesMessage = {};
    VpnController controller(nullptr, false);

    QTRY_VERIFY_WITH_TIMEOUT(controller.ready(), 2000);
    controller.loadCountries();
    QTRY_COMPARE_WITH_TIMEOUT(
        m_backend.delayedCountriesMessage.type(),
        QDBusMessage::MethodCallMessage, 2000);
    QVERIFY(controller.locationsBusy());

    m_backend.publishSession(true, false);
    QTRY_VERIFY_WITH_TIMEOUT(!controller.loggedIn(), 2000);
    QVERIFY(!controller.locationsBusy());
    m_backend.publishSession(true, true);
    QTRY_VERIFY_WITH_TIMEOUT(controller.loggedIn(), 2000);

    m_backend.delayCountries = false;
    controller.loadCountries();
    QTRY_COMPARE_WITH_TIMEOUT(controller.countryModel()->rowCount(), 2, 2000);
    QVERIFY(controller.countriesError().isEmpty());

    QVERIFY(m_backendBus->send(
        m_backend.delayedCountriesMessage.createErrorReply(
            QDBusError::Failed, QStringLiteral("old account read failed"))));
    QTest::qWait(100);
    QCOMPARE(controller.countryModel()->rowCount(), 2);
    QVERIFY(controller.countriesError().isEmpty());
    QVERIFY(!controller.locationsBusy());
}

void GroupedNavigationTest::pageRetirementDispatchesPendingParentRefresh()
{
    m_backend.publishSession(true, true);
    VpnController controller(nullptr, false);
    QTRY_VERIFY_WITH_TIMEOUT(controller.ready(), 2000);
    const auto context = controller.claimServerContext(QStringLiteral("CH"));
    QTRY_VERIFY_WITH_TIMEOUT(!controller.locationsBusy(), 2000);
    m_backend.delayCountries = true;
    m_backend.delayedCountriesMessage = {};
    controller.loadCountries();
    QTRY_COMPARE_WITH_TIMEOUT(m_backend.delayedCountriesMessage.type(),
                              QDBusMessage::MethodCallMessage, 2000);
    const auto oldRead = m_backend.delayedCountriesMessage;
    controller.loadCountries(); // A valid parent refresh is now pending.
    m_backend.delayCountries = false;
    controller.releaseServerContext(context);
    QTRY_VERIFY_WITH_TIMEOUT(!controller.locationsBusy(), 2000);
    QCOMPARE(controller.countryModel()->rowCount(), 2);
    QVERIFY(m_backendBus->send(oldRead.createErrorReply(
        QDBusError::Failed, QStringLiteral("retired page read"))));
    QTest::qWait(50);
    QVERIFY(!controller.locationsBusy());
    QVERIFY(controller.countriesError().isEmpty());
}

void GroupedNavigationTest::controlTimeoutDoesNotInventBackendLoss()
{
    m_backend.connectionState = QStringLiteral("connected");
    m_backend.publishSession(true, true);
    m_backend.delayDisconnect = true;
    m_backend.delayedDisconnectMessage = {};
    VpnController controller(nullptr, false);
    QTRY_VERIFY_WITH_TIMEOUT(controller.ready(), 2000);
    controller.disconnect();
    QTRY_COMPARE_WITH_TIMEOUT(m_backend.delayedDisconnectMessage.type(),
                              QDBusMessage::MethodCallMessage, 2000);
    const int snapshots = m_backend.snapshotCalls;
    QVERIFY(m_backendBus->send(m_backend.delayedDisconnectMessage.createErrorReply(
        QDBusError::NoReply, QStringLiteral("completion unknown"))));
    QTRY_VERIFY_WITH_TIMEOUT(m_backend.snapshotCalls > snapshots, 2000);
    QVERIFY(controller.backendAvailable());
    QVERIFY(!controller.message().contains(QStringLiteral("service stopped")));
    m_backend.delayDisconnect = false;
    m_backend.delayedDisconnectMessage = {};
    m_backend.connectionState = QStringLiteral("disconnected");
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

void GroupedNavigationTest::supersededServerGroupRetryReleasesBrowserOwnership()
{
    m_backend.publishSession(true, true);
    const int groupCallsBefore = m_backend.groupCalls;
    m_backend.emptyGroupResponses = 1;
    VpnController controller(nullptr, false);

    QTRY_VERIFY_WITH_TIMEOUT(controller.ready(), 2000);
    controller.loadServerGroups(QStringLiteral("CH"));
    QTRY_COMPARE_WITH_TIMEOUT(m_backend.emptyGroupResponses, 0, 2000);
    QTest::qWait(25);
    controller.loadServerGroups(QStringLiteral("US"));

    QTRY_COMPARE_WITH_TIMEOUT(
        controller.serverGroupModel()->rowCount(), 2, 2000);
    QCOMPARE(m_backend.lastCountry, QStringLiteral("US"));
    QCOMPARE(m_backend.groupCalls, groupCallsBefore + 2);
    QVERIFY(!controller.locationsBusy());
}

void GroupedNavigationTest::supersededExactServerRetryReleasesBrowserOwnership()
{
    m_backend.publishSession(true, true);
    const int serverCallsBefore = m_backend.serverCalls;
    m_backend.emptyServerResponses = 1;
    VpnController controller(nullptr, false);

    QTRY_VERIFY_WITH_TIMEOUT(controller.ready(), 2000);
    controller.loadGroupServers(QStringLiteral("CH"),
                                QStringLiteral("location"),
                                QStringLiteral("Zurich"));
    QTRY_COMPARE_WITH_TIMEOUT(m_backend.emptyServerResponses, 0, 2000);
    QTest::qWait(25);
    controller.loadGroupServers(QStringLiteral("US"),
                                QStringLiteral("location"),
                                QStringLiteral("Arizona"));

    QTRY_COMPARE_WITH_TIMEOUT(controller.serverModel()->rowCount(), 2, 2000);
    QCOMPARE(m_backend.lastCountry, QStringLiteral("US"));
    QCOMPARE(m_backend.lastGroupName, QStringLiteral("Arizona"));
    QCOMPARE(m_backend.serverCalls, serverCallsBefore + 2);
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
    QVERIFY(connectionFinished.at(0).at(0).toULongLong() > 0);
    QCOMPARE(connectionFinished.at(0).at(1).toString(),
             QStringLiteral("connected"));
    QVERIFY(connectionFinished.at(0).at(2).toBool());

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

void GroupedNavigationTest::staleConnectionReplyCannotCompleteReplacementOperation()
{
    m_backend.publishSession(true, true);
    m_backend.delayedCapabilityOperationCount = 2;
    m_backend.delayedCapabilityMessages.clear();
    VpnController controller(nullptr, false);
    QSignalSpy connectionStarted(
        &controller, &VpnController::connectionOperationStarted);
    QSignalSpy connectionFinished(
        &controller, &VpnController::connectionOperationFinished);

    QTRY_VERIFY_WITH_TIMEOUT(controller.ready(), 2000);
    controller.connectFastestWithFeatures({QStringLiteral("p2p")});
    QTRY_COMPARE_WITH_TIMEOUT(
        m_backend.delayedCapabilityMessages.size(), 1, 2000);
    QTRY_COMPARE_WITH_TIMEOUT(connectionStarted.count(), 1, 2000);
    const quint64 firstOperation =
        connectionStarted.at(0).at(0).toULongLong();

    // Production publishes busy=false before the method reply. That permits a
    // retry while the first D-Bus reply is still in flight.
    m_backend.publishSession(true, true);
    QTRY_VERIFY_WITH_TIMEOUT(!controller.busy(), 2000);
    controller.connectFastestWithFeatures({QStringLiteral("streaming")});
    QTRY_COMPARE_WITH_TIMEOUT(
        m_backend.delayedCapabilityMessages.size(), 2, 2000);
    QTRY_COMPARE_WITH_TIMEOUT(connectionStarted.count(), 2, 2000);
    const quint64 replacementOperation =
        connectionStarted.at(1).at(0).toULongLong();
    QVERIFY(replacementOperation > firstOperation);
    QVERIFY(controller.busy());

    QVERIFY(m_backendBus->send(
        m_backend.delayedCapabilityMessages.at(0).createErrorReply(
            QDBusError::Failed,
            QStringLiteral("older connection attempt failed"))));
    QTest::qWait(100);
    QCOMPARE(connectionFinished.count(), 0);
    QVERIFY(controller.busy());

    QVERIFY(m_backendBus->send(
        m_backend.delayedCapabilityMessages.at(1).createReply()));
    QTRY_COMPARE_WITH_TIMEOUT(connectionFinished.count(), 1, 2000);
    QCOMPARE(connectionFinished.at(0).at(0).toULongLong(),
             replacementOperation);
    QCOMPARE(connectionFinished.at(0).at(1).toString(),
             QStringLiteral("connected"));
    QVERIFY(connectionFinished.at(0).at(2).toBool());

    m_backend.delayedCapabilityOperationCount = 0;
    m_backend.delayedCapabilityMessages.clear();
}

void GroupedNavigationTest::staleForegroundAuthReplyCannotCorruptReplacementOperation()
{
    m_backend.publishSession(true, true);
    m_backend.delayLogout = true;
    m_backend.delayedLogoutMessage = {};
    m_backend.delayedCapabilityOperationCount = 1;
    m_backend.delayedCapabilityMessages.clear();
    VpnController controller(nullptr, false);
    QSignalSpy connectionFinished(
        &controller, &VpnController::connectionOperationFinished);

    QTRY_VERIFY_WITH_TIMEOUT(controller.ready(), 2000);
    controller.logout();
    QTRY_COMPARE_WITH_TIMEOUT(
        m_backend.delayedLogoutMessage.type(),
        QDBusMessage::MethodCallMessage, 2000);

    m_backend.publishSession(true, true);
    QTRY_VERIFY_WITH_TIMEOUT(!controller.busy(), 2000);
    controller.connectFastestWithFeatures({QStringLiteral("p2p")});
    QTRY_COMPARE_WITH_TIMEOUT(
        m_backend.delayedCapabilityMessages.size(), 1, 2000);
    QVERIFY(controller.busy());

    QVERIFY(m_backendBus->send(
        m_backend.delayedLogoutMessage.createErrorReply(
            QDBusError::Failed,
            QStringLiteral("older logout failed"))));
    QTest::qWait(100);
    QVERIFY(controller.busy());
    QVERIFY(controller.message().isEmpty());
    QCOMPARE(connectionFinished.count(), 0);

    QVERIFY(m_backendBus->send(
        m_backend.delayedCapabilityMessages.at(0).createReply()));
    QTRY_COMPARE_WITH_TIMEOUT(connectionFinished.count(), 1, 2000);
    QVERIFY(connectionFinished.at(0).at(2).toBool());

    m_backend.delayLogout = false;
    m_backend.delayedCapabilityOperationCount = 0;
    m_backend.delayedCapabilityMessages.clear();
}

void GroupedNavigationTest::staleConnectionReplyCannotCompleteAfterLogout()
{
    m_backend.publishSession(true, true);
    m_backend.delayLogout = true;
    m_backend.delayedLogoutMessage = {};
    m_backend.delayedCapabilityOperationCount = 1;
    m_backend.delayedCapabilityMessages.clear();
    VpnController controller(nullptr, false);
    QSignalSpy connectionFinished(
        &controller, &VpnController::connectionOperationFinished);

    QTRY_VERIFY_WITH_TIMEOUT(controller.ready(), 2000);
    controller.connectFastestWithFeatures({QStringLiteral("p2p")});
    QTRY_COMPARE_WITH_TIMEOUT(
        m_backend.delayedCapabilityMessages.size(), 1, 2000);

    m_backend.publishSession(true, true);
    QTRY_VERIFY_WITH_TIMEOUT(!controller.busy(), 2000);
    controller.logout();
    QTRY_COMPARE_WITH_TIMEOUT(
        m_backend.delayedLogoutMessage.type(),
        QDBusMessage::MethodCallMessage, 2000);
    QVERIFY(controller.busy());

    QVERIFY(m_backendBus->send(
        m_backend.delayedCapabilityMessages.at(0).createErrorReply(
            QDBusError::Failed,
            QStringLiteral("superseded connection failed"))));
    QTest::qWait(100);
    QCOMPARE(connectionFinished.count(), 0);
    QVERIFY(controller.busy());

    m_backend.publishSession(true, false);
    QVERIFY(m_backendBus->send(
        m_backend.delayedLogoutMessage.createReply()));
    QTRY_VERIFY_WITH_TIMEOUT(!controller.loggedIn(), 2000);

    m_backend.delayLogout = false;
    m_backend.delayedCapabilityOperationCount = 0;
    m_backend.delayedCapabilityMessages.clear();
    m_backend.connectionState = QStringLiteral("disconnected");
    m_backend.publishSession(true, true);
}

void GroupedNavigationTest::staleControlDisconnectReplyCannotCorruptSignedOutState()
{
    for (const bool failReply : {false, true}) {
        m_backend.connectionState = QStringLiteral("connected");
        m_backend.delayDisconnect = true;
        m_backend.delayLogout = true;
        m_backend.delayedDisconnectMessage = {};
        m_backend.delayedLogoutMessage = {};
        m_backend.publishSession(true, true);
        VpnController controller(nullptr, false);
        QSignalSpy connectionFinished(
            &controller, &VpnController::connectionOperationFinished);

        QTRY_VERIFY_WITH_TIMEOUT(controller.ready(), 2000);
        QTRY_VERIFY_WITH_TIMEOUT(controller.loggedIn(), 2000);
        controller.disconnect();
        QTRY_COMPARE_WITH_TIMEOUT(
            m_backend.delayedDisconnectMessage.type(),
            QDBusMessage::MethodCallMessage, 2000);

        m_backend.connectionState = QStringLiteral("disconnected");
        m_backend.publishSession(true, true);
        controller.logout();
        QTRY_COMPARE_WITH_TIMEOUT(
            m_backend.delayedLogoutMessage.type(),
            QDBusMessage::MethodCallMessage, 2000);
        m_backend.publishSession(true, false);
        QTRY_VERIFY_WITH_TIMEOUT(!controller.loggedIn(), 2000);
        const QString signedOutMessage = controller.message();
        const int snapshotCalls = m_backend.snapshotCalls;

        const QDBusMessage delayedReply = failReply
            ? m_backend.delayedDisconnectMessage.createErrorReply(
                  QDBusError::Failed,
                  QStringLiteral("superseded disconnect failed"))
            : m_backend.delayedDisconnectMessage.createReply();
        QVERIFY(m_backendBus->send(delayedReply));
        QTest::qWait(100);
        QVERIFY(controller.backendAvailable());
        QCOMPARE(controller.message(), signedOutMessage);
        QCOMPARE(connectionFinished.count(), 0);
        QCOMPARE(m_backend.snapshotCalls, snapshotCalls);

        QVERIFY(m_backendBus->send(
            m_backend.delayedLogoutMessage.createReply()));
        QTest::qWait(20);
    }

    m_backend.delayDisconnect = false;
    m_backend.delayLogout = false;
    m_backend.delayedDisconnectMessage = {};
    m_backend.delayedLogoutMessage = {};
    m_backend.publishSession(true, true);
}

void GroupedNavigationTest::staleReconnectionReplyCannotCorruptForegroundOperation()
{
    for (const bool failReply : {false, true}) {
        m_backend.delayReconnection = true;
        m_backend.delayedReconnectionMessage = {};
        m_backend.delayedCapabilityOperationCount = 1;
        m_backend.delayedCapabilityMessages.clear();
        m_backend.publishSession(true, true);
        VpnController controller(nullptr, false);
        QSignalSpy connectionFinished(
            &controller, &VpnController::connectionOperationFinished);

        QTRY_VERIFY_WITH_TIMEOUT(controller.ready(), 2000);
        controller.setReconnectionEnabled(false);
        QTRY_COMPARE_WITH_TIMEOUT(
            m_backend.delayedReconnectionMessage.type(),
            QDBusMessage::MethodCallMessage, 2000);
        controller.connectFastestWithFeatures({QStringLiteral("p2p")});
        QTRY_COMPARE_WITH_TIMEOUT(
            m_backend.delayedCapabilityMessages.size(), 1, 2000);
        QVERIFY(controller.busy());
        const int snapshotCalls = m_backend.snapshotCalls;

        const QDBusMessage delayedReply = failReply
            ? m_backend.delayedReconnectionMessage.createErrorReply(
                  QDBusError::Failed,
                  QStringLiteral("superseded preference failed"))
            : m_backend.delayedReconnectionMessage.createReply();
        QVERIFY(m_backendBus->send(delayedReply));
        QTest::qWait(100);
        QVERIFY(controller.backendAvailable());
        QVERIFY(controller.busy());
        QVERIFY(controller.message().isEmpty());
        QCOMPARE(connectionFinished.count(), 0);
        QCOMPARE(m_backend.snapshotCalls, snapshotCalls);

        QVERIFY(m_backendBus->send(
            m_backend.delayedCapabilityMessages.at(0).createReply()));
        QTRY_COMPARE_WITH_TIMEOUT(connectionFinished.count(), 1, 2000);
    }

    m_backend.delayReconnection = false;
    m_backend.delayedReconnectionMessage = {};
    m_backend.delayedCapabilityOperationCount = 0;
    m_backend.delayedCapabilityMessages.clear();
}

void GroupedNavigationTest::npsSubmissionWaitsForBackendAcceptance()
{
    QCOMPARE(m_backend.authPublicKey.size(), 32);
    m_backend.publishSession(true, true);
    m_backend.delayAuthPublicKey = false;
    m_backend.delayNpsSubmission = true;
    m_backend.delayedNpsSubmissionMessage = {};
    VpnController controller(nullptr, false);
    QSignalSpy submissionFinished(
        &controller, &VpnController::npsSurveySubmissionFinished);

    QTRY_VERIFY_WITH_TIMEOUT(controller.ready(), 2000);
    controller.m_npsSurveyAvailable = true;
    controller.submitNpsSurvey(9, QStringLiteral("Works well on Plasma"));
    QTRY_COMPARE_WITH_TIMEOUT(
        m_backend.delayedNpsSubmissionMessage.type(),
        QDBusMessage::MethodCallMessage, 2000);
    QVERIFY(controller.npsSurveySubmissionPending());
    QCOMPARE(submissionFinished.count(), 0);

    QVERIFY(m_backendBus->send(
        m_backend.delayedNpsSubmissionMessage.createReply()));
    QTRY_COMPARE_WITH_TIMEOUT(submissionFinished.count(), 1, 2000);
    QVERIFY(submissionFinished.at(0).at(0).toBool());
    QVERIFY(!controller.npsSurveySubmissionPending());

    m_backend.delayNpsSubmission = false;
}

void GroupedNavigationTest::npsCompletionUnknownCannotBeRetried()
{
    m_backend.publishSession(true, true);
    m_backend.delayAuthPublicKey = false;
    m_backend.delayNpsSubmission = true;
    m_backend.delayedNpsSubmissionMessage = {};
    VpnController controller(nullptr, false);
    QSignalSpy submissionFinished(
        &controller, &VpnController::npsSurveySubmissionFinished);

    QTRY_VERIFY_WITH_TIMEOUT(controller.ready(), 2000);
    controller.m_npsSurveyAvailable = true;
    const int submissionsBefore = m_backend.npsSubmissionCalls;
    controller.submitNpsSurvey(9, QStringLiteral("Works well on Plasma"));
    QTRY_COMPARE_WITH_TIMEOUT(
        m_backend.delayedNpsSubmissionMessage.type(),
        QDBusMessage::MethodCallMessage, 2000);

    QVERIFY(m_backendBus->send(
        m_backend.delayedNpsSubmissionMessage.createErrorReply(
            QStringLiteral(
                "quest.entropy.PlasmaVPN.Error.NpsCompletionUnknown"),
            QStringLiteral(
                "Survey submission completion could not be confirmed"))));
    QTRY_COMPARE_WITH_TIMEOUT(submissionFinished.count(), 1, 2000);
    QVERIFY(!submissionFinished.at(0).at(0).toBool());
    QVERIFY(submissionFinished.at(0).at(1).toString().contains(
        QStringLiteral("not be retried"), Qt::CaseInsensitive));
    QVERIFY(!controller.npsSurveyAvailable());
    QVERIFY(!controller.npsSurveySubmissionPending());

    controller.submitNpsSurvey(9, QStringLiteral("Do not duplicate"));
    QTest::qWait(100);
    QCOMPARE(m_backend.npsSubmissionCalls, submissionsBefore + 1);
    QCOMPARE(submissionFinished.count(), 1);

    m_backend.delayNpsSubmission = false;
    m_backend.delayedNpsSubmissionMessage = {};
}

void GroupedNavigationTest::npsDismissalDoesNotOwnVpnOperationsOrGlobalGuidance()
{
    m_backend.publishSession(true, true);
    m_backend.delayAuthPublicKey = false;
    m_backend.delayNpsSubmission = true;
    m_backend.delayedNpsSubmissionMessage = {};
    VpnController controller(nullptr, false);
    QSignalSpy submissionFinished(
        &controller, &VpnController::npsSurveySubmissionFinished);

    QTRY_VERIFY_WITH_TIMEOUT(controller.ready(), 2000);
    controller.m_npsSurveyAvailable = true;
    const int submissionsBefore = m_backend.npsSubmissionCalls;
    const int connectionsBefore = m_backend.capabilityCalls;
    controller.dismissNpsSurvey();
    QTRY_COMPARE_WITH_TIMEOUT(
        m_backend.delayedNpsSubmissionMessage.type(),
        QDBusMessage::MethodCallMessage, 2000);
    QVERIFY(controller.npsSurveySubmissionPending());

    controller.connectFastestWithFeatures({QStringLiteral("p2p")});
    QTRY_COMPARE_WITH_TIMEOUT(
        m_backend.capabilityCalls, connectionsBefore + 1, 2000);
    QTRY_VERIFY_WITH_TIMEOUT(!controller.busy(), 2000);
    const QString currentGuidance = controller.message();

    QVERIFY(m_backendBus->send(
        m_backend.delayedNpsSubmissionMessage.createErrorReply(
            QDBusError::Failed,
            QStringLiteral("dismissal rejected"))));
    QTRY_COMPARE_WITH_TIMEOUT(submissionFinished.count(), 1, 2000);
    QVERIFY(!submissionFinished.at(0).at(0).toBool());
    QVERIFY(!controller.npsSurveySubmissionPending());
    QVERIFY(!controller.npsSurveyAvailable());
    QCOMPARE(controller.message(), currentGuidance);
    QCOMPARE(m_backend.npsSubmissionCalls, submissionsBefore + 1);

    m_backend.delayNpsSubmission = false;
    m_backend.delayedNpsSubmissionMessage = {};
}

void GroupedNavigationTest::rejectedNpsSubmissionCanBeRetried()
{
    m_backend.publishSession(true, true);
    m_backend.delayAuthPublicKey = false;
    m_backend.delayNpsSubmission = false;
    m_backend.failNextNpsSubmission = true;
    VpnController controller(nullptr, false);
    QSignalSpy submissionFinished(
        &controller, &VpnController::npsSurveySubmissionFinished);

    QTRY_VERIFY_WITH_TIMEOUT(controller.ready(), 2000);
    controller.m_npsSurveyAvailable = true;
    const int submissionsBefore = m_backend.npsSubmissionCalls;
    controller.submitNpsSurvey(8, QStringLiteral("First attempt"));
    QTRY_COMPARE_WITH_TIMEOUT(submissionFinished.count(), 1, 2000);
    QVERIFY(!submissionFinished.at(0).at(0).toBool());
    QVERIFY(controller.npsSurveyAvailable());
    QVERIFY(!controller.npsSurveySubmissionPending());

    controller.submitNpsSurvey(8, QStringLiteral("Second attempt"));
    QTRY_COMPARE_WITH_TIMEOUT(submissionFinished.count(), 2, 2000);
    QVERIFY(submissionFinished.at(1).at(0).toBool());
    QCOMPARE(m_backend.npsSubmissionCalls, submissionsBefore + 2);
    QVERIFY(!controller.npsSurveyAvailable());
    QVERIFY(!controller.npsSurveySubmissionPending());
}

void GroupedNavigationTest::staleNpsKeyCannotSubmitForReplacementSession()
{
    QCOMPARE(m_backend.authPublicKey.size(), 32);
    m_backend.publishSession(true, true);
    m_backend.delayAuthPublicKey = true;
    m_backend.delayedAuthPublicKeyMessage = {};
    VpnController controller(nullptr, false);
    QSignalSpy submissionFinished(
        &controller, &VpnController::npsSurveySubmissionFinished);

    QTRY_VERIFY_WITH_TIMEOUT(controller.ready(), 2000);
    controller.m_npsSurveyAvailable = true;
    const int submissionsBefore = m_backend.npsSubmissionCalls;
    controller.submitNpsSurvey(9, QStringLiteral("Works well on Plasma"));
    QVERIFY(controller.npsSurveySubmissionPending());
    QTRY_COMPARE_WITH_TIMEOUT(
        m_backend.delayedAuthPublicKeyMessage.type(),
        QDBusMessage::MethodCallMessage, 2000);

    m_backend.publishSession(true, false);
    QTRY_VERIFY_WITH_TIMEOUT(!controller.loggedIn(), 2000);
    m_backend.publishSession(true, true);
    QTRY_VERIFY_WITH_TIMEOUT(controller.loggedIn(), 2000);
    QTRY_COMPARE_WITH_TIMEOUT(submissionFinished.count(), 1, 2000);
    QVERIFY(!submissionFinished.at(0).at(0).toBool());
    QVERIFY(!controller.npsSurveySubmissionPending());

    const QDBusMessage staleKeyReply =
        m_backend.delayedAuthPublicKeyMessage.createReply(
            QString::fromLatin1(m_backend.authPublicKey.toBase64()));
    m_backend.delayAuthPublicKey = false;
    m_backend.delayNpsSubmission = true;
    m_backend.delayedNpsSubmissionMessage = {};
    controller.m_npsSurveyAvailable = true;
    controller.submitNpsSurvey(
        10, QStringLiteral("Replacement session response"));
    QTRY_COMPARE_WITH_TIMEOUT(
        m_backend.delayedNpsSubmissionMessage.type(),
        QDBusMessage::MethodCallMessage, 2000);
    QVERIFY(controller.npsSurveySubmissionPending());

    QVERIFY(m_backendBus->send(staleKeyReply));
    QTest::qWait(100);
    QCOMPARE(m_backend.npsSubmissionCalls, submissionsBefore + 1);
    QCOMPARE(submissionFinished.count(), 1);
    QVERIFY(controller.npsSurveySubmissionPending());

    QVERIFY(m_backendBus->send(
        m_backend.delayedNpsSubmissionMessage.createReply()));
    QTRY_COMPARE_WITH_TIMEOUT(submissionFinished.count(), 2, 2000);
    QVERIFY(submissionFinished.at(1).at(0).toBool());
    QVERIFY(!controller.npsSurveySubmissionPending());

    m_backend.delayAuthPublicKey = false;
    m_backend.delayNpsSubmission = false;
}

void GroupedNavigationTest::staleNpsDismissalCannotCompleteReplacementSubmission()
{
    m_backend.publishSession(true, true);
    m_backend.delayAuthPublicKey = false;
    m_backend.delayNpsSubmission = true;
    m_backend.delayedNpsSubmissionMessage = {};
    VpnController controller(nullptr, false);
    QSignalSpy submissionFinished(
        &controller, &VpnController::npsSurveySubmissionFinished);

    QTRY_VERIFY_WITH_TIMEOUT(controller.ready(), 2000);
    controller.m_npsSurveyAvailable = true;
    controller.dismissNpsSurvey();
    QTRY_COMPARE_WITH_TIMEOUT(
        m_backend.delayedNpsSubmissionMessage.type(),
        QDBusMessage::MethodCallMessage, 2000);
    const QDBusMessage staleDismissalReply =
        m_backend.delayedNpsSubmissionMessage.createReply();

    m_backend.publishSession(true, false);
    QTRY_VERIFY_WITH_TIMEOUT(!controller.loggedIn(), 2000);
    QTRY_COMPARE_WITH_TIMEOUT(submissionFinished.count(), 1, 2000);
    QVERIFY(!submissionFinished.at(0).at(0).toBool());
    m_backend.publishSession(true, true);
    QTRY_VERIFY_WITH_TIMEOUT(controller.loggedIn(), 2000);

    m_backend.delayedNpsSubmissionMessage = {};
    controller.m_npsSurveyAvailable = true;
    controller.submitNpsSurvey(
        9, QStringLiteral("Replacement session response"));
    QTRY_COMPARE_WITH_TIMEOUT(
        m_backend.delayedNpsSubmissionMessage.type(),
        QDBusMessage::MethodCallMessage, 2000);
    QVERIFY(controller.npsSurveySubmissionPending());

    QVERIFY(m_backendBus->send(staleDismissalReply));
    QTest::qWait(100);
    QCOMPARE(submissionFinished.count(), 1);
    QVERIFY(controller.npsSurveySubmissionPending());

    QVERIFY(m_backendBus->send(
        m_backend.delayedNpsSubmissionMessage.createReply()));
    QTRY_COMPARE_WITH_TIMEOUT(submissionFinished.count(), 2, 2000);
    QVERIFY(submissionFinished.at(1).at(0).toBool());
    QVERIFY(!controller.npsSurveySubmissionPending());

    m_backend.delayNpsSubmission = false;
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
