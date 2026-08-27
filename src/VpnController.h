#pragma once

#include <QObject>
#include <QString>
#include <QVariant>

class QDBusPendingCallWatcher;
class QDBusServiceWatcher;
class QAbstractItemModel;
class QJsonObject;
class CountryModel;
class LocationFilterProxyModel;
class ServerModel;

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
    Q_PROPERTY(QString message READ message NOTIFY snapshotChanged)
    Q_PROPERTY(QString primaryActionText READ primaryActionText NOTIFY snapshotChanged)
    Q_PROPERTY(bool primaryActionEnabled READ primaryActionEnabled NOTIFY snapshotChanged)
    Q_PROPERTY(QAbstractItemModel *countryModel READ countryModel CONSTANT)
    Q_PROPERTY(QAbstractItemModel *serverModel READ serverModel CONSTANT)

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
    [[nodiscard]] QString message() const;
    [[nodiscard]] QString primaryActionText() const;
    [[nodiscard]] bool primaryActionEnabled() const;
    [[nodiscard]] QAbstractItemModel *countryModel() const;
    [[nodiscard]] QAbstractItemModel *serverModel() const;

    Q_INVOKABLE void refresh();
    Q_INVOKABLE void activatePrimaryAction();
    Q_INVOKABLE void loadCountries();
    Q_INVOKABLE void loadServers(const QString &countryCode);
    Q_INVOKABLE void clearServerContext();
    Q_INVOKABLE void connectCountry(const QString &countryCode);
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
    Q_INVOKABLE void setServerSortMode(const QString &mode);
    Q_INVOKABLE void setReconnectionEnabled(bool enabled);

signals:
    void backendAvailableChanged();
    void snapshotChanged();
    void locationsChanged();

private slots:
    void onServiceRegistered(const QString &service);
    void onServiceUnregistered(const QString &service);
    void onSnapshotChanged(const QString &snapshotJson);
    void onServerDataChanged(bool topologyChanged);

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
    void handleServersReply(QDBusPendingCallWatcher *watcher);
    void handleServerLoadsReply(QDBusPendingCallWatcher *watcher);

    QDBusServiceWatcher *m_serviceWatcher = nullptr;
    CountryModel *m_countryModel = nullptr;
    ServerModel *m_serverModel = nullptr;
    LocationFilterProxyModel *m_countryFilterModel = nullptr;
    LocationFilterProxyModel *m_serverFilterModel = nullptr;
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
    bool m_serverRefreshPending = false;
    bool m_serverLoadsRefreshPending = false;
    bool m_reconnectionEnabled = true;
    QString m_currentServerCountry;
    QString m_state = QStringLiteral("unavailable");
    QString m_serverName;
    QString m_message = QStringLiteral("Waiting for the Proton backend service");
};
