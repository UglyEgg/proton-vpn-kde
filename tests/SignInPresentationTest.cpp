// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#include <QQmlComponent>
#include <QJsonDocument>
#include <QJsonObject>
#include <QQmlContext>
#include <QQmlEngine>
#include <QQmlNetworkAccessManagerFactory>
#include <QNetworkAccessManager>
#include <QNetworkReply>
#include <QQuickItem>
#include <QQuickWindow>
#include <QTimer>
#include <atomic>
#include <QScopedPointer>
#include <QStringListModel>
#include <QtTest>
#include "ConnectionAction.h"
#include "RunnerActionRequest.h"

namespace
{
class DeniedReply final : public QNetworkReply
{
public:
    DeniedReply(const QNetworkRequest &request, QObject *parent) : QNetworkReply(parent)
    {
        setRequest(request);
        setUrl(request.url());
        open(QIODevice::ReadOnly);
        setError(QNetworkReply::ContentAccessDenied, QStringLiteral("No test network I/O"));
        setFinished(true);
        QTimer::singleShot(0, this, [this] { emit finished(); });
    }
    void abort() override { }
protected:
    qint64 readData(char *, qint64) override { return -1; }
};

class DenyingNetworkFactory final : public QQmlNetworkAccessManagerFactory
{
public:
    std::atomic_int requests = 0;
    QNetworkAccessManager *create(QObject *parent) override
    {
        class Manager final : public QNetworkAccessManager
        {
        public:
            Manager(std::atomic_int &count, QObject *owner)
                : QNetworkAccessManager(owner), m_count(count) { }
        protected:
            QNetworkReply *createRequest(Operation, const QNetworkRequest &request,
                                         QIODevice *) override
            {
                ++m_count;
                return new DeniedReply(request, this); // Never call the network implementation.
            }
        private:
            std::atomic_int &m_count;
        };
        return new Manager(requests, parent);
    }
};

class FakeVpnController final : public QObject
{
    Q_OBJECT
    Q_PROPERTY(bool ready MEMBER ready NOTIFY snapshotChanged)
    Q_PROPERTY(bool loggedIn MEMBER loggedIn NOTIFY snapshotChanged)
    Q_PROPERTY(bool busy MEMBER busy NOTIFY snapshotChanged)
    Q_PROPERTY(bool backendAvailable MEMBER backendAvailable NOTIFY snapshotChanged)
    Q_PROPERTY(bool primaryActionEnabled READ primaryActionEnabled NOTIFY snapshotChanged)
    Q_PROPERTY(bool canConnect READ canConnect NOTIFY snapshotChanged)
    Q_PROPERTY(bool canDisconnect READ canDisconnect NOTIFY snapshotChanged)
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
    Q_PROPERTY(bool packetCaptureActive MEMBER packetCaptureActive NOTIFY snapshotChanged)
    Q_PROPERTY(bool crashReportSubmissionEnabled MEMBER crashReportSubmissionEnabled CONSTANT)
    Q_PROPERTY(bool telemetryBuildEnabled MEMBER telemetryBuildEnabled CONSTANT)
    Q_PROPERTY(bool shutdownPending MEMBER shutdownPending NOTIFY snapshotChanged)
    Q_PROPERTY(bool npsSurveySubmissionPending MEMBER npsSurveySubmissionPending NOTIFY snapshotChanged)
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
    bool packetCaptureActive = false;
    bool crashReportSubmissionEnabled = false;
    bool telemetryBuildEnabled = false;
    int captureStartCalls = 0;
    int captureStopCalls = 0;
    bool shutdownPending = false;
    bool npsSurveySubmissionPending = false;
    bool locationsBusy = false;
    QString serversError;
    QString serverLoadsError = QStringLiteral("Unable to update server loads");
    int restartCalls = 0;
    int refreshCalls = 0;
    int disconnectCalls = 0;
    int connectCalls = 0;
    QStringList connectedGroup;
    QString serverFilter;
    QStringListModel emptyServerModel;
    QString lastSetting;
    QVariant lastSettingValue;
    int settingsUpdateCalls = 0;

