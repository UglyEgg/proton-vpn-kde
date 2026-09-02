// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#include <QQmlComponent>
#include <QQmlContext>
#include <QQmlEngine>
#include <QScopedPointer>
#include <QStringListModel>
#include <QtTest>

namespace
{
class FakeVpnController final : public QObject
{
    Q_OBJECT
    Q_PROPERTY(bool ready MEMBER ready NOTIFY snapshotChanged)
    Q_PROPERTY(bool loggedIn MEMBER loggedIn NOTIFY snapshotChanged)
    Q_PROPERTY(bool busy MEMBER busy NOTIFY snapshotChanged)
    Q_PROPERTY(bool backendAvailable MEMBER backendAvailable NOTIFY snapshotChanged)
    Q_PROPERTY(bool primaryActionEnabled READ primaryActionEnabled NOTIFY snapshotChanged)
    Q_PROPERTY(bool backendRestartAllowed MEMBER backendRestartAllowed NOTIFY snapshotChanged)
    Q_PROPERTY(bool fido2Available MEMBER fido2Available NOTIFY snapshotChanged)
    Q_PROPERTY(int killSwitch MEMBER killSwitch NOTIFY snapshotChanged)
    Q_PROPERTY(QString authState MEMBER authState NOTIFY snapshotChanged)
    Q_PROPERTY(QString state MEMBER state NOTIFY snapshotChanged)
    Q_PROPERTY(QString errorCode MEMBER errorCode NOTIFY snapshotChanged)
    Q_PROPERTY(QString message MEMBER message NOTIFY snapshotChanged)
    Q_PROPERTY(QString snapshotError MEMBER snapshotError NOTIFY snapshotChanged)
    Q_PROPERTY(bool snapshotRestartAllowed MEMBER snapshotRestartAllowed NOTIFY snapshotChanged)
    Q_PROPERTY(bool snapshotRefreshPending MEMBER snapshotRefreshPending NOTIFY snapshotChanged)
    Q_PROPERTY(QString packetCaptureError MEMBER packetCaptureError NOTIFY snapshotChanged)
    Q_PROPERTY(bool shutdownPending MEMBER shutdownPending NOTIFY snapshotChanged)
    Q_PROPERTY(bool locationsBusy MEMBER locationsBusy NOTIFY snapshotChanged)
    Q_PROPERTY(QString serversError MEMBER serversError NOTIFY snapshotChanged)
    Q_PROPERTY(QString serverLoadsError MEMBER serverLoadsError NOTIFY snapshotChanged)
    Q_PROPERTY(QAbstractItemModel *serverModel READ serverModel CONSTANT)

public:
    bool ready = true;
    bool loggedIn = false;
    bool busy = false;
    bool backendAvailable = true;
    bool backendRestartAllowed = true;
    bool fido2Available = false;
    int killSwitch = 0;
    QString authState = QStringLiteral("signed_out");
    QString state = QStringLiteral("disconnected");
    QString errorCode;
    QString message;
    QString snapshotError;
    bool snapshotRestartAllowed = false;
    bool snapshotRefreshPending = false;
    QString packetCaptureError;
    bool shutdownPending = false;
    bool locationsBusy = false;
    QString serversError;
    QString serverLoadsError = QStringLiteral("Unable to update server loads");
    int restartCalls = 0;
    int refreshCalls = 0;
    int disconnectCalls = 0;
    QString serverFilter;
    QStringListModel emptyServerModel;

    [[nodiscard]] bool primaryActionEnabled() const
    {
        return backendAvailable && ready && loggedIn
            && (!busy || state == QStringLiteral("connecting"));
    }

