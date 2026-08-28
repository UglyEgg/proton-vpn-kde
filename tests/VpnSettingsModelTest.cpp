#include "VpnSettingsModel.h"

#include <QSignalSpy>
#include <QtTest>

namespace
{
const auto kValidSettings = R"json({
    "schemaVersion": 1,
    "protocol": "wireguard",
    "protocols": [
        {"id": "wireguard", "name": "WireGuard"},
        {"id": "openvpn-udp", "name": "OpenVPN (UDP)"}
    ],
    "killSwitch": 1,
    "netShield": 2,
    "vpnAccelerator": true,
    "moderateNat": false,
    "portForwarding": false,
    "ipv6": true,
    "anonymousCrashReports": false,
    "paidFeaturesAvailable": true,
    "protocolEditable": true,
    "killSwitchEditable": true,
    "splitTunnelingEnabled": false,
    "customDnsEnabled": false
})json";
}

class VpnSettingsModelTest final : public QObject
{
    Q_OBJECT

private slots:
    void appliesVersionedSettingsAtomically();
    void rejectsInvalidPayloadWithoutReplacingCurrentState();
};

void VpnSettingsModelTest::appliesVersionedSettingsAtomically()
{
    VpnSettingsModel model;
    QSignalSpy changed(&model, &VpnSettingsModel::changed);
    QString error;

    QVERIFY(model.applyJson(QString::fromUtf8(kValidSettings), &error));
    QVERIFY(error.isEmpty());
    QVERIFY(model.loaded());
    QCOMPARE(model.protocol(), QStringLiteral("wireguard"));
    QCOMPARE(model.protocolIndex(), 0);
    QCOMPARE(model.protocolOptions().size(), 2);
    QCOMPARE(model.killSwitch(), 1);
    QCOMPARE(model.netShield(), 2);
    QVERIFY(model.vpnAccelerator());
    QVERIFY(!model.anonymousCrashReports());
    QVERIFY(model.paidFeaturesAvailable());
    QCOMPARE(changed.count(), 1);
}

void VpnSettingsModelTest::rejectsInvalidPayloadWithoutReplacingCurrentState()
{
    VpnSettingsModel model;
    QVERIFY(model.applyJson(QString::fromUtf8(kValidSettings)));
    QString error;

    QVERIFY(!model.applyJson(
        QStringLiteral(R"({"schemaVersion":2,"protocol":"openvpn-udp"})"),
        &error));

    QVERIFY(!error.isEmpty());
    QVERIFY(model.loaded());
    QCOMPARE(model.protocol(), QStringLiteral("wireguard"));
    QCOMPARE(model.killSwitch(), 1);
}

QTEST_GUILESS_MAIN(VpnSettingsModelTest)

#include "VpnSettingsModelTest.moc"
