// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#include "SplitTunnelingModel.h"

#include <QSignalSpy>
#include <QtTest>

namespace
{
const auto kValidSettings = R"json({
    "schemaVersion": 1,
    "available": true,
    "paidFeaturesAvailable": true,
    "enabled": true,
    "mode": "exclude",
    "excludeAppPaths": ["/usr/bin/firefox"],
    "includeAppPaths": ["/usr/bin/konsole"],
    "excludeIpRanges": ["10.0.0.0/8"],
    "includeIpRanges": [],
    "excludeIpRangeCount": 1,
    "includeIpRangeCount": 0
})json";
}

class SplitTunnelingModelTest final : public QObject
{
    Q_OBJECT

private slots:
    void appliesVersionedSettingsAtomically();
    void rejectsInvalidPayloadWithoutReplacingCurrentState();
};

void SplitTunnelingModelTest::appliesVersionedSettingsAtomically()
{
    SplitTunnelingModel model;
    QSignalSpy changed(&model, &SplitTunnelingModel::changed);
    QString error;

    QVERIFY(model.applyJson(QString::fromUtf8(kValidSettings), &error));
    QVERIFY(error.isEmpty());
    QVERIFY(model.loaded());
    QVERIFY(model.available());
    QVERIFY(model.paidFeaturesAvailable());
    QVERIFY(model.enabled());
    QCOMPARE(model.mode(), QStringLiteral("exclude"));
    QCOMPARE(model.modeIndex(), 0);
    QCOMPARE(model.selectedAppPaths(), QStringList{QStringLiteral("/usr/bin/firefox")});
    QCOMPARE(model.selectedIpRangeCount(), 1);
    QCOMPARE(model.selectedIpRanges(), QStringList{QStringLiteral("10.0.0.0/8")});
    QVERIFY(model.containsApplication(QStringLiteral("/usr/bin/firefox")));
    QCOMPARE(changed.count(), 1);
}

void SplitTunnelingModelTest::rejectsInvalidPayloadWithoutReplacingCurrentState()
{
    SplitTunnelingModel model;
    QVERIFY(model.applyJson(QString::fromUtf8(kValidSettings)));
    QString error;

    QVERIFY(!model.applyJson(
        QStringLiteral(R"({"schemaVersion":1,"mode":"unknown"})"),
        &error));

    QVERIFY(!error.isEmpty());
    QVERIFY(model.loaded());
    QCOMPARE(model.mode(), QStringLiteral("exclude"));
    QCOMPARE(model.selectedAppPaths(), QStringList{QStringLiteral("/usr/bin/firefox")});
}

QTEST_GUILESS_MAIN(SplitTunnelingModelTest)

#include "SplitTunnelingModelTest.moc"