    Q_INVOKABLE void restartBackend() { ++restartCalls; }
    Q_INVOKABLE void refresh() { ++refreshCalls; }
    Q_INVOKABLE void disableKillSwitchForLogin() { }
    Q_INVOKABLE void login(const QString &, const QString &) { }
    Q_INVOKABLE void submitTwoFactor(const QString &) { }
    Q_INVOKABLE void beginFido2() { }
    Q_INVOKABLE void cancelFido2() { }
    Q_INVOKABLE void submitFido2Pin(const QString &) { }
    Q_INVOKABLE void cancelLogin() { }
    Q_INVOKABLE void disconnect() { ++disconnectCalls; }
    Q_INVOKABLE void setServerFeatureFilter(const QStringList &) { }
    Q_INVOKABLE quint64 claimGroupServerContext(
        const QString &, const QString &, const QString &) { return 1; }
    Q_INVOKABLE void releaseGroupServerContext(quint64) { }
    Q_INVOKABLE void loadGroupServers(
        const QString &, const QString &, const QString &) { }
    Q_INVOKABLE void setServerFilter(const QString &filter)
    {
        serverFilter = filter;
    }
    Q_INVOKABLE void connectGroup(
        const QString &, const QString &, const QString &) { }
    Q_INVOKABLE void connectGroupWithFeatures(
        const QString &, const QString &, const QString &, const QStringList &) { }
    Q_INVOKABLE void connectServer(const QString &) { }

    [[nodiscard]] QAbstractItemModel *serverModel()
    {
        return &emptyServerModel;
    }

signals:
    void snapshotChanged();
    void connectionOperationStarted(quint64 operationId,
                                    const QString &targetState);
    void connectionOperationFinished(quint64 operationId,
                                     const QString &targetState,
                                     bool success,
                                     const QString &message);
};

class FakeAppSettings final : public QObject
{
    Q_OBJECT
    Q_PROPERTY(QStringList fastestFeatures MEMBER fastestFeatures CONSTANT)

public:
    QStringList fastestFeatures;

    Q_INVOKABLE bool isServerPinned(const QString &) const { return false; }
    Q_INVOKABLE void togglePinnedServer(const QString &) { }
};
}

class SignInPresentationTest final : public QObject
{
    Q_OBJECT

private slots:
    void signingInPreservesAuthoritativeMessage();
    void completionUnknownStopsProgress();
    void terminalIdentityFailureIsNotStartup();
    void recoveryPreservesAuthoritativeMessage_data();
    void recoveryPreservesAuthoritativeMessage();
    void applicationRecoveryIsPersistentAndActionable();
    void connectionActionFeedbackTracksOwnedResult();
    void unavailableBackendRejectsRunnerDisconnect();
    void serverEmptyStateExplainsActiveFilters_data();
    void serverEmptyStateExplainsActiveFilters();

private:
    QObject *createComponent(QQmlEngine &engine, FakeVpnController &controller,
                             const QString &fileName);
    QString m_componentErrors;
};

QObject *SignInPresentationTest::createComponent(QQmlEngine &engine,
                                                 FakeVpnController &controller,
                                                 const QString &fileName)
{
    engine.rootContext()->setContextProperty(QStringLiteral("vpnController"),
                                             &controller);
    const QString sourcePath =
        QStringLiteral(PROTON_VPN_KDE_SOURCE_DIR "/qml/") + fileName;
    QQmlComponent component(&engine, QUrl::fromLocalFile(sourcePath));
    if (component.isError())
    {
        QStringList errors;
        for (const QQmlError &error : component.errors())
        {
            errors.append(error.toString());
        }
        m_componentErrors = errors.join(QLatin1Char('\n'));
        return nullptr;
    }
    return component.create();
}

void SignInPresentationTest::signingInPreservesAuthoritativeMessage()
{
    FakeVpnController controller;
    controller.authState = QStringLiteral("signing_in");
    controller.busy = true;
    controller.message = QStringLiteral("Authentication is still completing.");
    QQmlEngine engine;
    QScopedPointer<QObject> page(
        createComponent(engine, controller, QStringLiteral("SignInPage.qml")));
    QVERIFY2(page, qPrintable(m_componentErrors));

    QCOMPARE(page->property("activeStepHeading").toString(),
             QStringLiteral("Signing in"));
    const QObject *diagnostic =
        page->findChild<QObject *>(QStringLiteral("backendStartupDiagnostic"));
    QVERIFY(diagnostic);
    QVERIFY(diagnostic->property("visible").toBool());
    QCOMPARE(diagnostic->property("text").toString(), controller.message);
    const QObject *progress =
        page->findChild<QObject *>(QStringLiteral("authenticationProgress"));
    QVERIFY(progress);
    QVERIFY(progress->property("running").toBool());
}

