// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#include "BackgroundQuitCoordinator.h"
#include "VpnConnectionController.h"

#include <QSignalSpy>
#include <QtTest>

namespace
{
class FakeVpnController final : public VpnConnectionController
{
    Q_OBJECT

public:
    bool backendAvailable() const override { return backend; }
    bool ready() const override { return true; }
    bool loggedIn() const override { return true; }
    bool busy() const override { return operationBusy; }
    int killSwitch() const override { return 0; }
    QString state() const override { return connectionState; }
    QString serverName() const override { return {}; }
    int forwardedPort() const override { return 0; }
    QString message() const override { return {}; }
    QString primaryActionText() const override { return {}; }
    ProtonVpnKde::ConnectionActionCapabilities connectionCapabilities() const override
    {
        return ProtonVpnKde::connectionActionCapabilities(
            backend, true, healthy, true, operationBusy, connectionState, u"signed_in");
    }

    void activatePrimaryAction() override {}
    void connectTarget(const QString &) override {}
    void connectGroup(const QString &, const QString &, const QString &) override {}
    void disconnect() override { ++disconnectCalls; }

    void publish(const QString &state, bool busy = false)
    {
        connectionState = state;
        operationBusy = busy;
        emit snapshotChanged();
    }

    bool backend = true;
    bool healthy = true;
    bool operationBusy = false;
    int disconnectCalls = 0;
    QString connectionState = QStringLiteral("connected");
};
}

class BackgroundQuitCoordinatorTest final : public QObject
{
    Q_OBJECT

private slots:
    void waitsForConfirmedDisconnectBeforeQuitting();
    void waitsForDisconnectAlreadyInProgress();
    void quitsImmediatelyWhenAlreadyDisconnected();
    void initialDisconnectedStillRequiresAnIdleAvailableBackend();
    void unreadableStateCannotConfirmDisconnect_data();
    void unreadableStateCannotConfirmDisconnect();
    void keepsControlsAliveWhenDisconnectTimesOut();
};

void BackgroundQuitCoordinatorTest::waitsForConfirmedDisconnectBeforeQuitting()
{
    FakeVpnController controller;
    BackgroundQuitCoordinator coordinator(&controller, 1000);
    QSignalSpy readySpy(&coordinator, &BackgroundQuitCoordinator::readyToQuit);

    coordinator.disconnectAndQuit();
    QCOMPARE(controller.disconnectCalls, 1);
    QVERIFY(coordinator.pending());
    QCOMPARE(readySpy.count(), 0);

    controller.publish(QStringLiteral("disconnected"), true);
    QCOMPARE(readySpy.count(), 0);
    QVERIFY(coordinator.pending());

    controller.publish(QStringLiteral("disconnected"), false);
    QCOMPARE(readySpy.count(), 1);
    QVERIFY(!coordinator.pending());
}

void BackgroundQuitCoordinatorTest::waitsForDisconnectAlreadyInProgress()
{
    FakeVpnController controller;
    controller.connectionState = QStringLiteral("disconnecting");
    controller.operationBusy = true;
    BackgroundQuitCoordinator coordinator(&controller, 1000);
    QSignalSpy readySpy(&coordinator, &BackgroundQuitCoordinator::readyToQuit);

    coordinator.disconnectAndQuit();

    QCOMPARE(controller.disconnectCalls, 0);
    QVERIFY(coordinator.pending());
    controller.publish(QStringLiteral("disconnected"), false);
    QCOMPARE(readySpy.count(), 1);
    QVERIFY(!coordinator.pending());
}

void BackgroundQuitCoordinatorTest::quitsImmediatelyWhenAlreadyDisconnected()
{
    FakeVpnController controller;
    controller.connectionState = QStringLiteral("disconnected");
    BackgroundQuitCoordinator coordinator(&controller, 1000);
    QSignalSpy readySpy(&coordinator, &BackgroundQuitCoordinator::readyToQuit);

    coordinator.disconnectAndQuit();

    QCOMPARE(controller.disconnectCalls, 0);
    QCOMPARE(readySpy.count(), 1);
    QVERIFY(!coordinator.pending());
}

void BackgroundQuitCoordinatorTest::keepsControlsAliveWhenDisconnectTimesOut()
{
    FakeVpnController controller;
    BackgroundQuitCoordinator coordinator(&controller, 1);
    QSignalSpy readySpy(&coordinator, &BackgroundQuitCoordinator::readyToQuit);
    QSignalSpy timeoutSpy(
        &coordinator, &BackgroundQuitCoordinator::disconnectTimedOut);

    coordinator.disconnectAndQuit();

    QTRY_COMPARE_WITH_TIMEOUT(timeoutSpy.count(), 1, 1000);
    QCOMPARE(readySpy.count(), 0);
    QVERIFY(!coordinator.pending());
}

void BackgroundQuitCoordinatorTest::initialDisconnectedStillRequiresAnIdleAvailableBackend()
{
    for (const bool backendAvailable : {false, true}) {
        FakeVpnController controller;
        controller.connectionState = QStringLiteral("disconnected");
        controller.backend = backendAvailable;
        controller.operationBusy = backendAvailable;
        BackgroundQuitCoordinator coordinator(&controller, 1000);
        QSignalSpy readySpy(&coordinator, &BackgroundQuitCoordinator::readyToQuit);

        coordinator.disconnectAndQuit();

        QCOMPARE(readySpy.count(), 0);
        QVERIFY(coordinator.pending());
        controller.backend = true;
        controller.publish(QStringLiteral("disconnected"), false);
        QCOMPARE(readySpy.count(), 1);
    }
}

void BackgroundQuitCoordinatorTest::unreadableStateCannotConfirmDisconnect_data()
{
    QTest::addColumn<bool>("initiallyUnreadable");
    QTest::newRow("unreadable-on-entry") << true;
    QTest::newRow("unreadable-while-waiting") << false;
}

void BackgroundQuitCoordinatorTest::unreadableStateCannotConfirmDisconnect()
{
    QFETCH(bool, initiallyUnreadable);
    FakeVpnController controller;
    if (initiallyUnreadable) {
        controller.connectionState = QStringLiteral("disconnected");
        controller.healthy = false;
    }
    BackgroundQuitCoordinator coordinator(&controller, 1000);
    QSignalSpy readySpy(&coordinator, &BackgroundQuitCoordinator::readyToQuit);
    coordinator.disconnectAndQuit();
    QCOMPARE(readySpy.count(), 0);
    QVERIFY(coordinator.pending());

    controller.healthy = false;
    controller.publish(QStringLiteral("disconnected"));
    QCOMPARE(readySpy.count(), 0);
    QVERIFY(coordinator.pending());

    controller.healthy = true;
    controller.publish(QStringLiteral("disconnected"));
    QCOMPARE(readySpy.count(), 1);
    QVERIFY(!coordinator.pending());
}

QTEST_MAIN(BackgroundQuitCoordinatorTest)

#include "BackgroundQuitCoordinatorTest.moc"
