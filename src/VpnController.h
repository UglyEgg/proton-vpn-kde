#pragma once

#include "ClientRegistrationState.h"
#include "VpnConnectionController.h"
#include "VpnSettingsModel.h"
#include "SplitTunnelingModel.h"
#include "CustomDnsModel.h"

#include <QObject>
#include <QString>
#include <QVariant>

class QDBusPendingCallWatcher;
class QDBusServiceWatcher;
class QTimer;
class QAbstractItemModel;
class QJsonObject;
class CountryModel;
class LocationSearchModel;
class LocationFilterProxyModel;
class ServerGroupModel;
class ServerModel;
class InstalledApplicationModel;
class GroupedNavigationTest;

class VpnController final : public VpnConnectionController
{
    Q_OBJECT
    Q_PROPERTY(bool backendAvailable READ backendAvailable NOTIFY backendAvailableChanged)
    Q_PROPERTY(bool ready READ ready NOTIFY snapshotChanged)
    Q_PROPERTY(bool startupCompatible READ startupCompatible NOTIFY snapshotChanged)
    Q_PROPERTY(bool loggedIn READ loggedIn NOTIFY snapshotChanged)
    Q_PROPERTY(QString authState READ authState NOTIFY snapshotChanged)
    Q_PROPERTY(QString accountName READ accountName NOTIFY snapshotChanged)
    Q_PROPERTY(QString planTitle READ planTitle NOTIFY snapshotChanged)
    Q_PROPERTY(int userTier READ userTier NOTIFY snapshotChanged)
    Q_PROPERTY(int maxConnections READ maxConnections NOTIFY snapshotChanged)
    Q_PROPERTY(bool fido2Available READ fido2Available NOTIFY snapshotChanged)
    Q_PROPERTY(int killSwitch READ killSwitch NOTIFY snapshotChanged)
    Q_PROPERTY(bool busy READ busy NOTIFY snapshotChanged)
    Q_PROPERTY(bool locationsBusy READ locationsBusy NOTIFY locationsChanged)
    Q_PROPERTY(bool locationSearchBusy READ locationSearchBusy NOTIFY locationsChanged)
    Q_PROPERTY(bool npsSurveyAvailable READ npsSurveyAvailable NOTIFY npsSurveyChanged)
    Q_PROPERTY(bool supportReportSubmissionEnabled READ supportReportSubmissionEnabled CONSTANT)
    Q_PROPERTY(bool crashReportSubmissionEnabled READ crashReportSubmissionEnabled CONSTANT)
    Q_PROPERTY(QString state READ state NOTIFY snapshotChanged)
    Q_PROPERTY(QString errorCode READ errorCode NOTIFY snapshotChanged)
    Q_PROPERTY(QString serverName READ serverName NOTIFY snapshotChanged)
    Q_PROPERTY(QString serverLocation READ serverLocation NOTIFY snapshotChanged)
    Q_PROPERTY(QString exitCountry READ exitCountry NOTIFY snapshotChanged)
    Q_PROPERTY(QString entryCountry READ entryCountry NOTIFY snapshotChanged)
    Q_PROPERTY(int forwardedPort READ forwardedPort NOTIFY snapshotChanged)
    Q_PROPERTY(bool secureCore READ secureCore NOTIFY snapshotChanged)
    Q_PROPERTY(bool tor READ tor NOTIFY snapshotChanged)
    Q_PROPERTY(bool p2p READ p2p NOTIFY snapshotChanged)
    Q_PROPERTY(bool streaming READ streaming NOTIFY snapshotChanged)
    Q_PROPERTY(bool smartRouting READ smartRouting NOTIFY snapshotChanged)
    Q_PROPERTY(bool packetCaptureActive READ packetCaptureActive NOTIFY snapshotChanged)
    Q_PROPERTY(bool coreMemoryOptimized READ coreMemoryOptimized NOTIFY snapshotChanged)
    Q_PROPERTY(QString coreVersion READ coreVersion NOTIFY snapshotChanged)
    Q_PROPERTY(QString message READ message NOTIFY snapshotChanged)
    Q_PROPERTY(QString primaryActionText READ primaryActionText NOTIFY snapshotChanged)
    Q_PROPERTY(bool primaryActionEnabled READ primaryActionEnabled NOTIFY snapshotChanged)
    Q_PROPERTY(QAbstractItemModel *countryModel READ countryModel CONSTANT)
    Q_PROPERTY(QAbstractItemModel *locationSearchModel READ locationSearchModel CONSTANT)
    Q_PROPERTY(QAbstractItemModel *serverGroupModel READ serverGroupModel CONSTANT)
    Q_PROPERTY(QAbstractItemModel *serverModel READ serverModel CONSTANT)
    Q_PROPERTY(QAbstractItemModel *applicationModel READ applicationModel CONSTANT)
    Q_PROPERTY(VpnSettingsModel *settings READ settings CONSTANT)
    Q_PROPERTY(SplitTunnelingModel *splitTunneling READ splitTunneling CONSTANT)
    Q_PROPERTY(CustomDnsModel *customDns READ customDns CONSTANT)

public:
    explicit VpnController(QObject *parent = nullptr);
    ~VpnController() override;

