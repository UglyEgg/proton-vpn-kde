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
    bool primaryActionEnabled() const override { return true; }

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

QTEST_MAIN(BackgroundQuitCoordinatorTest)

#include "BackgroundQuitCoordinatorTest.moc"
