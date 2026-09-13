// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#include "AppSettings.h"
#include "NotificationIntegration.h"
#include "VpnConnectionController.h"

#include <QTemporaryDir>
#include <QtTest>

namespace
{
class ObservedController final : public VpnConnectionController
{
public:
    bool available = true;
    bool healthy = true;
    QString observedState = QStringLiteral("connected");
    bool backendAvailable() const override { return available; }
    bool ready() const override { return healthy; }
    bool loggedIn() const override { return true; }
    bool busy() const override { return false; }
    int killSwitch() const override { return 0; }
    QString state() const override { return observedState; }
    QString serverName() const override { return {}; }
    int forwardedPort() const override { return 0; }
    QString message() const override { return {}; }
    QString primaryActionText() const override { return {}; }
    ProtonVpnKde::ConnectionActionCapabilities connectionCapabilities() const override { return {}; }
    void activatePrimaryAction() override {}
    void connectTarget(const QString &) override {}
    void connectGroup(const QString &, const QString &, const QString &) override {}
    void disconnect() override {}
};
}

class NotificationIntegrationTest final : public QObject
{
    Q_OBJECT
private slots:
    void observationGapsResetTheNotificationBaseline()
    {
        QTemporaryDir directory;
        qputenv("XDG_CONFIG_HOME", directory.path().toUtf8());
        AppSettings settings;
        settings.setNotificationsEnabled(false); // Never contact desktop notifications.
        ObservedController controller;
        NotificationIntegration notifications(&controller, &settings);
        QVERIFY(notifications.m_initialized);
        for (const bool lossOfOwner : {false, true}) {
            controller.available = !lossOfOwner;
            controller.healthy = lossOfOwner;
            controller.observedState = QStringLiteral("unavailable");
            emit controller.snapshotChanged();
            QVERIFY(!notifications.m_initialized);
            // Recovery to either state establishes a baseline, not an event.
            for (const QString &state : {QStringLiteral("connected"), QStringLiteral("disconnected")}) {
                controller.available = true;
                controller.healthy = true;
                controller.observedState = state;
                emit controller.snapshotChanged();
                QVERIFY(notifications.m_initialized);
                QCOMPARE(notifications.m_previousState, state);
                controller.healthy = false;
                emit controller.snapshotChanged();
                QVERIFY(!notifications.m_initialized);
            }
        }
    }
};

QTEST_GUILESS_MAIN(NotificationIntegrationTest)
#include "NotificationIntegrationTest.moc"