    [[nodiscard]] bool backendAvailable() const override;
    [[nodiscard]] bool ready() const override;
    [[nodiscard]] bool startupCompatible() const;
    [[nodiscard]] bool loggedIn() const override;
    [[nodiscard]] QString authState() const;
    [[nodiscard]] QString accountName() const;
    [[nodiscard]] QString planTitle() const;
    [[nodiscard]] int userTier() const;
    [[nodiscard]] int maxConnections() const;
    [[nodiscard]] bool fido2Available() const;
    [[nodiscard]] int killSwitch() const override;
    [[nodiscard]] bool busy() const override;
    [[nodiscard]] bool locationsBusy() const;
    [[nodiscard]] bool locationSearchBusy() const;
    [[nodiscard]] bool npsSurveyAvailable() const;
    [[nodiscard]] bool supportReportSubmissionEnabled() const;
    [[nodiscard]] bool crashReportSubmissionEnabled() const;
    [[nodiscard]] QString state() const override;
    [[nodiscard]] QString errorCode() const;
    [[nodiscard]] QString serverName() const override;
    [[nodiscard]] QString serverLocation() const;
    [[nodiscard]] QString exitCountry() const;
    [[nodiscard]] QString entryCountry() const;
    [[nodiscard]] int forwardedPort() const override;
    [[nodiscard]] bool secureCore() const;
    [[nodiscard]] bool tor() const;
    [[nodiscard]] bool p2p() const;
    [[nodiscard]] bool streaming() const;
    [[nodiscard]] bool smartRouting() const;
    [[nodiscard]] bool packetCaptureActive() const;
    [[nodiscard]] bool coreMemoryOptimized() const;
    [[nodiscard]] QString coreVersion() const;
    [[nodiscard]] QString message() const override;
    [[nodiscard]] QString primaryActionText() const override;
    [[nodiscard]] bool primaryActionEnabled() const override;
    [[nodiscard]] QAbstractItemModel *countryModel() const;
    [[nodiscard]] QAbstractItemModel *locationSearchModel() const;
    [[nodiscard]] QAbstractItemModel *serverGroupModel() const;
    [[nodiscard]] QAbstractItemModel *serverModel() const;
    [[nodiscard]] QAbstractItemModel *applicationModel() const;
    [[nodiscard]] VpnSettingsModel *settings() const;
    [[nodiscard]] SplitTunnelingModel *splitTunneling() const;
    [[nodiscard]] CustomDnsModel *customDns() const;

