#include "AppLifecycle.h"

#include <QSignalSpy>
#include <QTest>

class AppLifecycleTest final : public QObject
{
    Q_OBJECT

private slots:
    void quitsImmediatelyWhenDisconnected();
    void confirmsAndWaitsForDisconnect();
    void quitsWhenBackendCannotDisconnect();
    void cancellationLeavesTheAppRunning();
    void ignoresDuplicateQuitRequests();
};

void AppLifecycleTest::quitsImmediatelyWhenDisconnected()
{
    AppLifecycle lifecycle;
    QSignalSpy quitReady(&lifecycle, &AppLifecycle::quitReady);
    QSignalSpy confirmation(&lifecycle,
                            &AppLifecycle::quitConfirmationRequested);

    lifecycle.requestQuit(QStringLiteral("disconnected"), true);

    QCOMPARE(quitReady.count(), 1);
    QCOMPARE(confirmation.count(), 0);
    QVERIFY(!lifecycle.quitPending());
}

void AppLifecycleTest::confirmsAndWaitsForDisconnect()
{
    AppLifecycle lifecycle;
    QSignalSpy confirmation(&lifecycle,
                            &AppLifecycle::quitConfirmationRequested);
    QSignalSpy disconnect(&lifecycle, &AppLifecycle::disconnectRequested);
    QSignalSpy quitReady(&lifecycle, &AppLifecycle::quitReady);

    lifecycle.requestQuit(QStringLiteral("connected"), true);
    QCOMPARE(confirmation.count(), 1);
    lifecycle.confirmQuit();
    QCOMPARE(disconnect.count(), 1);
    QVERIFY(lifecycle.quitPending());
    QCOMPARE(quitReady.count(), 0);

    lifecycle.observeConnectionState(QStringLiteral("disconnecting"));
    QCOMPARE(quitReady.count(), 0);
    lifecycle.observeConnectionState(QStringLiteral("disconnected"));
    QCOMPARE(quitReady.count(), 1);
    QVERIFY(!lifecycle.quitPending());
}

void AppLifecycleTest::quitsWhenBackendCannotDisconnect()
{
    AppLifecycle lifecycle;
    QSignalSpy confirmation(&lifecycle,
                            &AppLifecycle::quitConfirmationRequested);
    QSignalSpy quitReady(&lifecycle, &AppLifecycle::quitReady);

    lifecycle.requestQuit(QStringLiteral("unavailable"), false);

    QCOMPARE(confirmation.count(), 0);
    QCOMPARE(quitReady.count(), 1);
}

void AppLifecycleTest::cancellationLeavesTheAppRunning()
{
    AppLifecycle lifecycle;
    QSignalSpy disconnect(&lifecycle, &AppLifecycle::disconnectRequested);
    QSignalSpy quitReady(&lifecycle, &AppLifecycle::quitReady);

    lifecycle.requestQuit(QStringLiteral("connected"), true);
    lifecycle.cancelQuit();
    lifecycle.confirmQuit();
    lifecycle.observeConnectionState(QStringLiteral("disconnected"));

    QCOMPARE(disconnect.count(), 0);
    QCOMPARE(quitReady.count(), 0);
}

void AppLifecycleTest::ignoresDuplicateQuitRequests()
{
    AppLifecycle lifecycle;
    QSignalSpy confirmation(&lifecycle,
                            &AppLifecycle::quitConfirmationRequested);
    QSignalSpy disconnect(&lifecycle, &AppLifecycle::disconnectRequested);

    lifecycle.requestQuit(QStringLiteral("connected"), true);
    lifecycle.requestQuit(QStringLiteral("connected"), true);
    lifecycle.confirmQuit();
    lifecycle.requestQuit(QStringLiteral("disconnecting"), true);

    QCOMPARE(confirmation.count(), 1);
    QCOMPARE(disconnect.count(), 1);
}

QTEST_GUILESS_MAIN(AppLifecycleTest)

#include "AppLifecycleTest.moc"