void SignInPresentationTest::completionUnknownStopsProgress()
{
    FakeVpnController controller;
    controller.authState = QStringLiteral("signing_in");
    controller.busy = false;
    controller.message = QStringLiteral(
        "Authentication is still completing; refreshing its state.");
    QQmlEngine engine;
    QScopedPointer<QObject> page(
        createComponent(engine, controller, QStringLiteral("SignInPage.qml")));
    QVERIFY2(page, qPrintable(m_componentErrors));

    const QObject *diagnostic =
        page->findChild<QObject *>(QStringLiteral("backendStartupDiagnostic"));
    QVERIFY(diagnostic);
    QVERIFY(diagnostic->property("visible").toBool());
    QCOMPARE(diagnostic->property("text").toString(), controller.message);
    const QObject *progress =
        page->findChild<QObject *>(QStringLiteral("authenticationProgress"));
    QVERIFY(progress);
    QVERIFY(!progress->property("running").toBool());
}

void SignInPresentationTest::terminalIdentityFailureIsNotStartup()
{
    FakeVpnController controller;
    controller.ready = false;
    controller.backendAvailable = false;
    controller.backendRestartAllowed = false;
    controller.message = QStringLiteral(
        "Close and reopen the application after reinstalling it.");
    QQmlEngine engine;
    QScopedPointer<QObject> page(
        createComponent(engine, controller, QStringLiteral("SignInPage.qml")));
    QVERIFY2(page, qPrintable(m_componentErrors));

    QCOMPARE(page->property("activeStepHeading").toString(),
             QStringLiteral("Sign-in unavailable"));
    QCOMPARE(page->property("activeStepDescription").toString(),
             controller.message);
    QVERIFY(page->property("terminalBackendFailure").toBool());
    const QObject *progress = page->findChild<QObject *>(
        QStringLiteral("backendPreparationProgress"));
    QVERIFY(progress);
    QVERIFY(!progress->property("running").toBool());
}

void SignInPresentationTest::recoveryPreservesAuthoritativeMessage_data()
{
    QTest::addColumn<QString>("authState");
    QTest::newRow("authentication-unknown")
        << QStringLiteral("authentication_unknown");
    QTest::newRow("settings-unavailable")
        << QStringLiteral("settings_unavailable");
    QTest::newRow("protection-unknown") << QStringLiteral("protection_unknown");
}

void SignInPresentationTest::recoveryPreservesAuthoritativeMessage()
{
    QFETCH(QString, authState);
    FakeVpnController controller;
    controller.authState = authState;
    controller.message =
        QStringLiteral("Exact recovery guidance for %1").arg(authState);
    QQmlEngine engine;
    QScopedPointer<QObject> page(
        createComponent(engine, controller, QStringLiteral("SignInPage.qml")));
    QVERIFY2(page, qPrintable(m_componentErrors));

    QCOMPARE(page->property("activeStepHeading").toString(),
             QStringLiteral("Account state unavailable"));
    QCOMPARE(page->property("activeStepDescription").toString(),
             controller.message);
}

