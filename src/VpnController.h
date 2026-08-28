#pragma once

#include "VpnSettingsModel.h"
#include "SplitTunnelingModel.h"
#include "CustomDnsModel.h"

#include <QObject>
#include <QString>
#include <QVariant>

class QDBusPendingCallWatcher;
class QDBusServiceWatcher;
class QAbstractItemModel;
class QJsonObject;
class CountryModel;
class LocationFilterProxyModel;
class ServerGroupModel;
class ServerModel;
class InstalledApplicationModel;

class VpnController final : public QObject
{
    Q_OBJECT
    Q_PROPERTY(bool backendAvailable READ backendAvailable NOTIFY backendAvailableChanged)
    Q_PROPERTY(bool ready READ ready NOTIFY snapshotChanged)
    Q_PROPERTY(bool loggedIn READ loggedIn NOTIFY snapshotChanged)
    Q_PROPERTY(QString authState READ authState NOTIFY snapshotChanged)
    Q_PROPERTY(QString accountName READ accountName NOTIFY snapshotChanged)
    Q_PROPERTY(QString planTitle READ planTitle NOTIFY snapshotChanged)
    Q_PROPERTY(int userTier READ userTier NOTIFY snapshotChanged)
    Q_PROPERTY(int maxConnections READ maxConnections NOTIFY snapshotChanged)
    Q_PROPERTY(bool fido2Available READ fido2Available NOTIFY snapshotChanged)
    Q_PROPERTY(bool busy READ busy NOTIFY snapshotChanged)
    Q_PROPERTY(bool locationsBusy READ locationsBusy NOTIFY locationsChanged)
    Q_PROPERTY(QString state READ state NOTIFY snapshotChanged)
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
    Q_PROPERTY(QString message READ message NOTIFY snapshotChanged)
    Q_PROPERTY(QString primaryActionText READ primaryActionText NOTIFY snapshotChanged)
    Q_PROPERTY(bool primaryActionEnabled READ primaryActionEnabled NOTIFY snapshotChanged)
    Q_PROPERTY(QAbstractItemModel *countryModel READ countryModel CONSTANT)
    Q_PROPERTY(QAbstractItemModel *serverGroupModel READ serverGroupModel CONSTANT)
    Q_PROPERTY(QAbstractItemModel *serverModel READ serverModel CONSTANT)
    Q_PROPERTY(QAbstractItemModel *applicationModel READ applicationModel CONSTANT)
    Q_PROPERTY(VpnSettingsModel *settings READ settings CONSTANT)
    Q_PROPERTY(SplitTunnelingModel *splitTunneling READ splitTunneling CONSTANT)
    Q_PROPERTY(CustomDnsModel *customDns READ customDns CONSTANT)

public:
    explicit VpnController(QObject *parent = nullptr);

    [[nodiscard]] bool backendAvailable() const;
    [[nodiscard]] bool ready() const;
    [[nodiscard]] bool loggedIn() const;
    [[nodiscard]] QString authState() const;
    [[nodiscard]] QString accountName() const;
    [[nodiscard]] QString planTitle() const;
    [[nodiscard]] int userTier() const;
    [[nodiscard]] int maxConnections() const;
    [[nodiscard]] bool fido2Available() const;
    [[nodiscard]] bool busy() const;
    [[nodiscard]] bool locationsBusy() const;
    [[nodiscard]] QString state() const;
    [[nodiscard]] QString serverName() const;
    [[nodiscard]] QString serverLocation() const;
    [[nodiscard]] QString exitCountry() const;
    [[nodiscard]] QString entryCountry() const;
    [[nodiscard]] int forwardedPort() const;
    [[nodiscard]] bool secureCore() const;
    [[nodiscard]] bool tor() const;
    [[nodiscard]] bool p2p() const;
    [[nodiscard]] bool streaming() const;
    [[nodiscard]] bool smartRouting() const;
    [[nodiscard]] QString message() const;
    [[nodiscard]] QString primaryActionText() const;
    [[nodiscard]] bool primaryActionEnabled() const;
    [[nodiscard]] QAbstractItemModel *countryModel() const;
    [[nodiscard]] QAbstractItemModel *serverGroupModel() const;
    [[nodiscard]] QAbstractItemModel *serverModel() const;
    [[nodiscard]] QAbstractItemModel *applicationModel() const;
    [[nodiscard]] VpnSettingsModel *settings() const;
    [[nodiscard]] SplitTunnelingModel *splitTunneling() const;
    [[nodiscard]] CustomDnsModel *customDns() const;