    Q_INVOKABLE void refresh();
    Q_INVOKABLE void activatePrimaryAction() override;
    Q_INVOKABLE void disconnect() override;
    Q_INVOKABLE void copyForwardedPort();
    Q_INVOKABLE void startPacketCapture(const QString &directoryPath);
    Q_INVOKABLE void stopPacketCapture();
    Q_INVOKABLE void submitSupportReport(const QString &username,
                                         const QString &email,
                                         const QString &description,
                                         bool includeLogs);
    Q_INVOKABLE void loadCountries();
    Q_INVOKABLE void searchLocations(const QString &query);
    Q_INVOKABLE void clearLocationSearch();
    Q_INVOKABLE void submitNpsSurvey(int score, const QString &comments);
    Q_INVOKABLE void dismissNpsSurvey();
    Q_INVOKABLE void loadServerGroups(const QString &countryCode);
    Q_INVOKABLE void loadGroupServers(const QString &countryCode,
                                      const QString &groupKind,
                                      const QString &groupName);
    Q_INVOKABLE void clearGroupServerContext();
    Q_INVOKABLE void clearServerContext();
    Q_INVOKABLE void connectCountry(const QString &countryCode);
    Q_INVOKABLE void connectCountryWithFeatures(
        const QString &countryCode, const QStringList &features);
    Q_INVOKABLE void connectTarget(const QString &target) override;
    Q_INVOKABLE void connectFastestWithFeature(const QString &feature);
    Q_INVOKABLE void connectFastestWithFeatures(const QStringList &features);
    Q_INVOKABLE void connectGroup(const QString &countryCode,
                                  const QString &groupKind,
                                  const QString &groupName) override;
    Q_INVOKABLE void connectGroupWithFeatures(
        const QString &countryCode, const QString &groupKind,
        const QString &groupName, const QStringList &features);
    Q_INVOKABLE void connectServer(const QString &serverName);
    Q_INVOKABLE void login(const QString &username, const QString &password);
    Q_INVOKABLE void submitTwoFactor(const QString &code);
    Q_INVOKABLE void cancelLogin();
    Q_INVOKABLE void beginFido2();
    Q_INVOKABLE void submitFido2Pin(const QString &pin);
    Q_INVOKABLE void cancelFido2();
    Q_INVOKABLE void logout();
    Q_INVOKABLE void disableKillSwitchForLogin();
    Q_INVOKABLE void setCountryFilter(const QString &filterText);
    Q_INVOKABLE void setServerFilter(const QString &filterText);
    Q_INVOKABLE void setApplicationFilter(const QString &filterText);
    Q_INVOKABLE void setServerGroupFeatureFilter(const QStringList &features);
    Q_INVOKABLE void setServerFeatureFilter(const QStringList &features);
    Q_INVOKABLE void setReconnectionEnabled(bool enabled);
    Q_INVOKABLE void setFastestFeatures(const QStringList &features);
    Q_INVOKABLE void loadSettings();
    Q_INVOKABLE void updateSetting(const QString &name, const QVariant &value);
    Q_INVOKABLE void loadSplitTunneling();
    Q_INVOKABLE void updateSplitTunneling(const QString &name,
                                          const QVariant &value);
    Q_INVOKABLE void setSplitTunnelingApplication(
        const QString &executable, bool selected);
    Q_INVOKABLE void clearSplitTunnelingApplications();
    Q_INVOKABLE void addSplitTunnelingIpRange(const QString &ipRange);
    Q_INVOKABLE void removeSplitTunnelingIpRange(const QString &ipRange);
    Q_INVOKABLE void clearSplitTunnelingIpRanges();
    Q_INVOKABLE void loadCustomDns();
    Q_INVOKABLE void updateCustomDns(const QString &name,
                                     const QVariant &value);
    Q_INVOKABLE void addCustomDnsServer(const QString &address);
    Q_INVOKABLE void removeCustomDnsServer(const QString &address);
    Q_INVOKABLE QString applicationName(const QString &executable) const;

signals:
    void locationsChanged();
    void npsSurveyChanged();
    void supportReportFinished(bool success, const QString &message);

private slots:
    void onServiceRegistered(const QString &service);
    void onServiceUnregistered(const QString &service);
    void onSnapshotChanged(const QString &snapshotJson);
    void onServerDataChanged(bool topologyChanged);
    void onSettingsChanged(const QString &settingsJson);
    void onSplitTunnelingChanged(const QString &settingsJson);
    void onCustomDnsChanged(const QString &settingsJson);

private:
    friend class GroupedNavigationTest;
    VpnController(QObject *parent, bool discoverApplications);