void SignInPresentationTest::applicationRecoveryIsPersistentAndActionable()
{
    FakeVpnController controller;
    controller.loggedIn = true;
    controller.state = QStringLiteral("unresponsive");
    controller.backendRestartAllowed = true;
    controller.message = QStringLiteral("Restart the local service.");
    QQmlEngine engine;
    const QString sourcePath = QStringLiteral(
        PROTON_VPN_KDE_SOURCE_DIR "/qml/ApplicationRecoveryBanner.qml");
    QQmlComponent component(&engine, QUrl::fromLocalFile(sourcePath));
    const QVariantList dialogErrorCodes{
        QStringLiteral("maximum_sessions_reached"),
        QStringLiteral("authentication_denied"),
        QStringLiteral("two_factor_required"),
        QStringLiteral("certificate_not_yet_valid")};
    const QVariantMap initialProperties{
        {QStringLiteral("vpnController"),
         QVariant::fromValue(static_cast<QObject *>(&controller))},
        {QStringLiteral("dialogErrorCodes"), dialogErrorCodes}};
    QScopedPointer<QObject> banner(
        component.createWithInitialProperties(initialProperties));
    if (!banner)
    {
        QStringList errors;
        for (const QQmlError &error : component.errors())
        {
            errors.append(error.toString());
        }
        QFAIL(qPrintable(errors.join(QLatin1Char('\n'))));
    }

    QVERIFY(banner->property("recoveryActive").toBool());
    QCOMPARE(banner->property("text").toString(), controller.message);
    QVERIFY(QMetaObject::invokeMethod(banner.data(), "requestRestart"));
    QCOMPARE(controller.restartCalls, 1);

    controller.state = QStringLiteral("error");
    controller.errorCode = QStringLiteral("tunnel_setup_failed");
    controller.message = QStringLiteral("Core rejected the tunnel setup.");
    emit controller.snapshotChanged();
    QCoreApplication::processEvents();
    QVERIFY(!banner->property("recoveryActive").toBool());
    QVERIFY(banner->property("connectionErrorActive").toBool());
    QVERIFY(banner->property("text").toString().contains(controller.message));

    controller.errorCode = QStringLiteral("authentication_denied");
    emit controller.snapshotChanged();
    QCoreApplication::processEvents();
    QVERIFY(!banner->property("connectionErrorActive").toBool());

    controller.state = QStringLiteral("disconnected");
    controller.errorCode.clear();
    emit controller.snapshotChanged();
    QCoreApplication::processEvents();
    QVERIFY(!banner->property("recoveryActive").toBool());
    QVERIFY(!banner->property("bannerActive").toBool());
    QCOMPARE(banner->property("height").toReal(), 0.0);

    controller.snapshotError = QStringLiteral(
        "The backend returned an incomplete state snapshot");
    controller.snapshotRestartAllowed = true;
    emit controller.snapshotChanged();
    QCoreApplication::processEvents();
    QVERIFY(banner->property("snapshotErrorActive").toBool());
    QCOMPARE(banner->property("text").toString(), controller.snapshotError);
    const QObject *refreshAction = banner->findChild<QObject *>(
        QStringLiteral("refreshInvalidSnapshotAction"));
    QVERIFY(refreshAction);
    QVERIFY(refreshAction->property("visible").toBool());
    QVERIFY(refreshAction->property("enabled").toBool());
    const QObject *restartAction = banner->findChild<QObject *>(
        QStringLiteral("restartUnresponsiveBackendAction"));
    QVERIFY(restartAction);
    QVERIFY(restartAction->property("visible").toBool());
    QVERIFY(QMetaObject::invokeMethod(banner.data(), "requestSnapshotRefresh"));
    QCOMPARE(controller.refreshCalls, 1);

    controller.snapshotRefreshPending = true;
    emit controller.snapshotChanged();
    QCoreApplication::processEvents();
    QVERIFY(!refreshAction->property("enabled").toBool());

    controller.snapshotRestartAllowed = false;
    emit controller.snapshotChanged();
    QCoreApplication::processEvents();
    QVERIFY(!restartAction->property("visible").toBool());

    controller.snapshotError.clear();
    controller.snapshotRestartAllowed = false;
    controller.snapshotRefreshPending = false;
    controller.packetCaptureError = QStringLiteral(
        "The packet capture could not be stopped");
    emit controller.snapshotChanged();
    QCoreApplication::processEvents();
    QVERIFY(!banner->property("snapshotErrorActive").toBool());
    QVERIFY(banner->property("packetCaptureErrorActive").toBool());
    QCOMPARE(banner->property("text").toString(),
             controller.packetCaptureError);

    banner->setProperty("showPacketCaptureError", false);
    QCoreApplication::processEvents();
    QVERIFY(!banner->property("packetCaptureErrorActive").toBool());
    QVERIFY(!banner->property("bannerActive").toBool());

    controller.packetCaptureError.clear();
    controller.shutdownPending = true;
    emit controller.snapshotChanged();
    QCoreApplication::processEvents();
    QVERIFY(banner->property("shutdownActive").toBool());
    QVERIFY(banner->property("bannerActive").toBool());
    QVERIFY(banner->property("text").toString().contains(
        QStringLiteral("capture"), Qt::CaseInsensitive));
}

