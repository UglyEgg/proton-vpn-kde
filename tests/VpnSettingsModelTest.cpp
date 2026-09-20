// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#include "VpnSettingsModel.h"
#include "SettingsRequestState.h"

#include <QJsonDocument>
#include <QJsonObject>
#include <QSignalSpy>
#include <QtTest>

namespace
{
const auto kValidSettings = R"json({
    "schemaVersion": 2,
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
    "telemetry": true,
    "telemetryAvailable": true,
    "paidFeaturesAvailable": true,
    "protocolEditable": true,
    "killSwitchEditable": true,
    "splitTunnelingEnabled": false,
    "customDnsEnabled": false,
    "packetCaptureSupported": true
})json";
}

class VpnSettingsModelTest final : public QObject
{
    Q_OBJECT

private slots:
    void appliesVersionedSettingsAtomically();
    void dataReceiptPreservesRequestOwnership();
    void requestStateRetainsUnknownWritesUntilReadback();
    void acceptsLegacySettingsDuringPackageUpgrade();
    void rejectsInvalidPayloadWithoutReplacingCurrentState();
};

void VpnSettingsModelTest::requestStateRetainsUnknownWritesUntilReadback()
{
    ProtonVpnKde::SettingsRequestState request;
    QVERIFY(request.canRead());
    const auto oldRead = request.beginRead();
    request.invalidate();
    const auto write = request.beginWrite();
    request.complete(oldRead, true, false);
    QVERIFY(request.busy());
    request.complete(write, false, true);
    QVERIFY(request.writeUnconfirmed());
    QVERIFY(request.needsRead());
    QVERIFY(request.canRead());
    const auto failedRead = request.beginRead();
    QVERIFY(!request.canRead());
    request.complete(failedRead, false, false);
    QVERIFY(request.needsRead());
    const auto readback = request.beginRead();
    request.complete(write, true, false);
    QVERIFY(request.busy());
    request.complete(readback, true, false);
    QVERIFY(!request.busy());
    QVERIFY(request.writeUnconfirmed());
    const auto laterRead = request.beginRead();
    request.complete(laterRead, true, false);
    QVERIFY(request.writeUnconfirmed());
    const auto rejectedWrite = request.beginWrite();
    QVERIFY(!request.writeUnconfirmed());
    request.complete(rejectedWrite, false, false);
    QVERIFY(!request.busy());
}

void VpnSettingsModelTest::dataReceiptPreservesRequestOwnership()
{
    VpnSettingsModel model;
    model.setBusy(true);
    model.setMessage(QStringLiteral("The current request is still completing"));
    QVERIFY(model.applyJson(QString::fromUtf8(kValidSettings)));
    QVERIFY(model.busy());
    QCOMPARE(model.message(), QStringLiteral("The current request is still completing"));
    QVERIFY(!model.applyJson(QStringLiteral("{}")));
    QVERIFY(model.busy());
    model.reset();
    QVERIFY(!model.busy());
}

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
    QVERIFY(model.telemetry());
    QVERIFY(model.telemetryAvailable());
    QVERIFY(model.paidFeaturesAvailable());
    QVERIFY(model.packetCaptureSupported());
    QCOMPARE(changed.count(), 1);
}

void VpnSettingsModelTest::acceptsLegacySettingsDuringPackageUpgrade()
{
    QJsonObject legacy = QJsonDocument::fromJson(kValidSettings).object();
    legacy.insert(QStringLiteral("schemaVersion"), 1);
    legacy.remove(QStringLiteral("telemetryAvailable"));

    VpnSettingsModel model;
    QVERIFY(model.applyJson(QString::fromUtf8(
        QJsonDocument(legacy).toJson(QJsonDocument::Compact))));
    QVERIFY(!model.telemetry());
    QVERIFY(!model.telemetryAvailable());

    legacy.remove(QStringLiteral("telemetry"));
    QVERIFY(model.applyJson(QString::fromUtf8(
        QJsonDocument(legacy).toJson(QJsonDocument::Compact))));
    QVERIFY(!model.telemetry());
    QVERIFY(!model.telemetryAvailable());
}

void VpnSettingsModelTest::rejectsInvalidPayloadWithoutReplacingCurrentState()
{
    VpnSettingsModel model;
    QVERIFY(model.applyJson(QString::fromUtf8(kValidSettings)));
    QString error;

    QVERIFY(!model.applyJson(
        QStringLiteral(R"({"schemaVersion":2,"protocol":"openvpn-udp"})"),
        &error));

    QJsonObject missingCapability =
        QJsonDocument::fromJson(kValidSettings).object();
    missingCapability.remove(QStringLiteral("telemetryAvailable"));
    QVERIFY(!model.applyJson(QString::fromUtf8(
        QJsonDocument(missingCapability).toJson(QJsonDocument::Compact)),
        &error));

    QVERIFY(!error.isEmpty());
    QVERIFY(model.loaded());
    QCOMPARE(model.protocol(), QStringLiteral("wireguard"));
    QCOMPARE(model.killSwitch(), 1);
}

QTEST_GUILESS_MAIN(VpnSettingsModelTest)

#include "VpnSettingsModelTest.moc"
