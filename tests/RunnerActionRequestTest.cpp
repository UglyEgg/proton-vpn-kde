#include "RunnerActionRequest.h"

#include <QTest>

class RunnerActionRequestTest final : public QObject
{
    Q_OBJECT

private slots:
    void acceptsIntendedActions_data();
    void acceptsIntendedActions();
    void rejectsUnintendedOrMalformedActions_data();
    void rejectsUnintendedOrMalformedActions();
};

void RunnerActionRequestTest::acceptsIntendedActions_data()
{
    QTest::addColumn<QString>("action");
    QTest::addColumn<QString>("argument");

    QTest::newRow("fastest") << QStringLiteral("fastest") << QString();
    QTest::newRow("disconnect") << QStringLiteral("disconnect") << QString();
    QTest::newRow("country")
        << QStringLiteral("country") << QStringLiteral("CH");
    QTest::newRow("server")
        << QStringLiteral("server") << QStringLiteral("US-CA#18");
}

void RunnerActionRequestTest::acceptsIntendedActions()
{
    QFETCH(QString, action);
    QFETCH(QString, argument);

    const auto request = ProtonVpnKde::validatedRunnerActionRequest(
        action, argument);
    QVERIFY(request.has_value());
    QCOMPARE(request->action, action);
    QCOMPARE(request->argument, argument);
}

void RunnerActionRequestTest::rejectsUnintendedOrMalformedActions_data()
{
    QTest::addColumn<QString>("action");
    QTest::addColumn<QString>("argument");

    QTest::newRow("backend method")
        << QStringLiteral("UpdateSettings") << QString();
    QTest::newRow("logout") << QStringLiteral("logout") << QString();
    QTest::newRow("fastest argument")
        << QStringLiteral("fastest") << QStringLiteral("p2p");
    QTest::newRow("disconnect argument")
        << QStringLiteral("disconnect") << QStringLiteral("now");
    QTest::newRow("lowercase country")
        << QStringLiteral("country") << QStringLiteral("ch");
    QTest::newRow("long country")
        << QStringLiteral("country") << QStringLiteral("CHE");
    QTest::newRow("server traversal")
        << QStringLiteral("server") << QStringLiteral("../US-CA#18");
    QTest::newRow("server shell syntax")
        << QStringLiteral("server") << QStringLiteral("US-CA#18;logout");
    QTest::newRow("oversized server")
        << QStringLiteral("server")
        << (QString(64, QLatin1Char('A')) + QStringLiteral("#1"));
    QTest::newRow("embedded nul")
        << QString::fromUtf8("fastest\0logout", 14) << QString();
}

void RunnerActionRequestTest::rejectsUnintendedOrMalformedActions()
{
    QFETCH(QString, action);
    QFETCH(QString, argument);

    QVERIFY(!ProtonVpnKde::validatedRunnerActionRequest(action, argument));
}

QTEST_GUILESS_MAIN(RunnerActionRequestTest)

#include "RunnerActionRequestTest.moc"
