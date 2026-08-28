#include "VpnSettingsModel.h"

#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonParseError>
#include <QSet>
#include <QVariantMap>

namespace
{
bool readBoolean(const QJsonObject &object, const QString &key, bool *value)
{
    const QJsonValue item = object.value(key);
    if (!item.isBool()) {
        return false;
    }
    *value = item.toBool();
    return true;
}

bool readMode(const QJsonObject &object, const QString &key, int *value)
{
    const QJsonValue item = object.value(key);
    if (!item.isDouble()) {
        return false;
    }
    const int mode = item.toInt(-1);
    if (mode < 0 || mode > 2) {
        return false;
    }
    *value = mode;
    return true;
}
}

VpnSettingsModel::VpnSettingsModel(QObject *parent)
    : QObject(parent)
{
}

bool VpnSettingsModel::loaded() const { return m_loaded; }
bool VpnSettingsModel::busy() const { return m_busy; }
QString VpnSettingsModel::message() const { return m_message; }
QString VpnSettingsModel::protocol() const { return m_protocol; }
QVariantList VpnSettingsModel::protocolOptions() const { return m_protocolOptions; }
int VpnSettingsModel::killSwitch() const { return m_killSwitch; }
int VpnSettingsModel::netShield() const { return m_netShield; }
bool VpnSettingsModel::vpnAccelerator() const { return m_vpnAccelerator; }
bool VpnSettingsModel::moderateNat() const { return m_moderateNat; }
bool VpnSettingsModel::portForwarding() const { return m_portForwarding; }
bool VpnSettingsModel::ipv6() const { return m_ipv6; }
bool VpnSettingsModel::anonymousCrashReports() const { return m_anonymousCrashReports; }
bool VpnSettingsModel::paidFeaturesAvailable() const { return m_paidFeaturesAvailable; }
bool VpnSettingsModel::protocolEditable() const { return m_protocolEditable; }
bool VpnSettingsModel::killSwitchEditable() const { return m_killSwitchEditable; }
bool VpnSettingsModel::splitTunnelingEnabled() const { return m_splitTunnelingEnabled; }
bool VpnSettingsModel::customDnsEnabled() const { return m_customDnsEnabled; }

int VpnSettingsModel::protocolIndex() const
{
    for (qsizetype index = 0; index < m_protocolOptions.size(); ++index) {
        if (m_protocolOptions.at(index).toMap().value(QStringLiteral("id")).toString()
            == m_protocol) {
            return static_cast<int>(index);
        }
    }
    return -1;
}

bool VpnSettingsModel::applyJson(const QString &settingsJson,
                                 QString *errorMessage)
{
    QJsonParseError parseError;
    const QJsonDocument document = QJsonDocument::fromJson(
        settingsJson.toUtf8(), &parseError);
    const auto fail = [errorMessage](const QString &message) {
        if (errorMessage) {
            *errorMessage = message;
        }
        return false;
    };
    if (parseError.error != QJsonParseError::NoError || !document.isObject()) {
        return fail(tr("The backend returned invalid VPN settings"));
    }

    const QJsonObject object = document.object();
    if (object.value(QStringLiteral("schemaVersion")).toInt() != 1) {
        return fail(tr("The backend uses an unsupported settings version"));
    }
    const QJsonValue protocolValue = object.value(QStringLiteral("protocol"));
    const QJsonValue protocolsValue = object.value(QStringLiteral("protocols"));
    if (!protocolValue.isString() || protocolValue.toString().isEmpty()
        || !protocolsValue.isArray()) {
        return fail(tr("The backend returned incomplete VPN settings"));
    }

    QVariantList protocolOptions;
    QSet<QString> protocolIds;
    for (const QJsonValue item : protocolsValue.toArray()) {
        if (!item.isObject()) {
            return fail(tr("The backend returned an invalid protocol list"));
        }
        const QJsonObject protocol = item.toObject();
        const QString id = protocol.value(QStringLiteral("id")).toString();
        const QString name = protocol.value(QStringLiteral("name")).toString();
        if (id.isEmpty() || name.isEmpty() || protocolIds.contains(id)) {
            return fail(tr("The backend returned an invalid protocol list"));
        }
        protocolIds.insert(id);
        protocolOptions.append(QVariantMap{
            {QStringLiteral("id"), id},
            {QStringLiteral("name"), name},
        });
    }
    const QString protocol = protocolValue.toString();
    if (!protocolIds.contains(protocol)) {
        return fail(tr("The selected VPN protocol is unavailable"));
    }

    int killSwitch = 0;
    int netShield = 0;
    bool vpnAccelerator = false;
    bool moderateNat = false;
    bool portForwarding = false;
    bool ipv6 = false;
    bool anonymousCrashReports = false;
    bool paidFeaturesAvailable = false;
    bool protocolEditable = false;
    bool killSwitchEditable = false;
    bool splitTunnelingEnabled = false;
    bool customDnsEnabled = false;
    if (!readMode(object, QStringLiteral("killSwitch"), &killSwitch)
        || !readMode(object, QStringLiteral("netShield"), &netShield)
        || !readBoolean(object, QStringLiteral("vpnAccelerator"), &vpnAccelerator)
        || !readBoolean(object, QStringLiteral("moderateNat"), &moderateNat)
        || !readBoolean(object, QStringLiteral("portForwarding"), &portForwarding)
        || !readBoolean(object, QStringLiteral("ipv6"), &ipv6)
        || !readBoolean(object, QStringLiteral("anonymousCrashReports"), &anonymousCrashReports)
        || !readBoolean(object, QStringLiteral("paidFeaturesAvailable"), &paidFeaturesAvailable)
        || !readBoolean(object, QStringLiteral("protocolEditable"), &protocolEditable)
        || !readBoolean(object, QStringLiteral("killSwitchEditable"), &killSwitchEditable)
        || !readBoolean(object, QStringLiteral("splitTunnelingEnabled"), &splitTunnelingEnabled)
        || !readBoolean(object, QStringLiteral("customDnsEnabled"), &customDnsEnabled)) {
        return fail(tr("The backend returned incomplete VPN settings"));
    }

    m_protocol = protocol;
    m_protocolOptions = protocolOptions;
    m_killSwitch = killSwitch;
    m_netShield = netShield;
    m_vpnAccelerator = vpnAccelerator;
    m_moderateNat = moderateNat;
    m_portForwarding = portForwarding;
    m_ipv6 = ipv6;
    m_anonymousCrashReports = anonymousCrashReports;
    m_paidFeaturesAvailable = paidFeaturesAvailable;
    m_protocolEditable = protocolEditable;
    m_killSwitchEditable = killSwitchEditable;
    m_splitTunnelingEnabled = splitTunnelingEnabled;
    m_customDnsEnabled = customDnsEnabled;
    m_loaded = true;
    m_busy = false;
    m_message.clear();
    emit changed();
    return true;
}

void VpnSettingsModel::reset(const QString &message)
{
    m_loaded = false;
    m_busy = false;
    m_message = message;
    m_protocolOptions.clear();
    m_protocolEditable = false;
    m_killSwitchEditable = false;
    emit changed();
}

void VpnSettingsModel::setBusy(bool busy)
{
    if (m_busy == busy) {
        return;
    }
    m_busy = busy;
    emit changed();
}

void VpnSettingsModel::setMessage(const QString &message)
{
    if (m_message == message) {
        return;
    }
    m_message = message;
    emit changed();
}