    [[nodiscard]] bool primaryActionEnabled() const
    {
        const auto capability = capabilities();
        return capability.primaryDisconnects ? capability.disconnect : capability.connect;
    }
    [[nodiscard]] bool canConnect() const { return capabilities().connect; }
    [[nodiscard]] bool canDisconnect() const { return capabilities().disconnect; }
    [[nodiscard]] ProtonVpnKde::ConnectionActionCapabilities capabilities() const
    {
        return ProtonVpnKde::connectionActionCapabilities(
            backendAvailable, ready, snapshotError.isEmpty(), loggedIn, busy, state, authState);
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
    Q_INVOKABLE void stopPacketCapture() { ++captureStopCalls; }
    Q_INVOKABLE void startPacketCapture(const QString &) { ++captureStartCalls; }
    Q_INVOKABLE void connectCountry(const QString &) { ++connectCalls; }
    Q_INVOKABLE void connectFastestWithFeatures(const QStringList &) { ++connectCalls; }
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
        const QString &country, const QString &kind, const QString &name)
    {
        ++connectCalls;
        connectedGroup = {country, kind, name};
    }
    Q_INVOKABLE void connectGroupWithFeatures(
        const QString &, const QString &, const QString &, const QStringList &) { }
    Q_INVOKABLE void connectServer(const QString &) { ++connectCalls; }
    Q_INVOKABLE void updateSetting(const QString &name, const QVariant &value)
    {
        ++settingsUpdateCalls;
        lastSetting = name;
        lastSettingValue = value;
    }