void SignInPresentationTest::connectionActionFeedbackTracksOwnedResult()
{
    FakeVpnController controller;
    controller.loggedIn = true;
    QQmlEngine engine;
    const QString sourcePath = QStringLiteral(
        PROTON_VPN_KDE_SOURCE_DIR "/qml/ConnectionActionFeedback.qml");
    QQmlComponent component(&engine, QUrl::fromLocalFile(sourcePath));
    const QVariantMap initialProperties{
        {QStringLiteral("controller"),
         QVariant::fromValue(static_cast<QObject *>(&controller))}};
    QScopedPointer<QObject> feedback(
        component.createWithInitialProperties(initialProperties));
    if (!feedback)
    {
        QStringList errors;
        for (const QQmlError &error : component.errors())
        {
            errors.append(error.toString());
        }
        QFAIL(qPrintable(errors.join(QLatin1Char('\n'))));
    }

    const QVariant expectedState = QStringLiteral("connected");
    quint64 operationId = 1;
    emit controller.connectionOperationStarted(
        operationId, expectedState.toString());
    QCoreApplication::processEvents();
    controller.message =
        QStringLiteral("No server available in the current tier");
    emit controller.snapshotChanged();
    emit controller.connectionOperationFinished(
        operationId, QStringLiteral("connected"), false, controller.message);
    QCoreApplication::processEvents();
    QVERIFY(feedback->property("messageActive").toBool());
    QCOMPARE(feedback->property("completedMessage").toString(),
             controller.message);

    emit controller.connectionOperationStarted(
        ++operationId, expectedState.toString());
    QCoreApplication::processEvents();
    QVERIFY(!feedback->property("messageActive").toBool());
    controller.message.clear();
    emit controller.connectionOperationFinished(
        operationId, QStringLiteral("connected"), true, {});
    QCoreApplication::processEvents();
    QVERIFY(!feedback->property("awaitingResult").toBool());
    QVERIFY(!feedback->property("messageActive").toBool());

    const quint64 supersededOperation = ++operationId;
    emit controller.connectionOperationStarted(
        supersededOperation, expectedState.toString());
    emit controller.connectionOperationStarted(
        ++operationId, expectedState.toString());
    emit controller.connectionOperationFinished(
        supersededOperation,
        QStringLiteral("connected"),
        false,
        QStringLiteral("An older connection attempt failed"));
    QCoreApplication::processEvents();
    QVERIFY(feedback->property("awaitingResult").toBool());
    QVERIFY(!feedback->property("messageActive").toBool());
    controller.message = QStringLiteral("The current connection attempt failed");
    emit controller.connectionOperationFinished(
        operationId, QStringLiteral("connected"), false, controller.message);
    QCoreApplication::processEvents();
    QVERIFY(feedback->property("messageActive").toBool());
    QCOMPARE(feedback->property("completedMessage").toString(),
             controller.message);

    controller.state = QStringLiteral("connected");
    emit controller.connectionOperationStarted(
        ++operationId, expectedState.toString());
    QCoreApplication::processEvents();
    controller.message = QStringLiteral("Unable to switch VPN servers");
    emit controller.snapshotChanged();
    emit controller.connectionOperationFinished(
        operationId, QStringLiteral("connected"), false, controller.message);
    QCoreApplication::processEvents();
    QVERIFY(feedback->property("messageActive").toBool());
    QCOMPARE(feedback->property("completedMessage").toString(),
             controller.message);

    const QVariant disconnectedState = QStringLiteral("disconnected");
    emit controller.connectionOperationStarted(
        ++operationId, disconnectedState.toString());
    QCoreApplication::processEvents();
    controller.message = QStringLiteral("The VPN could not be disconnected");
    emit controller.snapshotChanged();
    emit controller.connectionOperationFinished(
        operationId - 1, QStringLiteral("connected"), false,
        QStringLiteral("An older server switch failed"));
    QCoreApplication::processEvents();
    QVERIFY(feedback->property("awaitingResult").toBool());
    QVERIFY(!feedback->property("messageActive").toBool());
    emit controller.connectionOperationFinished(
        operationId, QStringLiteral("disconnected"), false, controller.message);
    QCoreApplication::processEvents();
    QVERIFY(feedback->property("messageActive").toBool());
    QCOMPARE(feedback->property("completedMessage").toString(),
             controller.message);

    controller.state = QStringLiteral("error");
    emit controller.snapshotChanged();
    QCoreApplication::processEvents();
    QVERIFY(!feedback->property("messageActive").toBool());

    controller.state = QStringLiteral("connected");
    emit controller.connectionOperationStarted(
        ++operationId, disconnectedState.toString());
    QCoreApplication::processEvents();
    emit controller.connectionOperationFinished(
        operationId, QStringLiteral("disconnected"), false, controller.message);
    QCoreApplication::processEvents();
    QVERIFY(feedback->property("messageActive").toBool());
    QCOMPARE(feedback->property("completedMessage").toString(),
             controller.message);

    emit controller.connectionOperationStarted(
        ++operationId, disconnectedState.toString());
    QCoreApplication::processEvents();
    controller.backendAvailable = false;
    emit controller.snapshotChanged();
    QCoreApplication::processEvents();
    QVERIFY(!feedback->property("awaitingResult").toBool());
    QVERIFY(!feedback->property("messageActive").toBool());

    controller.backendAvailable = true;
    controller.loggedIn = true;
    emit controller.connectionOperationStarted(
        ++operationId, expectedState.toString());
    QCoreApplication::processEvents();
    controller.loggedIn = false;
    emit controller.snapshotChanged();
    QCoreApplication::processEvents();
    QVERIFY(!feedback->property("awaitingResult").toBool());
    QVERIFY(!feedback->property("messageActive").toBool());
}

