// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#include "SnapshotContract.generated.h"
#include "SnapshotTestData.h"

#include <QJsonDocument>
#include <QtTest>

class SnapshotContractTest final : public QObject
{
    Q_OBJECT

private slots:
    void acceptsTheCompleteCrossLanguageFixture();
    void rejectsMissingExtraAndWronglyTypedFields();
};

void SnapshotContractTest::acceptsTheCompleteCrossLanguageFixture()
{
    const auto document = QJsonDocument::fromJson(
        ProtonVpnKde::TestData::completeSnapshot().toUtf8());
    QVERIFY(document.isObject());
    QVERIFY(ProtonVpnKde::validateSnapshotV2(document.object()));
}

void SnapshotContractTest::rejectsMissingExtraAndWronglyTypedFields()
{
    auto snapshot = QJsonDocument::fromJson(
                        ProtonVpnKde::TestData::completeSnapshot().toUtf8())
                        .object();
    snapshot.remove(QStringLiteral("accountName"));
    QVERIFY(!ProtonVpnKde::validateSnapshotV2(snapshot));

    snapshot = QJsonDocument::fromJson(
                   ProtonVpnKde::TestData::completeSnapshot().toUtf8())
                   .object();
    snapshot.insert(QStringLiteral("unexpected"), true);
    QVERIFY(!ProtonVpnKde::validateSnapshotV2(snapshot));

    snapshot = QJsonDocument::fromJson(
                   ProtonVpnKde::TestData::completeSnapshot().toUtf8())
                   .object();
    snapshot.insert(QStringLiteral("loggedIn"), QStringLiteral("true"));
    QVERIFY(!ProtonVpnKde::validateSnapshotV2(snapshot));

    snapshot = QJsonDocument::fromJson(
                   ProtonVpnKde::TestData::completeSnapshot().toUtf8())
                   .object();
    snapshot.remove(QStringLiteral("vpnExitIpv4"));
    QVERIFY(!ProtonVpnKde::validateSnapshotV2(snapshot));
}

QTEST_MAIN(SnapshotContractTest)

#include "SnapshotContractTest.moc"
