#pragma once

#include <QObject>
#include <QString>
#include <QVariantList>

class VpnSettingsModel final : public QObject
{
    Q_OBJECT
    Q_PROPERTY(bool loaded READ loaded NOTIFY changed)
    Q_PROPERTY(bool busy READ busy NOTIFY changed)
    Q_PROPERTY(QString message READ message NOTIFY changed)
    Q_PROPERTY(QString protocol READ protocol NOTIFY changed)
    Q_PROPERTY(int protocolIndex READ protocolIndex NOTIFY changed)
    Q_PROPERTY(QVariantList protocolOptions READ protocolOptions NOTIFY changed)
    Q_PROPERTY(int killSwitch READ killSwitch NOTIFY changed)
    Q_PROPERTY(int netShield READ netShield NOTIFY changed)
    Q_PROPERTY(bool vpnAccelerator READ vpnAccelerator NOTIFY changed)
    Q_PROPERTY(bool moderateNat READ moderateNat NOTIFY changed)
    Q_PROPERTY(bool portForwarding READ portForwarding NOTIFY changed)
    Q_PROPERTY(bool ipv6 READ ipv6 NOTIFY changed)
    Q_PROPERTY(bool anonymousCrashReports READ anonymousCrashReports NOTIFY changed)
    Q_PROPERTY(bool paidFeaturesAvailable READ paidFeaturesAvailable NOTIFY changed)
    Q_PROPERTY(bool protocolEditable READ protocolEditable NOTIFY changed)
    Q_PROPERTY(bool killSwitchEditable READ killSwitchEditable NOTIFY changed)
    Q_PROPERTY(bool splitTunnelingEnabled READ splitTunnelingEnabled NOTIFY changed)
    Q_PROPERTY(bool customDnsEnabled READ customDnsEnabled NOTIFY changed)

public:
    explicit VpnSettingsModel(QObject *parent = nullptr);

    [[nodiscard]] bool loaded() const;
    [[nodiscard]] bool busy() const;
    [[nodiscard]] QString message() const;
    [[nodiscard]] QString protocol() const;
    [[nodiscard]] int protocolIndex() const;
    [[nodiscard]] QVariantList protocolOptions() const;
    [[nodiscard]] int killSwitch() const;
    [[nodiscard]] int netShield() const;
    [[nodiscard]] bool vpnAccelerator() const;
    [[nodiscard]] bool moderateNat() const;
    [[nodiscard]] bool portForwarding() const;
    [[nodiscard]] bool ipv6() const;
    [[nodiscard]] bool anonymousCrashReports() const;
    [[nodiscard]] bool paidFeaturesAvailable() const;
    [[nodiscard]] bool protocolEditable() const;
    [[nodiscard]] bool killSwitchEditable() const;
    [[nodiscard]] bool splitTunnelingEnabled() const;
    [[nodiscard]] bool customDnsEnabled() const;

    bool applyJson(const QString &settingsJson, QString *errorMessage = nullptr);
    void reset(const QString &message = {});
    void setBusy(bool busy);
    void setMessage(const QString &message);

signals:
    void changed();

private:
    bool m_loaded = false;
    bool m_busy = false;
    QString m_message;
    QString m_protocol = QStringLiteral("wireguard");
    QVariantList m_protocolOptions;
    int m_killSwitch = 0;
    int m_netShield = 0;
    bool m_vpnAccelerator = true;
    bool m_moderateNat = false;
    bool m_portForwarding = false;
    bool m_ipv6 = true;
    bool m_anonymousCrashReports = true;
    bool m_paidFeaturesAvailable = false;
    bool m_protocolEditable = false;
    bool m_killSwitchEditable = false;
    bool m_splitTunnelingEnabled = false;
    bool m_customDnsEnabled = false;
};
