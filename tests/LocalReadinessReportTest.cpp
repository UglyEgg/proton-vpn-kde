// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#include "CommunityReportFormat.h"
#include "DesktopReadiness.h"

#include <QMetaProperty>
#include <QtTest>

class LocalReadinessReportTest final : public QObject
{
    Q_OBJECT

private Q_SLOTS:
    void secretServiceClassification();
    void readinessPropertiesHaveIndependentSignals();
    void packageCapabilityParsing();
    void reportContainsOnlyAllowlistedFacts();
    void unavailableStateDoesNotClaimCompatibility();
};

void LocalReadinessReportTest::readinessPropertiesHaveIndependentSignals()
{
    const QMetaObject &meta = DesktopReadiness::staticMetaObject;
    const QMetaProperty secret = meta.property(
        meta.indexOfProperty("secretServiceState"));
    const QMetaProperty core = meta.property(
        meta.indexOfProperty("coreCapabilityState"));
    const QMetaProperty keyring = meta.property(
        meta.indexOfProperty("keyringCapabilityState"));

    QCOMPARE(secret.notifySignal().name(), QByteArray("secretServiceStateChanged"));
    QCOMPARE(core.notifySignal().name(), QByteArray("packageCapabilityStatesChanged"));
    QCOMPARE(keyring.notifySignal().name(), QByteArray("packageCapabilityStatesChanged"));
    QVERIFY(secret.notifySignalIndex() != core.notifySignalIndex());
}

void LocalReadinessReportTest::secretServiceClassification()
{
    const QString service = QStringLiteral("org.freedesktop.secrets");
    QCOMPARE(DesktopReadiness::classifySecretService({service}, {}),
             QStringLiteral("running"));
    QCOMPARE(DesktopReadiness::classifySecretService({service}, {service}),
             QStringLiteral("running"));
    QCOMPARE(DesktopReadiness::classifySecretService({}, {service}),
             QStringLiteral("activatable"));
    QCOMPARE(DesktopReadiness::classifySecretService({}, {}),
             QStringLiteral("missing"));
}

void LocalReadinessReportTest::packageCapabilityParsing()
{
    const QByteArray core = "proton-vpn-api-core-plasma-protun-secret";
    const QByteArray keyring = "proton-keyring-secret-service-owner-pinned";
    const QByteArray rpm = core + " = 1\n" + keyring + " = 1\n";
    const QByteArray dpkg = core + " (= 1), other-virtual (= 2)\n"
                            + keyring + " (= 1)\n";
    QVERIFY(DesktopReadiness::containsPackageCapability(rpm, core));
    QVERIFY(DesktopReadiness::containsPackageCapability(rpm, keyring));
    QVERIFY(DesktopReadiness::containsPackageCapability(dpkg, core));
    QVERIFY(DesktopReadiness::containsPackageCapability(dpkg, keyring));
    QVERIFY(DesktopReadiness::containsPackageCapability(core + " = 10\n", core));
    QVERIFY(!DesktopReadiness::containsPackageCapability(core + " = 0\n", core));
    QVERIFY(!DesktopReadiness::containsPackageCapability(
        "other-" + core + " = 1\n", core));
    QVERIFY(!DesktopReadiness::containsPackageCapability(
        core + " (= 1) plus-secret\n", core));
}

void LocalReadinessReportTest::reportContainsOnlyAllowlistedFacts()
{
    CommunityReportFacts facts;
    facts.clientVersion = QStringLiteral("0.14.2");
    facts.coreVersion = QStringLiteral("5.6.20\npassword=do-not-share");
    facts.osFamily = QStringLiteral("fedora\n/home/private");
    facts.qtVersion = QStringLiteral("6.10.2");
    facts.secretServiceState = QStringLiteral("running\n203.0.113.8");
    facts.vpnState = QStringLiteral("connected\nserver=secret");
    facts.errorCode = QStringLiteral("tunnel_setup_failed\naccount=secret");
    facts.backendAvailable = true;
    facts.backendReady = true;
    facts.snapshotHealthy = true;
    facts.startupCompatible = true;
    facts.coreMemoryOptimized = true;
    facts.telemetryBuildEnabled = true;
    facts.telemetryRuntimeAvailable = true;
    facts.telemetryPreferenceKnown = true;
    facts.telemetryEnabled = false;

    const QString report = formatCommunityReport(facts);
    QVERIFY(report.contains(QStringLiteral("Client version: 0.14.2")));
    QVERIFY(report.contains(QStringLiteral("Core startup check: compatible")));
    QVERIFY(report.contains(QStringLiteral("Core memory overlay: detected")));
    QVERIFY(report.contains(QStringLiteral("Connection telemetry: disabled")));
    QVERIFY(!report.contains(QStringLiteral("do-not-share")));
    QVERIFY(!report.contains(QStringLiteral("/home/private")));
    QVERIFY(!report.contains(QStringLiteral("203.0.113.8")));
    QVERIFY(!report.contains(QStringLiteral("account=secret")));
    QVERIFY(!report.contains(QStringLiteral("server=secret")));
    QVERIFY(report.contains(QStringLiteral("Proton Core: not reported")));
    QVERIFY(report.contains(QStringLiteral("VPN state: unknown")));
    QVERIFY(report.contains(QStringLiteral("Error code: unknown")));
}

void LocalReadinessReportTest::unavailableStateDoesNotClaimCompatibility()
{
    CommunityReportFacts facts;
    facts.clientVersion = QStringLiteral("0.14.2");
    facts.coreVersion = QStringLiteral("5.6.20");
    facts.osFamily = QStringLiteral("fedora");
    facts.qtVersion = QStringLiteral("6.10.2");
    facts.secretServiceState = QStringLiteral("activatable");
    facts.vpnState = QStringLiteral("disconnected");
    facts.startupCompatible = true;
    facts.coreMemoryOptimized = true;

    const QString report = formatCommunityReport(facts);
    QVERIFY(report.contains(QStringLiteral("Backend: unavailable")));
    QVERIFY(report.contains(QStringLiteral("Core startup check: not checked")));
    QVERIFY(report.contains(QStringLiteral("Core memory overlay: not checked")));
    QVERIFY(report.contains(QStringLiteral("Secret Service advertised: activatable")));
    QVERIFY(report.contains(
        QStringLiteral("Connection telemetry: disabled by build policy")));
}

QTEST_GUILESS_MAIN(LocalReadinessReportTest)

#include "LocalReadinessReportTest.moc"