void SignInPresentationTest::unavailableBackendRejectsRunnerDisconnect()
{
    FakeVpnController controller;
    controller.backendAvailable = false;
    controller.ready = true;
    controller.loggedIn = true;
    controller.state = QStringLiteral("connected");
    FakeAppSettings appSettings;
    QQmlEngine engine;
    const QString sourcePath = QStringLiteral(
        PROTON_VPN_KDE_SOURCE_DIR "/qml/MainDialogs.qml");
    QQmlComponent component(&engine, QUrl::fromLocalFile(sourcePath));
    const QVariantMap initialProperties{
        {QStringLiteral("vpnController"),
         QVariant::fromValue(static_cast<QObject *>(&controller))},
        {QStringLiteral("appSettings"),
         QVariant::fromValue(static_cast<QObject *>(&appSettings))},
        {QStringLiteral("windowWidth"), 800.0}};
    QScopedPointer<QObject> dialogs(
        component.createWithInitialProperties(initialProperties));
    if (!dialogs)
    {
        QStringList errors;
        for (const QQmlError &error : component.errors())
        {
            errors.append(error.toString());
        }
        QFAIL(qPrintable(errors.join(QLatin1Char('\n'))));
    }

    const QVariant action = QStringLiteral("disconnect");
    const QVariant argument = QString{};
    QVERIFY(QMetaObject::invokeMethod(
        dialogs.data(), "requestRunnerAction",
        Q_ARG(QVariant, action), Q_ARG(QVariant, argument)));
    QCoreApplication::processEvents();
    QVERIFY(!dialogs->property("runnerActionEnabled").toBool());
    QVERIFY(QMetaObject::invokeMethod(dialogs.data(), "acceptRunnerAction"));
    QCoreApplication::processEvents();
    QCOMPARE(controller.disconnectCalls, 0);
}

