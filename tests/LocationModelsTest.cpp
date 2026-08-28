#include "LocationModels.h"

#include <QSignalSpy>
#include <QTest>

class LocationModelsTest final : public QObject
{
    Q_OBJECT

private slots:
    void parsesCountries();
    void parsesGlobalSearchResults();
    void parsesServerGroups();
    void parsesServers();
    void updatesServerLoadsWithoutResetting();
    void rejectsUnsupportedPayload();
    void filtersAcrossConfiguredRoles();
    void reordersWhenServerLoadsChange();
};

void LocationModelsTest::parsesCountries()
{
    CountryModel model;
    QString error;
    const bool accepted = model.resetFromJson(QStringLiteral(R"json(
        {"schemaVersion":1,"countries":[
            {"code":"US","serverCount":6045,"accessible":false},
            {"code":"CH","serverCount":809,"accessible":true,"free":true},
            {"code":"UK","serverCount":849,"accessible":true,
             "underMaintenance":true}
        ]}
    )json"), &error);

    QVERIFY2(accepted, qPrintable(error));
    QCOMPARE(model.rowCount(), 3);
    const auto roles = model.roleNames();
    const int codeRole = roles.key("code");
    const int nameRole = roles.key("name");
    const int countRole = roles.key("serverCount");
    const int accessibleRole = roles.key("accessible");
    const int maintenanceRole = roles.key("underMaintenance");
    const int freeRole = roles.key("free");

    bool foundSwitzerland = false;
    bool foundUnitedKingdom = false;
    for (int row = 0; row < model.rowCount(); ++row) {
        const QModelIndex index = model.index(row);
        if (index.data(codeRole).toString() == QStringLiteral("CH")) {
            foundSwitzerland = true;
            QVERIFY(!index.data(nameRole).toString().isEmpty());
            QCOMPARE(index.data(countRole).toInt(), 809);
            QVERIFY(index.data(accessibleRole).toBool());
            QVERIFY(index.data(freeRole).toBool());
        }
        if (index.data(codeRole).toString() == QStringLiteral("UK")) {
            foundUnitedKingdom = true;
            QVERIFY(index.data(nameRole).toString() != QStringLiteral("UK"));
            QVERIFY(index.data(maintenanceRole).toBool());
        }
    }
    QVERIFY(foundSwitzerland);
    QVERIFY(foundUnitedKingdom);
}

void LocationModelsTest::parsesGlobalSearchResults()
{
    CountryModel countries;
    QVERIFY(countries.resetFromJson(QStringLiteral(R"json(
        {"schemaVersion":1,"countries":[
            {"code":"CH","serverCount":12,"accessible":true},
            {"code":"US","serverCount":40,"accessible":false}
        ]}
    )json")));

    LocationSearchModel model;
    QString error;
    QVERIFY(model.resetFromJson(QStringLiteral(R"json(
        {"schemaVersion":1,"results":[
            {"kind":"location","name":"Chicago, IL","countryCode":"US",
             "accessible":false},
            {"kind":"server","name":"CH#101","countryCode":"CH",
             "location":"Zurich","groupKind":"location",
             "groupName":"Zurich","load":24,"accessible":true},
            {"kind":"unsupported","name":"ignored","countryCode":"CH"}
        ]}
    )json"), countries, QStringLiteral("ch"), &error));

    QVERIFY2(error.isEmpty(), qPrintable(error));
    QCOMPARE(model.rowCount(), 3);
    const auto roles = model.roleNames();
    QCOMPARE(model.index(0).data(roles.key("kind")).toString(),
             QStringLiteral("country"));
    QCOMPARE(model.index(0).data(roles.key("countryCode")).toString(),
             QStringLiteral("CH"));
    QCOMPARE(model.index(0).data(roles.key("serverCount")).toInt(), 12);
    QCOMPARE(model.index(1).data(roles.key("kind")).toString(),
             QStringLiteral("location"));
    QVERIFY(!model.index(1).data(roles.key("accessible")).toBool());
    QCOMPARE(model.index(2).data(roles.key("name")).toString(),
             QStringLiteral("CH#101"));
    QCOMPARE(model.index(2).data(roles.key("load")).toInt(), 24);
    QCOMPARE(model.index(2).data(roles.key("groupName")).toString(),
             QStringLiteral("Zurich"));
    QVERIFY(!model.index(2).data(roles.key("countryName")).toString().isEmpty());
}

void LocationModelsTest::parsesServerGroups()
{
    ServerGroupModel model;
    QString error;
    const bool accepted = model.resetFromJson(QStringLiteral(R"json(
        {"schemaVersion":1,"groups":[
            {"kind":"location","name":"Zurich","serverCount":14,
             "accessible":true,"tor":true,"p2p":true},
            {"kind":"secure-core","name":"Via Secure Core","serverCount":3,
             "accessible":true,"secureCore":true,"smartRouting":true}
        ]}
    )json"), &error);

    QVERIFY2(accepted, qPrintable(error));
    QCOMPARE(model.rowCount(), 2);
    const auto roles = model.roleNames();
    QCOMPARE(model.index(0).data(roles.key("name")).toString(),
             QStringLiteral("Zurich"));
    QVERIFY(model.index(0).data(roles.key("tor")).toBool());
    QCOMPARE(model.index(1).data(roles.key("kind")).toString(),
             QStringLiteral("secure-core"));
    QVERIFY(model.index(1).data(roles.key("secureCore")).toBool());
    QVERIFY(model.index(1).data(roles.key("smartRouting")).toBool());
}

void LocationModelsTest::parsesServers()
{
    ServerModel model;
    QString error;
    const bool accepted = model.resetFromJson(QStringLiteral(R"json(
        {"schemaVersion":1,"servers":[{
            "name":"CH#101","location":"Zurich","load":24,
            "entryCountry":"DE","accessible":false,
            "underMaintenance":true,"smartRouting":true,
            "secureCore":true,"tor":true,"p2p":true,"streaming":false
        }]}
    )json"), &error);

    QVERIFY2(accepted, qPrintable(error));
    QCOMPARE(model.rowCount(), 1);
    const auto roles = model.roleNames();
    const QModelIndex index = model.index(0);
    QCOMPARE(index.data(roles.key("name")).toString(), QStringLiteral("CH#101"));
    QCOMPARE(index.data(roles.key("load")).toInt(), 24);
    QVERIFY(index.data(roles.key("p2p")).toBool());
    QVERIFY(!index.data(roles.key("streaming")).toBool());
    QCOMPARE(index.data(roles.key("entryCountry")).toString(), QStringLiteral("DE"));
    QVERIFY(!index.data(roles.key("accessible")).toBool());
    QVERIFY(index.data(roles.key("underMaintenance")).toBool());
    QVERIFY(index.data(roles.key("smartRouting")).toBool());
    QVERIFY(index.data(roles.key("secureCore")).toBool());
    QVERIFY(index.data(roles.key("tor")).toBool());
}

void LocationModelsTest::updatesServerLoadsWithoutResetting()
{
    ServerModel model;
    QVERIFY(model.resetFromJson(QStringLiteral(R"json(
        {"schemaVersion":1,"servers":[
            {"name":"CH#101","location":"Zurich","load":24},
            {"name":"CH#202","location":"Zurich","load":51}
        ]}
    )json")));
    QSignalSpy resetSpy(&model, &QAbstractItemModel::modelReset);
    QSignalSpy changedSpy(&model, &QAbstractItemModel::dataChanged);

    QString error;
    QVERIFY(model.updateLoadsFromJson(QStringLiteral(R"json(
        {"schemaVersion":1,"loads":[
            {"name":"CH#101","load":60},
            {"name":"CH#202","load":51}
        ]}
    )json"), &error));

    QVERIFY2(error.isEmpty(), qPrintable(error));
    QCOMPARE(resetSpy.count(), 0);
    QCOMPARE(changedSpy.count(), 1);
    QCOMPARE(model.index(0).data(ServerModel::LoadRole).toInt(), 60);
    QCOMPARE(model.index(1).data(ServerModel::LoadRole).toInt(), 51);
}

void LocationModelsTest::rejectsUnsupportedPayload()
{
    CountryModel model;
    QString error;

    QVERIFY(!model.resetFromJson(
        QStringLiteral(R"json({"schemaVersion":2,"countries":[]})json"),
        &error));
    QVERIFY(!error.isEmpty());
    QCOMPARE(model.rowCount(), 0);
}

void LocationModelsTest::filtersAcrossConfiguredRoles()
{
    ServerModel sourceModel;
    QVERIFY(sourceModel.resetFromJson(QStringLiteral(R"json(
        {"schemaVersion":1,"servers":[
            {"name":"US-IL#584","location":"Chicago, IL","load":20},
            {"name":"CH#101","location":"Zurich","load":30}
        ]}
    )json")));

    LocationFilterProxyModel filterModel;
    filterModel.setSourceModel(&sourceModel);
    filterModel.setSearchRoles({ServerModel::NameRole, ServerModel::LocationRole});

    filterModel.setFilterText(QStringLiteral("chicago"));
    QCOMPARE(filterModel.rowCount(), 1);
    QCOMPARE(
        filterModel.index(0, 0).data(ServerModel::NameRole).toString(),
        QStringLiteral("US-IL#584"));

    filterModel.setFilterText(QStringLiteral("CH#"));
    QCOMPARE(filterModel.rowCount(), 1);
    QCOMPARE(
        filterModel.index(0, 0).data(ServerModel::NameRole).toString(),
        QStringLiteral("CH#101"));
}

void LocationModelsTest::reordersWhenServerLoadsChange()
{
    ServerModel sourceModel;
    QVERIFY(sourceModel.resetFromJson(QStringLiteral(R"json(
        {"schemaVersion":1,"servers":[
            {"name":"CH#202","location":"Zurich","load":1,
             "accessible":false},
            {"name":"CH#101","location":"Zurich","load":50},
            {"name":"CH#303","location":"Zurich","load":10}
        ]}
    )json")));

    LocationFilterProxyModel proxyModel;
    proxyModel.setSourceModel(&sourceModel);
    proxyModel.setAvailabilityRoles(
        ServerModel::AccessibleRole, ServerModel::UnderMaintenanceRole);
    proxyModel.sortByRole(ServerModel::LoadRole);
    QCOMPARE(
        proxyModel.index(0, 0).data(ServerModel::NameRole).toString(),
        QStringLiteral("CH#303"));

    QVERIFY(sourceModel.updateLoadsFromJson(QStringLiteral(R"json(
        {"schemaVersion":1,"loads":[
            {"name":"CH#202","load":0},
            {"name":"CH#101","load":5},
            {"name":"CH#303","load":90}
        ]}
    )json")));
    QCOMPARE(
        proxyModel.index(0, 0).data(ServerModel::NameRole).toString(),
        QStringLiteral("CH#101"));
}

QTEST_GUILESS_MAIN(LocationModelsTest)

#include "LocationModelsTest.moc"