    void registerClient();
    void unregisterClient();
    void connectBackendSignals();
    void disconnectBackendSignals();
    void setBackendAvailable(bool available);
    void applySnapshot(const QString &snapshotJson);
    void callOperation(const QString &method, const QVariantList &arguments = {});
    void callFastestOperation(const QStringList &features);
    void callSecretOperation(const QString &method, const QJsonObject &fields,
                             bool updateBusy = true);
    void callControlOperation(const QString &method,
                              const QVariantList &arguments = {});
    void requestServerLoads();
    void requestGroupServers(const QString &countryCode,
                             const QString &groupKind,
                             const QString &groupName,
                             quint64 requestGeneration,
                             int retryCount);
    bool scheduleGroupServerRetry(const QString &countryCode,
                                  const QString &groupKind,
                                  const QString &groupName,
                                  quint64 requestGeneration,
                                  int retryCount);
    void dispatchPendingLocationRefreshes();
    void setLocationsBusy(bool busy);
    void handleSnapshotReply(QDBusPendingCallWatcher *watcher);
    void handleOperationReply(QDBusPendingCallWatcher *watcher);
    void handleControlOperationReply(QDBusPendingCallWatcher *watcher);
    void handleRegisterClientReply(QDBusPendingCallWatcher *watcher);
    void handleCountriesReply(QDBusPendingCallWatcher *watcher);
    void handleLocationSearchReply(QDBusPendingCallWatcher *watcher);
    void handlePendingNpsSurveyReply(QDBusPendingCallWatcher *watcher);
    void handleServerGroupsReply(QDBusPendingCallWatcher *watcher);
    void handleServersReply(QDBusPendingCallWatcher *watcher);
    void handleServerLoadsReply(QDBusPendingCallWatcher *watcher);
    void handleSettingsReply(QDBusPendingCallWatcher *watcher);
    void handleSplitTunnelingReply(QDBusPendingCallWatcher *watcher);
    void handleCustomDnsReply(QDBusPendingCallWatcher *watcher);
    void loadPendingNpsSurvey();
    void scheduleClientRegistrationRetry();

    QDBusServiceWatcher *m_serviceWatcher = nullptr;
    QTimer *m_clientRegistrationRetryTimer = nullptr;
    CountryModel *m_countryModel = nullptr;
    LocationSearchModel *m_locationSearchModel = nullptr;
    ServerGroupModel *m_serverGroupModel = nullptr;
    ServerModel *m_serverModel = nullptr;
    InstalledApplicationModel *m_installedApplicationModel = nullptr;
    VpnSettingsModel *m_settings = nullptr;
    SplitTunnelingModel *m_splitTunneling = nullptr;
    CustomDnsModel *m_customDns = nullptr;
    LocationFilterProxyModel *m_countryFilterModel = nullptr;
    LocationFilterProxyModel *m_serverGroupFilterModel = nullptr;
    LocationFilterProxyModel *m_serverFilterModel = nullptr;
    LocationFilterProxyModel *m_applicationFilterModel = nullptr;
    bool m_backendAvailable = false;
    QString m_backendDestination;
    quint64 m_backendGeneration = 0;
    ProtonVpnKde::ClientRegistrationState m_clientRegistration;
    unsigned int m_clientRegistrationRetryCount = 0;
    bool m_ready = false;
    bool m_startupCompatible = true;
    bool m_loggedIn = false;
    QString m_authState = QStringLiteral("signed_out");
    QString m_accountName;
    QString m_planTitle;
    int m_userTier = 0;
    int m_maxConnections = 0;
    bool m_fido2Available = false;
    int m_killSwitch = 0;
    bool m_busy = false;
    bool m_locationsBusy = false;
    bool m_locationSearchBusy = false;
    quint64 m_locationSearchGeneration = 0;
    QString m_locationSearchQuery;
    bool m_npsSurveyChecked = false;
    bool m_npsSurveyAvailable = false;
    bool m_countryRefreshPending = false;
    bool m_serverGroupRefreshPending = false;
    bool m_serverRefreshPending = false;
    bool m_serverLoadsRefreshPending = false;
    quint64 m_serverRequestGeneration = 0;
    bool m_reconnectionEnabled = true;
    QStringList m_fastestFeatures;
    QString m_currentServerCountry;
    QString m_currentServerGroupKind;
    QString m_currentServerGroupName;
    QString m_state = QStringLiteral("unavailable");
    QString m_errorCode;
    QString m_serverName;
    QString m_serverLocation;
    QString m_exitCountry;
    QString m_entryCountry;
    int m_forwardedPort = 0;
    bool m_secureCore = false;
    bool m_tor = false;
    bool m_p2p = false;
    bool m_streaming = false;
    bool m_smartRouting = false;
    bool m_packetCaptureActive = false;
    bool m_coreMemoryOptimized = false;
    QString m_coreVersion;
    QString m_message = QStringLiteral("Waiting for the Proton backend service");
};