    [[nodiscard]] QAbstractItemModel *serverModel()
    {
        return &emptyServerModel;
    }

signals:
    void snapshotChanged();
    void npsSurveySubmissionFinished(bool success, const QString &message);
    void connectionOperationStarted(quint64 operationId,
                                    const QString &targetState);
    void connectionOperationFinished(quint64 operationId,
                                     const QString &targetState,
                                     bool acknowledged,
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
    void connectorStartupFailureIsNotSignIn();
    void terminalIdentityFailureIsNotStartup();
    void recoveryPreservesAuthoritativeMessage_data();
    void recoveryPreservesAuthoritativeMessage();
    void applicationRecoveryIsPersistentAndActionable();
    void connectionActionFeedbackTracksOwnedResult();
    void connectionFeedbackCannotInferAcknowledgement_data();
    void connectionFeedbackCannotInferAcknowledgement();
    void runnerActionsUseCurrentIntentPermission_data();
    void runnerActionsUseCurrentIntentPermission();
    void runnerNamesAreLiteralWithoutResourceLoading_data();
    void runnerNamesAreLiteralWithoutResourceLoading();
    void serverEmptyStateExplainsActiveFilters_data();
    void serverEmptyStateExplainsActiveFilters();
    void captureActionPreservesCleanupAdmission_data();
    void captureActionPreservesCleanupAdmission();
    void telemetryControlFollowsCapability_data();
    void telemetryControlFollowsCapability();

private:
    QObject *createComponent(QQmlEngine &engine, FakeVpnController &controller,
                             const QString &fileName);
    QString m_componentErrors;
};

void SignInPresentationTest::runnerNamesAreLiteralWithoutResourceLoading_data()
{
    QTest::addColumn<QString>("argument");
    QTest::newRow("image") << QStringLiteral(
        R"({"countryCode":"CH","kind":"location","name":"<img src='https://review.invalid/pixel.png'>"})");
    QTest::newRow("json-escaped-image") << QStringLiteral(
        R"({"countryCode":"CH","kind":"location","name":"\u003cimg src='https://review.invalid/pixel.png'\u003e"})");
    QTest::newRow("unicode-secure-core") << QStringLiteral(
        R"({"countryCode":"CH","kind":"secure-core","name":"Zürich — 東京"})");
    QTest::newRow("entities") << QStringLiteral(
        R"({"countryCode":"CH","kind":"location","name":"<b>A &amp; B</b>"})");
}

void SignInPresentationTest::runnerNamesAreLiteralWithoutResourceLoading()
{
    QFETCH(QString, argument);
    const auto request = ProtonVpnKde::validatedRunnerActionRequest(QStringLiteral("group"), argument);
    QVERIFY(request);
    const auto group = QJsonDocument::fromJson(request->argument.toUtf8()).object();
    FakeVpnController controller;
    controller.loggedIn = true;
    controller.authState = QStringLiteral("signed_in");
    FakeAppSettings appSettings;
    DenyingNetworkFactory network;
    QQmlEngine engine;
    engine.setNetworkAccessManagerFactory(&network);
    QQuickWindow window;
    window.resize(800, 600);
    QQmlComponent component(&engine, QUrl::fromLocalFile(QStringLiteral(
        PROTON_VPN_KDE_SOURCE_DIR "/qml/MainDialogs.qml")));
    QScopedPointer<QObject> dialogs(component.createWithInitialProperties({
        {QStringLiteral("vpnController"), QVariant::fromValue(static_cast<QObject *>(&controller))},
        {QStringLiteral("appSettings"), QVariant::fromValue(static_cast<QObject *>(&appSettings))},
        {QStringLiteral("windowWidth"), 800.0}}));
    QVERIFY2(dialogs, qPrintable(component.errorString()));
    auto *item = qobject_cast<QQuickItem *>(dialogs.data());
    QVERIFY(item);
    item->setParentItem(window.contentItem());
    item->setSize(QSizeF(800, 600));
    window.show();
    QVERIFY(QMetaObject::invokeMethod(dialogs.data(), "requestRunnerAction",
        Q_ARG(QVariant, QVariant(request->action)), Q_ARG(QVariant, QVariant(request->argument))));
    QTRY_VERIFY(dialogs->property("runnerActionVisible").toBool());
    QTest::qWait(100);
    QCOMPARE(controller.connectCalls, 0);
    QCOMPARE(network.requests.load(), 0);
    auto *label = dialogs->findChild<QObject *>(QStringLiteral("runnerConfirmationText"));
    QVERIFY(label);
    QCOMPARE(label->property("textFormat").toInt(), static_cast<int>(Qt::PlainText));
    QVERIFY(label->property("text").toString().contains(group.value(QStringLiteral("name")).toString()));
    QVERIFY(QMetaObject::invokeMethod(dialogs.data(), "acceptRunnerAction"));
    QTest::qWait(50);
    QCOMPARE(network.requests.load(), 0);
    QCOMPARE(controller.connectCalls, 1);
    QCOMPARE(controller.connectedGroup, QStringList({QStringLiteral("CH"),
        group.value(QStringLiteral("kind")).toString(), group.value(QStringLiteral("name")).toString()}));
}

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

void SignInPresentationTest::connectorStartupFailureIsNotSignIn()
{
    FakeVpnController controller;
    controller.ready = false;
    controller.loggedIn = true;
    controller.authState = QStringLiteral("signed_in");
    controller.state = QStringLiteral("error");
    controller.message = QStringLiteral("Saved session restored; networking could not initialize.");
    QQmlEngine engine;
    QScopedPointer<QObject> page(
        createComponent(engine, controller, QStringLiteral("SignInPage.qml")));
    QVERIFY2(page, qPrintable(m_componentErrors));
    QCOMPARE(page->property("activeStepHeading").toString(),
             QStringLiteral("VPN service could not start"));
    QCOMPARE(page->property("activeStepDescription").toString(), controller.message);
    QVERIFY(!page->property("credentialsVisible").toBool());
    QVERIFY(page->property("backendRetryVisible").toBool());
    auto *progress = page->findChild<QObject *>(QStringLiteral("backendPreparationProgress"));
    QVERIFY(progress);
    QVERIFY(!progress->property("running").toBool());
    // No implicit retry, including when the same failure is republished.
    emit controller.snapshotChanged();
    QCoreApplication::processEvents();
    QCOMPARE(controller.restartCalls, 0);
}

void SignInPresentationTest::recoveryPreservesAuthoritativeMessage_data()
{
    QTest::addColumn<QString>("authState");
    QTest::newRow("authentication-unknown")
        << QStringLiteral("authentication_unknown");
    QTest::newRow("settings-unavailable")
        << QStringLiteral("settings_unavailable");
    QTest::newRow("protection-unknown") << QStringLiteral("protection_unknown");
    QTest::newRow("account-restart") << QStringLiteral("account_restart_required");
    QTest::newRow("expired") << QStringLiteral("expired");
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
             authState == QStringLiteral("account_restart_required")
                 ? QStringLiteral("Finish signing out")
                 : authState == QStringLiteral("expired")
                     ? QStringLiteral("Prepare to sign in again")
                     : QStringLiteral("Account state unavailable"));
    QVERIFY(!page->property("credentialsVisible").toBool());
    QCOMPARE(page->property("activeStepDescription").toString(),
             controller.message);
    if (authState == QStringLiteral("expired")) {
        const QObject *notice = page->findChild<QObject *>(QStringLiteral("accountRecoveryNotice"));
        QVERIFY(notice);
        QVERIFY(notice->property("text").toString().contains(QStringLiteral("disconnects")));
    }
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

