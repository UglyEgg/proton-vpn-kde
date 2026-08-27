#include "LocationModels.h"

#include <QTest>

class LocationModelsTest final : public QObject
{
    Q_OBJECT

private slots:
    void parsesCountries();
    void parsesServers();
    void rejectsUnsupportedPayload();
    void filtersAcrossConfiguredRoles();
};

void LocationModelsTest::parsesCountries()
{
    CountryModel model;
    QString error;
    const bool accepted = model.resetFromJson(QStringLiteral(R"json(
        {"schemaVersion":1,"countries":[
            {"code":"US","serverCount":6045},
            {"code":"CH","serverCount":809},
            {"code":"UK","serverCount":849}
        ]}
    )json"), &error);

    QVERIFY2(accepted, qPrintable(error));
    QCOMPARE(model.rowCount(), 3);
    const auto roles = model.roleNames();
    const int codeRole = roles.key("code");
    const int nameRole = roles.key("name");
    const int countRole = roles.key("serverCount");

    bool foundSwitzerland = false;
    bool foundUnitedKingdom = false;
    for (int row = 0; row < model.rowCount(); ++row) {
        const QModelIndex index = model.index(row);
        if (index.data(codeRole).toString() == QStringLiteral("CH")) {
            foundSwitzerland = true;
            QVERIFY(!index.data(nameRole).toString().isEmpty());
            QCOMPARE(index.data(countRole).toInt(), 809);
        }
        if (index.data(codeRole).toString() == QStringLiteral("UK")) {
            foundUnitedKingdom = true;
            QVERIFY(index.data(nameRole).toString() != QStringLiteral("UK"));
        }
    }
    QVERIFY(foundSwitzerland);
    QVERIFY(foundUnitedKingdom);
}

void LocationModelsTest::parsesServers()
{
    ServerModel model;
    QString error;
    const bool accepted = model.resetFromJson(QStringLiteral(R"json(
        {"schemaVersion":1,"servers":[{
            "name":"CH#101","location":"Zurich","load":24,
            "p2p":true,"streaming":false
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

QTEST_GUILESS_MAIN(LocationModelsTest)

#include "LocationModelsTest.moc"
