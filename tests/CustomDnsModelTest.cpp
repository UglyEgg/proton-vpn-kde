#include "CustomDnsModel.h"

#include <QSignalSpy>
#include <QtTest>

namespace
{
const auto kValidSettings = R"json({
    "schemaVersion": 1,
    "paidFeaturesAvailable": true,
    "enabled": true,
    "servers": [
        {"address": "1.1.1.1", "enabled": true},
        {"address": "2606:4700:4700::1111", "enabled": false}
    ]
})json";
}

class CustomDnsModelTest final : public QObject
{
    Q_OBJECT

private slots:
    void appliesVersionedSettingsAtomically();
    void rejectsInvalidPayloadWithoutReplacingCurrentState();
    void normalizesAndFindsAddresses();
    void preservesExistingDuplicateEntries();
};

void CustomDnsModelTest::appliesVersionedSettingsAtomically()
{
    CustomDnsModel model;
    QSignalSpy changed(&model, &CustomDnsModel::changed);
    QString error;

    QVERIFY(model.applyJson(QString::fromUtf8(kValidSettings), &error));
    QVERIFY(error.isEmpty());
    QVERIFY(model.loaded());
    QVERIFY(model.paidFeaturesAvailable());
    QVERIFY(model.enabled());
    QCOMPARE(model.serverCount(), 2);
    QCOMPARE(model.servers().at(0).toMap().value(QStringLiteral("address")),
             QStringLiteral("1.1.1.1"));
    QVERIFY(!model.servers().at(1).toMap().value(
        QStringLiteral("enabled")).toBool());
    QCOMPARE(changed.count(), 1);
}

void CustomDnsModelTest::rejectsInvalidPayloadWithoutReplacingCurrentState()
{
    CustomDnsModel model;
    QVERIFY(model.applyJson(QString::fromUtf8(kValidSettings)));
    QString error;

    QVERIFY(!model.applyJson(QStringLiteral(R"json({
        "schemaVersion": 1,
        "paidFeaturesAvailable": true,
        "enabled": true,
        "servers": [{"address": "dns.example", "enabled": true}]
    })json"), &error));

    QVERIFY(!error.isEmpty());
    QVERIFY(model.loaded());
    QCOMPARE(model.serverCount(), 2);
    QVERIFY(model.enabled());
}

void CustomDnsModelTest::normalizesAndFindsAddresses()
{
    CustomDnsModel model;
    QVERIFY(model.applyJson(QString::fromUtf8(kValidSettings)));

    QCOMPARE(CustomDnsModel::normalizeServerAddress(
                 QStringLiteral("2606:4700:4700:0:0:0:0:1111")),
             QStringLiteral("2606:4700:4700::1111"));
    QVERIFY(model.containsServer(
        QStringLiteral("2606:4700:4700:0:0:0:0:1111")));
    QVERIFY(!model.isValidServerAddress(QStringLiteral("dns.example")));
}

void CustomDnsModelTest::preservesExistingDuplicateEntries()
{
    CustomDnsModel model;
    QVERIFY(model.applyJson(QStringLiteral(R"json({
        "schemaVersion": 1,
        "paidFeaturesAvailable": true,
        "enabled": false,
        "servers": [
            {"address": "2001:db8::1", "enabled": true},
            {"address": "2001:0db8:0:0:0:0:0:1", "enabled": false}
        ]
    })json")));

    QCOMPARE(model.serverCount(), 2);
    QCOMPARE(model.servers().at(0).toMap().value(QStringLiteral("address")),
             model.servers().at(1).toMap().value(QStringLiteral("address")));
}

QTEST_GUILESS_MAIN(CustomDnsModelTest)

#include "CustomDnsModelTest.moc"