    controller.state = QStringLiteral("connected");
    controller.authState = QStringLiteral("signed_in_degraded");
    controller.message = QStringLiteral("Packet capture stopped at the 15-minute safety limit");
    emit controller.snapshotChanged();
    QCoreApplication::processEvents();
    QVERIFY(banner->property("backgroundServicesDegraded").toBool());
    QVERIFY(banner->property("bannerActive").toBool());
    QVERIFY(!banner->property("connectionErrorActive").toBool());
    const QString degradedMessage = QStringLiteral(
        "Some Proton background updates stopped. Sign out and sign in again to restart them.");
    QCOMPARE(banner->property("text").toString(), degradedMessage);
    controller.message = QStringLiteral("The VPN operation is still completing");
    emit controller.snapshotChanged();
    QCoreApplication::processEvents();
    QCOMPARE(banner->property("text").toString(), degradedMessage);
    const QObject *degradedRestart = banner->findChild<QObject *>(
        QStringLiteral("restartUnresponsiveBackendAction"));
    QVERIFY(degradedRestart);
    QVERIFY(!degradedRestart->property("visible").toBool());
    QCOMPARE(controller.disconnectCalls, 0);

    controller.authState = QStringLiteral("signed_in");
    emit controller.snapshotChanged();
    QCoreApplication::processEvents();
    QVERIFY(!banner->property("bannerActive").toBool());
    controller.authState = QStringLiteral("signed_in_degraded");
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
    QVERIFY(banner->property("bannerActive").toBool());
    QCOMPARE(banner->property("text").toString(), degradedMessage);
    controller.authState = QStringLiteral("signed_in");
    emit controller.snapshotChanged();
    QCoreApplication::processEvents();
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

void SignInPresentationTest::connectionFeedbackCannotInferAcknowledgement_data()
{
    QTest::addColumn<QString>("initialState");
    QTest::addColumn<QString>("finalState");
    QTest::addColumn<QString>("target");
    QTest::addColumn<bool>("acknowledged");
    QTest::addColumn<bool>("replyFirst");
    for (const auto &initial : {QStringLiteral("connected"), QStringLiteral("disconnected")}) {
        for (const auto &final : {QStringLiteral("connected"), QStringLiteral("disconnected"), QStringLiteral("error")}) {
            for (const auto &target : {QStringLiteral("connected"), QStringLiteral("disconnected")}) {
                for (const bool acknowledged : {false, true}) {
                    for (const bool replyFirst : {false, true}) {
                        const QString name = initial + u'-' + final + u'-' + target
                            + (acknowledged ? QStringLiteral("-ack") : QStringLiteral("-unknown"))
                            + (replyFirst ? QStringLiteral("-reply-first") : QStringLiteral("-state-first"));
                        QTest::newRow(qPrintable(name)) << initial << final << target << acknowledged << replyFirst;
                    }
                }
            }
        }
    }
}

void SignInPresentationTest::connectionFeedbackCannotInferAcknowledgement()
{
    QFETCH(QString, initialState);
    QFETCH(QString, finalState);
    QFETCH(QString, target);
    QFETCH(bool, acknowledged);
    QFETCH(bool, replyFirst);
    FakeVpnController controller;
    controller.loggedIn = true;
    controller.state = initialState;
    QQmlEngine engine;
    QQmlComponent component(&engine, QUrl::fromLocalFile(QStringLiteral(
        PROTON_VPN_KDE_SOURCE_DIR "/qml/ConnectionActionFeedback.qml")));
    QScopedPointer<QObject> feedback(component.createWithInitialProperties({
        {QStringLiteral("controller"), QVariant::fromValue(static_cast<QObject *>(&controller))}}));
    QVERIFY2(feedback, qPrintable(component.errorString()));
    const QString warning = QStringLiteral("The request result could not be confirmed");
    emit controller.connectionOperationStarted(1, target);
    const auto finish = [&] {
        emit controller.connectionOperationFinished(1, target, acknowledged,
                                                    acknowledged ? QString{} : warning);
    };
    if (replyFirst) {
        finish();
    }
    controller.state = finalState;
    emit controller.snapshotChanged();
    if (!replyFirst) {
        finish();
    }
    QCoreApplication::processEvents();
    const bool warningVisible = !acknowledged && finalState != QStringLiteral("error");
    QCOMPARE(feedback->property("messageActive").toBool(), warningVisible);
    if (warningVisible) {
        QCOMPARE(feedback->property("completedMessage").toString(), warning);
        controller.message = QStringLiteral("An unrelated operation updated the status");
        emit controller.snapshotChanged();
        QCoreApplication::processEvents();
        QVERIFY(feedback->property("messageActive").toBool());
    }
    emit controller.connectionOperationStarted(2, target);
    QCoreApplication::processEvents();
    QVERIFY(!feedback->property("messageActive").toBool());
}

void SignInPresentationTest::runnerActionsUseCurrentIntentPermission_data()
{
    QTest::addColumn<QString>("action");
    QTest::addColumn<QString>("state");
    QTest::addColumn<bool>("busy");
    QTest::addColumn<bool>("loggedIn");
    QTest::addColumn<bool>("available");
    QTest::addColumn<bool>("expectedEnabled");
    QTest::addColumn<bool>("loseOwnerBeforeAccept");
    QTest::newRow("unavailable-disconnect") << QStringLiteral("disconnect")
        << QStringLiteral("connected") << false << true << false << false << false;
    QTest::newRow("pending-connect-cancel") << QStringLiteral("disconnect")
        << QStringLiteral("disconnected") << true << true << true << true << false;
    QTest::newRow("connecting-cancel") << QStringLiteral("disconnect")
        << QStringLiteral("connecting") << true << true << true << true << false;
    QTest::newRow("expired-tunnel-disconnect") << QStringLiteral("disconnect")
        << QStringLiteral("connected") << false << false << true << true << false;
    QTest::newRow("idle-disconnect") << QStringLiteral("disconnect")
        << QStringLiteral("disconnected") << false << true << true << false << false;
    QTest::newRow("idle-fastest") << QStringLiteral("fastest")
        << QStringLiteral("disconnected") << false << true << true << true << false;
    for (const QString &action : {QStringLiteral("fastest"), QStringLiteral("country"),
                                  QStringLiteral("server"), QStringLiteral("group")}) {
        QTest::newRow(qPrintable(action + QStringLiteral("-busy")))
            << action << QStringLiteral("connecting") << true << true << true << false << false;
        QTest::newRow(qPrintable(action + QStringLiteral("-switch-target")))
            << action << QStringLiteral("connected") << false << true << true << true << false;
    }
    QTest::newRow("reject-unknown-intent") << QStringLiteral("unknown")
        << QStringLiteral("disconnected") << false << true << true << false << false;
    QTest::newRow("owner-lost-before-disconnect-confirmation") << QStringLiteral("disconnect")
        << QStringLiteral("connecting") << true << true << true << true << true;
    QTest::newRow("owner-lost-before-connect-confirmation") << QStringLiteral("fastest")
        << QStringLiteral("disconnected") << false << true << true << true << true;
}

void SignInPresentationTest::runnerActionsUseCurrentIntentPermission()
{
    QFETCH(QString, action);
    QFETCH(QString, state);
    QFETCH(bool, busy);
    QFETCH(bool, loggedIn);
    QFETCH(bool, available);
    QFETCH(bool, expectedEnabled);
    QFETCH(bool, loseOwnerBeforeAccept);
    FakeVpnController controller;
    controller.backendAvailable = available;
    controller.ready = true;
    controller.loggedIn = loggedIn;
    controller.authState = loggedIn ? QStringLiteral("signed_in") : QStringLiteral("expired");
    controller.busy = busy;
    controller.state = state;
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

    const QVariant actionValue = action;
    const QVariant argument = action == QStringLiteral("group")
        ? QStringLiteral(R"json({"countryCode":"CH","kind":"location","name":"Zurich"})json")
        : QStringLiteral("CH");
    QVERIFY(QMetaObject::invokeMethod(
        dialogs.data(), "requestRunnerAction",
        Q_ARG(QVariant, actionValue), Q_ARG(QVariant, argument)));
    QCoreApplication::processEvents();
    QCOMPARE(dialogs->property("runnerActionEnabled").toBool(), expectedEnabled);
    if (loseOwnerBeforeAccept) {
        controller.backendAvailable = false;
        emit controller.snapshotChanged();
        QCoreApplication::processEvents();
        QVERIFY(!dialogs->property("runnerActionEnabled").toBool());
    }
    QVERIFY(QMetaObject::invokeMethod(dialogs.data(), "acceptRunnerAction"));
    QCoreApplication::processEvents();
    const bool shouldDispatch = expectedEnabled && !loseOwnerBeforeAccept;
    QCOMPARE(controller.disconnectCalls,
             shouldDispatch && action == QStringLiteral("disconnect") ? 1 : 0);
    QCOMPARE(controller.connectCalls,
             shouldDispatch && action != QStringLiteral("disconnect") ? 1 : 0);
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

void SignInPresentationTest::captureActionPreservesCleanupAdmission_data()
{
    QTest::addColumn<bool>("active");
    QTest::addColumn<bool>("busy");
    QTest::addColumn<bool>("ready");
    QTest::addColumn<bool>("available");
    QTest::addColumn<QString>("state");
    QTest::addColumn<bool>("enabled");
    QTest::newRow("stop-beside-busy-save")
        << true << true << true << true << QStringLiteral("connected") << true;
    QTest::newRow("stop-after-session-expiry")
        << true << false << true << true << QStringLiteral("disconnected") << true;
    QTest::newRow("stop-service-unavailable")
        << true << false << true << false << QStringLiteral("connected") << false;
    QTest::newRow("stop-service-not-ready")
        << true << false << false << true << QStringLiteral("connected") << false;
    QTest::newRow("start-connected")
        << false << false << true << true << QStringLiteral("connected") << true;
    QTest::newRow("start-busy")
        << false << true << true << true << QStringLiteral("connected") << false;
    QTest::newRow("start-disconnected")
        << false << false << true << true << QStringLiteral("disconnected") << false;
    QTest::newRow("start-service-unavailable")
        << false << false << true << false << QStringLiteral("connected") << false;
}

void SignInPresentationTest::captureActionPreservesCleanupAdmission()
{
    QFETCH(bool, active);
    QFETCH(bool, busy);
    QFETCH(bool, ready);
    QFETCH(bool, available);
    QFETCH(QString, state);
    QFETCH(bool, enabled);
    FakeVpnController controller;
    controller.packetCaptureActive = active;
    controller.busy = busy;
    controller.ready = ready;
    controller.backendAvailable = available;
    controller.state = state;
    controller.loggedIn = !active;
    controller.authState = active ? QStringLiteral("expired") : QStringLiteral("signed_in");
    QQmlEngine engine;
    engine.rootContext()->setContextProperty(QStringLiteral("testController"), &controller);
    QQmlComponent component(&engine);
    component.setData(R"qml(
import QtQuick
import "." as Local
Local.PrivacySettingsSection {
    vpnController: testController
    vpnSettings: QtObject {
        property bool packetCaptureSupported: true
        property bool anonymousCrashReports: false
        property bool telemetry: false
        property bool loaded: true
        property bool busy: false
    }
    appSettings: QtObject { property string packetCaptureDirectory: "/tmp" }
    pageWidth: 800
    width: 800
}
)qml", QUrl::fromLocalFile(QStringLiteral(
        PROTON_VPN_KDE_SOURCE_DIR "/qml/CaptureActionHarness.qml")));
    QScopedPointer<QObject> page(component.create());
    QVERIFY2(page, qPrintable(component.errorString()));
    QObject *button = page->findChild<QObject *>(QStringLiteral("packetCaptureAction"));
    QVERIFY(button);
    QCOMPARE(button->property("enabled").toBool(), enabled);
    QCOMPARE(button->property("text").toString(),
             active ? QStringLiteral("Stop capture") : QStringLiteral("Start capture"));
    if (enabled)
    {
        QVERIFY(QMetaObject::invokeMethod(button, "clicked"));
        QCOMPARE(controller.captureStopCalls, active ? 1 : 0);
        QCOMPARE(controller.captureStartCalls, active ? 0 : 1);
    }
    controller.backendAvailable = false;
    emit controller.snapshotChanged();
    QVERIFY(!button->property("enabled").toBool());
}