void SignInPresentationTest::serverEmptyStateExplainsActiveFilters_data()
{
    QTest::addColumn<QString>("filter");
    QTest::addColumn<QStringList>("capabilities");
    QTest::addColumn<QString>("expectedMessage");

    QTest::newRow("authoritative-empty")
        << QString{} << QStringList{}
        << QStringLiteral("No servers available");
    QTest::newRow("capability-empty")
        << QString{} << QStringList{QStringLiteral("p2p")}
        << QStringLiteral("No servers match the selected capabilities");
    QTest::newRow("search-empty")
        << QStringLiteral("no-such-server") << QStringList{}
        << QStringLiteral("No servers match your search");
    QTest::newRow("combined-empty")
        << QStringLiteral("no-such-server")
        << QStringList{QStringLiteral("p2p")}
        << QStringLiteral(
               "No servers match your search and selected capabilities");
}

void SignInPresentationTest::serverEmptyStateExplainsActiveFilters()
{
    QFETCH(QString, filter);
    QFETCH(QStringList, capabilities);
    QFETCH(QString, expectedMessage);

    FakeVpnController controller;
    controller.loggedIn = true;
    FakeAppSettings appSettings;
    QQmlEngine engine;
    engine.rootContext()->setContextProperty(
        QStringLiteral("vpnController"), &controller);
    engine.rootContext()->setContextProperty(
        QStringLiteral("appSettings"), &appSettings);
    engine.rootContext()->setContextProperty(
        QStringLiteral("testFilter"), filter);
    engine.rootContext()->setContextProperty(
        QStringLiteral("testCapabilities"), capabilities);

    static const QByteArray harness = R"qml(
import QtQuick
import org.kde.kirigami as Kirigami
import "." as Local

Kirigami.ApplicationWindow {
    visible: false
    width: 640
    height: 720
    property bool browserConnectionActionEnabled: true
    function beginConnectionAction(expectedState) { }

    Local.ServersPage {
        objectName: "serverPage"
        anchors.fill: parent
        countryCode: "CH"
        countryName: "Switzerland"
        countryFlag: "CH"
        groupKind: "location"
        groupName: "Zurich"
        groupAccessible: true
        groupUnderMaintenance: false
        initialServerFilter: testFilter
        requiredCapabilities: testCapabilities
    }
}
)qml";
    const QUrl harnessUrl = QUrl::fromLocalFile(QStringLiteral(
        PROTON_VPN_KDE_SOURCE_DIR "/qml/ServerEmptyStateHarness.qml"));
    QQmlComponent component(&engine);
    component.setData(harness, harnessUrl);
    QScopedPointer<QObject> window(component.create());
    if (!window)
    {
        QStringList errors;
        for (const QQmlError &error : component.errors())
        {
            errors.append(error.toString());
        }
        QFAIL(qPrintable(errors.join(QLatin1Char('\n'))));
    }
    QCoreApplication::processEvents();

    const QObject *page =
        window->findChild<QObject *>(QStringLiteral("serverPage"));
    QVERIFY(page);
    const QObject *placeholder =
        window->findChild<QObject *>(QStringLiteral("serverEmptyState"));
    QVERIFY(placeholder);
    QVERIFY(placeholder->property("visible").toBool());
    QCOMPARE(placeholder->property("text").toString(), expectedMessage);
    QCOMPARE(page->property("serverBrowserError").toString(),
             controller.serverLoadsError);
    QCOMPARE(controller.serverFilter, filter);
}

QTEST_MAIN(SignInPresentationTest)

#include "SignInPresentationTest.moc"
