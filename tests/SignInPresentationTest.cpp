// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#include <QQmlComponent>
#include <QQmlContext>
#include <QQmlEngine>
#include <QScopedPointer>
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
    Q_PROPERTY(bool backendRestartAllowed MEMBER backendRestartAllowed NOTIFY snapshotChanged)
    Q_PROPERTY(bool fido2Available MEMBER fido2Available NOTIFY snapshotChanged)
    Q_PROPERTY(int killSwitch MEMBER killSwitch NOTIFY snapshotChanged)
    Q_PROPERTY(QString authState MEMBER authState NOTIFY snapshotChanged)
    Q_PROPERTY(QString state MEMBER state NOTIFY snapshotChanged)
    Q_PROPERTY(QString errorCode MEMBER errorCode NOTIFY snapshotChanged)
    Q_PROPERTY(QString message MEMBER message NOTIFY snapshotChanged)

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
    int restartCalls = 0;

    Q_INVOKABLE void restartBackend() { ++restartCalls; }
    Q_INVOKABLE void disableKillSwitchForLogin() { }
    Q_INVOKABLE void login(const QString &, const QString &) { }
    Q_INVOKABLE void submitTwoFactor(const QString &) { }
    Q_INVOKABLE void beginFido2() { }
    Q_INVOKABLE void cancelFido2() { }
    Q_INVOKABLE void submitFido2Pin(const QString &) { }
    Q_INVOKABLE void cancelLogin() { }

signals:
    void snapshotChanged();
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
    controller.message =
        QStringLiteral("No server available in the current tier");
    emit controller.snapshotChanged();
    QCoreApplication::processEvents();
    QVERIFY(!banner->property("recoveryActive").toBool());
    QVERIFY(banner->property("statusMessageActive").toBool());
    QVERIFY(banner->property("bannerActive").toBool());
    QCOMPARE(banner->property("text").toString(), controller.message);

    controller.busy = true;
    emit controller.snapshotChanged();
    QCoreApplication::processEvents();
    QVERIFY(!banner->property("statusMessageActive").toBool());
    QVERIFY(!banner->property("bannerActive").toBool());

    controller.busy = false;
    controller.message.clear();
    emit controller.snapshotChanged();
    QCoreApplication::processEvents();
    QVERIFY(!banner->property("statusMessageActive").toBool());
    QVERIFY(!banner->property("bannerActive").toBool());
}

QTEST_MAIN(SignInPresentationTest)

#include "SignInPresentationTest.moc"