    Q_INVOKABLE void refresh();
    Q_INVOKABLE void activatePrimaryAction();
    Q_INVOKABLE void copyForwardedPort();
    Q_INVOKABLE void loadCountries();
    Q_INVOKABLE void loadServerGroups(const QString &countryCode);
    Q_INVOKABLE void loadGroupServers(const QString &countryCode,
                                      const QString &groupKind,
                                      const QString &groupName);
    Q_INVOKABLE void loadServers(const QString &countryCode);
    Q_INVOKABLE void clearGroupServerContext();
    Q_INVOKABLE void clearServerContext();
    Q_INVOKABLE void connectCountry(const QString &countryCode);
    Q_INVOKABLE void connectTarget(const QString &target);
    Q_INVOKABLE void connectGroup(const QString &countryCode,
                                  const QString &groupKind,
                                  const QString &groupName);
    Q_INVOKABLE void connectServer(const QString &serverName);
    Q_INVOKABLE void login(const QString &username, const QString &password);
    Q_INVOKABLE void submitTwoFactor(const QString &code);
    Q_INVOKABLE void cancelLogin();
    Q_INVOKABLE void beginFido2();
    Q_INVOKABLE void submitFido2Pin(const QString &pin);
    Q_INVOKABLE void cancelFido2();
    Q_INVOKABLE void logout();
    Q_INVOKABLE void setCountryFilter(const QString &filterText);
    Q_INVOKABLE void setServerFilter(const QString &filterText);
    Q_INVOKABLE void setApplicationFilter(const QString &filterText);
    Q_INVOKABLE void setReconnectionEnabled(bool enabled);
    Q_INVOKABLE void loadSettings();
    Q_INVOKABLE void updateSetting(const QString &name, const QVariant &value);
    Q_INVOKABLE void loadSplitTunneling();
    Q_INVOKABLE void updateSplitTunneling(const QString &name,
                                          const QVariant &value);
    Q_INVOKABLE void setSplitTunnelingApplication(
        const QString &executable, bool selected);
    Q_INVOKABLE void clearSplitTunnelingApplications();
    Q_INVOKABLE void loadCustomDns();
    Q_INVOKABLE void updateCustomDns(const QString &name,
                                     const QVariant &value);
    Q_INVOKABLE void addCustomDnsServer(const QString &address);
    Q_INVOKABLE void removeCustomDnsServer(const QString &address);
    Q_INVOKABLE QString applicationName(const QString &executable) const;

signals:
    void backendAvailableChanged();
    void snapshotChanged();
    void locationsChanged();

private slots:
    void onServiceRegistered(const QString &service);
    void onServiceUnregistered(const QString &service);
    void onSnapshotChanged(const QString &snapshotJson);
    void onServerDataChanged(bool topologyChanged);
    void onSettingsChanged(const QString &settingsJson);
    void onSplitTunnelingChanged(const QString &settingsJson);
    void onCustomDnsChanged(const QString &settingsJson);

private:
    void setBackendAvailable(bool available);
    void applySnapshot(const QString &snapshotJson);
    void callOperation(const QString &method, const QVariantList &arguments = {});
    void callSecretOperation(const QString &method, const QJsonObject &fields,
                             bool updateBusy = true);
    void callControlOperation(const QString &method,
                              const QVariantList &arguments = {});
    void requestServerLoads();
    void dispatchPendingLocationRefreshes();
    void setLocationsBusy(bool busy);
    void handleSnapshotReply(QDBusPendingCallWatcher *watcher);
    void handleOperationReply(QDBusPendingCallWatcher *watcher);
    void handleCountriesReply(QDBusPendingCallWatcher *watcher);
    void handleServerGroupsReply(QDBusPendingCallWatcher *watcher);
    void handleServersReply(QDBusPendingCallWatcher *watcher);
    void handleServerLoadsReply(QDBusPendingCallWatcher *watcher);
    void handleSettingsReply(QDBusPendingCallWatcher *watcher);
    void handleSplitTunnelingReply(QDBusPendingCallWatcher *watcher);
    void handleCustomDnsReply(QDBusPendingCallWatcher *watcher);

    QDBusServiceWatcher *m_serviceWatcher = nullptr;
    CountryModel *m_countryModel = nullptr;
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
    bool m_ready = false;
    bool m_loggedIn = false;
    QString m_authState = QStringLiteral("signed_out");
    QString m_accountName;
    QString m_planTitle;
    int m_userTier = 0;
    int m_maxConnections = 0;
    bool m_fido2Available = false;
    bool m_busy = false;
    bool m_locationsBusy = false;
    bool m_countryRefreshPending = false;
    bool m_serverGroupRefreshPending = false;
    bool m_serverRefreshPending = false;
    bool m_serverLoadsRefreshPending = false;
    bool m_reconnectionEnabled = true;
    QString m_currentServerCountry;
    QString m_currentServerGroupKind;
    QString m_currentServerGroupName;
    QString m_state = QStringLiteral("unavailable");
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
    QString m_message = QStringLiteral("Waiting for the Proton backend service");
};