void SignInPresentationTest::telemetryControlFollowsCapability_data()
{
    QTest::addColumn<bool>("buildEnabled");
    QTest::addColumn<bool>("runtimeAvailable");
    QTest::addColumn<bool>("preference");
    QTest::newRow("build-disabled") << false << true << false;
    QTest::newRow("core-unavailable") << true << false << false;
    QTest::newRow("available-off") << true << true << false;
    QTest::newRow("available-on") << true << true << true;
}

void SignInPresentationTest::telemetryControlFollowsCapability()
{
    QFETCH(bool, buildEnabled);
    QFETCH(bool, runtimeAvailable);
    QFETCH(bool, preference);
    FakeVpnController controller;
    controller.loggedIn = true;
    controller.telemetryBuildEnabled = buildEnabled;
    QQmlEngine engine;
    engine.rootContext()->setContextProperty(QStringLiteral("testController"),
                                             &controller);
    QQmlComponent component(&engine);
    component.setData(QStringLiteral(R"qml(
import QtQuick
import "." as Local
Local.PrivacySettingsSection {
    vpnController: testController
    vpnSettings: QtObject {
        property bool packetCaptureSupported: false
        property bool anonymousCrashReports: false
        property bool telemetry: %1
        property bool telemetryAvailable: %2
        property bool loaded: true
        property bool busy: false
    }
    appSettings: QtObject { property string packetCaptureDirectory: "/tmp" }
    pageWidth: 800
    width: 800
}
)qml").arg(preference ? QStringLiteral("true") : QStringLiteral("false"),
             runtimeAvailable ? QStringLiteral("true") : QStringLiteral("false")).toUtf8(),
        QUrl::fromLocalFile(QStringLiteral(
            PROTON_VPN_KDE_SOURCE_DIR "/qml/TelemetryControlHarness.qml")));
    QScopedPointer<QObject> page(component.create());
    QVERIFY2(page, qPrintable(component.errorString()));
    QObject *toggle = page->findChild<QObject *>(
        QStringLiteral("connectionTelemetrySwitch"));
    QVERIFY(toggle);
    const bool available = buildEnabled && runtimeAvailable;
    QCOMPARE(toggle->property("enabled").toBool(), available);
    QCOMPARE(toggle->property("checked").toBool(), available && preference);
    if (!available) {
        return;
    }

    toggle->setProperty("checked", !preference);
    QVERIFY(QMetaObject::invokeMethod(toggle, "clicked"));
    QCOMPARE(controller.settingsUpdateCalls, 1);
    QCOMPARE(controller.lastSetting, QStringLiteral("telemetry"));
    QCOMPARE(controller.lastSettingValue.toBool(), !preference);
}

QTEST_MAIN(SignInPresentationTest)

#include "SignInPresentationTest.moc"
