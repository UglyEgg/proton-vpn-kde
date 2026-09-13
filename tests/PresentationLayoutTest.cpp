// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#include <QDir>
#include <QFile>
#include <QJSValue>
#include <QQmlComponent>
#include <QQmlContext>
#include <QQmlEngine>
#include <QQuickItem>
#include <QQuickWindow>
#include <QScopeGuard>
#include <QScopedPointer>
#include <QTemporaryDir>
#include <QSignalSpy>
#include <QtTest>

#include "AppSettings.h"

class ReportPreviewController final : public QObject
{
    Q_OBJECT
    Q_PROPERTY(bool supportReportSubmissionEnabled READ submissionEnabled CONSTANT)
    Q_PROPERTY(bool loggedIn READ loggedIn CONSTANT)
    Q_PROPERTY(bool busy READ busy CONSTANT)
    Q_PROPERTY(QString accountName READ accountName CONSTANT)
public:
    bool submissionEnabled() const { return false; }
    bool loggedIn() const { return true; }
    bool busy() const { return false; }
    QString accountName() const { return QStringLiteral("demo-user"); }
    int submissions = 0;
    Q_INVOKABLE void submitSupportReport(
        const QString &, const QString &, const QString &, bool) { ++submissions; }
Q_SIGNALS:
    void supportReportFinished(bool success, const QString &message);
};

class PresentationLayoutTest final : public QObject
{
    Q_OBJECT
private Q_SLOTS:
    void reportStaysInsideCard_data();
    void reportStaysInsideCard();
    void splitRouteIsConditionalAndNavigable_data();
    void splitRouteIsConditionalAndNavigable();
    void windowSizeIsOwnedByContent();
    void startupControlsPreservePreferencesAndFit_data();
    void startupControlsPreservePreferencesAndFit();
    void startupControlsRestoreRejectedValues();
    void releaseNotesAreBriefAndNavigable_data();
    void releaseNotesAreBriefAndNavigable();

private:
    void capture(QQuickWindow *window);
};

void PresentationLayoutTest::startupControlsRestoreRejectedValues()
{
    QTemporaryDir configHome;
    QVERIFY(configHome.isValid());
    const auto oldConfig = qgetenv("XDG_CONFIG_HOME");
    const auto restore = qScopeGuard([&] { qputenv("XDG_CONFIG_HOME", oldConfig); });
    qputenv("XDG_CONFIG_HOME", configHome.path().toUtf8());
    QFile config(configHome.filePath("proton-vpn-kderc"));
    QVERIFY(config.open(QIODevice::WriteOnly));
    QVERIFY(config.write("[General][$i]\nAutoConnectTarget=US\n") > 0);
    config.close();
    AppSettings settings;
    QQmlEngine engine;
    QQmlComponent component(&engine, QUrl::fromLocalFile(QStringLiteral(
        PROTON_VPN_KDE_SOURCE_DIR "/qml/StartupSettingsSection.qml")));
    QScopedPointer<QObject> root(component.createWithInitialProperties({
        {QStringLiteral("appSettings"), QVariant::fromValue(static_cast<QObject *>(&settings))},
        {QStringLiteral("pageWidth"), 800.0}}));
    QVERIFY2(root, qPrintable(component.errorString()));
    auto *autoConnect = root->findChild<QObject *>(QStringLiteral("startupAutoConnect"));
    auto *presentation = root->findChild<QObject *>(QStringLiteral("startupPresentation"));
    auto *tray = root->findChild<QObject *>(QStringLiteral("keepTrayControlsSwitch"));
    QVERIFY(autoConnect && presentation && tray);
    for (int attempt = 0; attempt < 2; ++attempt) {
        autoConnect->setProperty("currentIndex", 0);
        QVERIFY(QMetaObject::invokeMethod(autoConnect, "activated", Q_ARG(int, 0)));
        QCOMPARE(settings.autoConnectTarget(), QStringLiteral("US"));
        QCOMPARE(autoConnect->property("currentIndex").toInt(), 2);
        QVERIFY(!settings.errorMessage().isEmpty());
        presentation->setProperty("currentIndex", 1);
        QVERIFY(QMetaObject::invokeMethod(presentation, "activated", Q_ARG(int, 1)));
        QCOMPARE(presentation->property("currentIndex").toInt(), 0);
        tray->setProperty("checked", false);
        QVERIFY(QMetaObject::invokeMethod(tray, "toggled"));
        QVERIFY(tray->property("checked").toBool());
    }
}

void PresentationLayoutTest::capture(QQuickWindow *window)
{
    const QString directory = qEnvironmentVariable("PLASMA_VPN_LAYOUT_CAPTURE_DIR");
    if (!directory.isEmpty()) {
        const QString name = QString::fromLatin1(QTest::currentTestFunction())
            + QLatin1Char('-') + QString::fromLatin1(QTest::currentDataTag())
            + QStringLiteral(".png");
        QVERIFY(window->grabWindow().save(QDir(directory).filePath(name)));
    }
}

void PresentationLayoutTest::startupControlsPreservePreferencesAndFit_data()
{
    QTest::addColumn<int>("viewportWidth");
    QTest::addColumn<qreal>("fontScale");
    QTest::addColumn<bool>("rtl");
    QTest::newRow("compact") << 440 << 1.0 << false;
    QTest::newRow("wide") << 800 << 1.0 << false;
    QTest::newRow("large-text") << 640 << 1.5 << false;
    QTest::newRow("rtl") << 440 << 1.0 << true;
}

void PresentationLayoutTest::startupControlsPreservePreferencesAndFit()
{
    QFETCH(int, viewportWidth);
    QFETCH(qreal, fontScale);
    QFETCH(bool, rtl);
    QTemporaryDir configHome;
    QVERIFY(configHome.isValid());
    const QByteArray oldConfig = qgetenv("XDG_CONFIG_HOME");
    qputenv("XDG_CONFIG_HOME", configHome.path().toUtf8());
    const auto originalFont = QGuiApplication::font();
    const auto originalDirection = QGuiApplication::layoutDirection();
    const auto restore = qScopeGuard([&] {
        qputenv("XDG_CONFIG_HOME", oldConfig);
        QGuiApplication::setFont(originalFont);
        QGuiApplication::setLayoutDirection(originalDirection);
    });
    auto font = originalFont;
    font.setPointSizeF(font.pointSizeF() * fontScale);
    QGuiApplication::setFont(font);
    QGuiApplication::setLayoutDirection(rtl ? Qt::RightToLeft : Qt::LeftToRight);
    AppSettings settings;
    settings.setCloseToTray(false);
    settings.setAutoConnectTarget(QStringLiteral("CH#101"));
    QQmlEngine engine;
    engine.rootContext()->setContextProperty(QStringLiteral("settingsFixture"), &settings);
    engine.rootContext()->setContextProperty(QStringLiteral("viewportWidth"), viewportWidth);
    QQmlComponent component(&engine);
    component.setData(R"(
        import QtQuick
        import QtQuick.Controls
        import QtQuick.Layouts
        ApplicationWindow {
            width: viewportWidth; height: 1100; visible: true
            ColumnLayout {
                width: parent.width
                StartupSettingsSection {
                    appSettings: settingsFixture
                    pageWidth: viewportWidth
                }
            }
        }
    )", QUrl::fromLocalFile(QStringLiteral(PROTON_VPN_KDE_SOURCE_DIR "/qml/LayoutFixture.qml")));
    QScopedPointer<QObject> root(component.create());
    QVERIFY2(root, qPrintable(component.errorString()));
    auto *window = qobject_cast<QQuickWindow *>(root.data());
    auto *card = root->findChild<QQuickItem *>(QStringLiteral("startupSettingsSection"));
    auto *presentation = root->findChild<QObject *>(QStringLiteral("startupPresentation"));
    auto *autoConnect = root->findChild<QObject *>(QStringLiteral("startupAutoConnect"));
    auto *target = root->findChild<QObject *>(QStringLiteral("startupCustomTarget"));
    auto *trayHelp = root->findChild<QQuickItem *>(QStringLiteral("trayStartupHelp"));
    auto *connectHelp = root->findChild<QQuickItem *>(QStringLiteral("autoConnectHelp"));
    QVERIFY(window && card && presentation && autoConnect && target);
    QVERIFY(trayHelp && connectHelp);
    QVERIFY(!trayHelp->isVisible());
    QVERIFY(connectHelp->isVisible());
    QCOMPARE(autoConnect->property("currentIndex").toInt(), 2);
    QCOMPARE(target->property("text").toString(), QStringLiteral("CH#101"));
    QVERIFY(QMetaObject::invokeMethod(presentation, "activated", Q_ARG(int, 1)));
    QVERIFY(settings.closeToTray());
    QVERIFY(settings.startTrayOnly(false, false));
    QVERIFY(trayHelp->isVisible());
    QVERIFY(!settings.startTrayOnly(false, true));
    QVERIFY(QMetaObject::invokeMethod(autoConnect, "activated", Q_ARG(int, 1)));
    QCOMPARE(settings.autoConnectTarget(), QStringLiteral("FASTEST"));
    QVERIFY(QMetaObject::invokeMethod(autoConnect, "activated", Q_ARG(int, 2)));
    QVERIFY(settings.autoConnectTarget().isEmpty());
    QVERIFY(connectHelp->isVisible()); // Explain why a blank custom target is off.
    target->setProperty("text", QStringLiteral(" us "));
    QVERIFY(QMetaObject::invokeMethod(target, "editingFinished"));
    QCOMPARE(settings.autoConnectTarget(), QStringLiteral("US"));
    settings.setAutoConnectTarget(QStringLiteral("DE"));
    QTRY_COMPARE(target->property("text").toString(), QStringLiteral("DE"));
    QVERIFY(!settings.autostart()->enabled()); // Opening/settings selection is not consent.
    QVERIFY(!QFileInfo::exists(configHome.filePath("autostart/proton-vpn-kde.desktop")));
    QTest::qWait(100);
    capture(window);
    const QRectF bounds(0, 0, card->width(), card->height());
    for (const auto &name : {"startAtLoginSwitch", "startupPresentation",
                             "keepTrayControlsSwitch", "startupAutoConnect", "startupCustomTarget"}) {
        auto *item = root->findChild<QQuickItem *>(QString::fromLatin1(name));
        QVERIFY(item);
        QVERIFY2(bounds.adjusted(-1, -1, 1, 1).contains(item->mapRectToItem(
            card, QRectF(0, 0, item->width(), item->height()))), name);
    }
    QVERIFY(QMetaObject::invokeMethod(presentation, "activated", Q_ARG(int, 0)));
    QVERIFY(!settings.startTrayOnly(false, false));
    QVERIFY(settings.closeToTray()); // Showing the window does not disable its tray.
    QVERIFY(!trayHelp->isVisible());
    QVERIFY(QMetaObject::invokeMethod(autoConnect, "activated", Q_ARG(int, 0)));
    QVERIFY(settings.autoConnectTarget().isEmpty());
    QVERIFY(!connectHelp->isVisible());
}

void PresentationLayoutTest::releaseNotesAreBriefAndNavigable_data()
{
    startupControlsPreservePreferencesAndFit_data();
}

void PresentationLayoutTest::releaseNotesAreBriefAndNavigable()
{
    QFETCH(int, viewportWidth);
    QFETCH(qreal, fontScale);
    QFETCH(bool, rtl);
    const auto originalFont = QGuiApplication::font();
    const auto originalDirection = QGuiApplication::layoutDirection();
    const auto restore = qScopeGuard([&] {
        QGuiApplication::setFont(originalFont);
        QGuiApplication::setLayoutDirection(originalDirection);
    });
    auto font = originalFont;
    font.setPointSizeF(font.pointSizeF() * fontScale);
    QGuiApplication::setFont(font);
    QGuiApplication::setLayoutDirection(rtl ? Qt::RightToLeft : Qt::LeftToRight);
    QQmlEngine engine;
    engine.rootContext()->setContextProperty(QStringLiteral("viewportWidth"), viewportWidth);
    QQmlComponent component(&engine);
    component.setData(R"(
        import QtQuick
        import QtQuick.Controls
        ApplicationWindow {
            width: viewportWidth; height: 1000; visible: true
            ReleaseNotesPage { anchors.fill: parent }
        }
    )", QUrl::fromLocalFile(QStringLiteral(PROTON_VPN_KDE_SOURCE_DIR "/qml/LayoutFixture.qml")));
    QScopedPointer<QObject> root(component.create());
    QVERIFY2(root, qPrintable(component.errorString()));
    auto *window = qobject_cast<QQuickWindow *>(root.data());
    auto *highlights = root->findChild<QQuickItem *>(QStringLiteral("currentReleaseHighlights"));
    auto *history = root->findChild<QQuickItem *>(QStringLiteral("previousReleaseHistory"));
    auto *toggle = root->findChild<QQuickItem *>(QStringLiteral("previousReleasesToggle"));
    QVERIFY(window && highlights && history && toggle);
    // Test the rendered model, not a source-text count. Technical history lives
    // in the changelog; adding detail must not silently grow the default view.
    const auto notes = highlights->property("notes").value<QJSValue>().toVariant().toList();
    QVERIFY(notes.size() >= 3 && notes.size() <= 5);
    QVERIFY(!history->isVisible());
    QTest::qWait(100);
    const QRectF viewport(0, 0, window->width(), window->height());
    QVERIFY(viewport.contains(highlights->mapRectToScene(
        QRectF(0, 0, highlights->width(), highlights->height()))));
    capture(window);
    toggle->forceActiveFocus(Qt::TabFocusReason);
    QVERIFY(toggle->hasActiveFocus());
    QTest::keyClick(window, Qt::Key_Space);
    QTRY_VERIFY(history->isVisible());
    QTest::keyClick(window, Qt::Key_Space);
    QTRY_VERIFY(!history->isVisible());
    QTest::keyClick(window, Qt::Key_Tab);
    QVERIFY(!toggle->hasActiveFocus());
}

void PresentationLayoutTest::reportStaysInsideCard_data()
{
    QTest::addColumn<int>("viewportWidth");
    QTest::addColumn<qreal>("fontScale");
    QTest::addColumn<bool>("rtl");
    QTest::newRow("compact") << 480 << 1.0 << false;
    QTest::newRow("reported-width") << 671 << 1.0 << false;
    QTest::newRow("wide") << 900 << 1.0 << false;
    QTest::newRow("large-text") << 640 << 1.5 << false;
    QTest::newRow("rtl") << 480 << 1.0 << true;
}

void PresentationLayoutTest::reportStaysInsideCard()
{
    QFETCH(int, viewportWidth);
    QFETCH(qreal, fontScale);
    QFETCH(bool, rtl);
    const QFont originalFont = QGuiApplication::font();
    const auto originalDirection = QGuiApplication::layoutDirection();
    const auto restore = qScopeGuard([&] {
        QGuiApplication::setFont(originalFont);
        QGuiApplication::setLayoutDirection(originalDirection);
    });
    QFont font = originalFont;
    font.setPointSizeF(font.pointSizeF() * fontScale);
    QGuiApplication::setFont(font);
    QGuiApplication::setLayoutDirection(rtl ? Qt::RightToLeft : Qt::LeftToRight);
    ReportPreviewController controller;
    QQmlEngine engine;
    engine.rootContext()->setContextProperty(QStringLiteral("vpnController"), &controller);
    engine.rootContext()->setContextProperty(QStringLiteral("viewportWidth"), viewportWidth);
    QQmlComponent component(&engine);
    component.setData(R"(
        import QtQuick
        import QtQuick.Controls
        ApplicationWindow {
            width: viewportWidth; height: 900; visible: true
            ReportIssuePage { anchors.fill: parent }
        }
    )", QUrl::fromLocalFile(QStringLiteral(PROTON_VPN_KDE_SOURCE_DIR "/qml/LayoutFixture.qml")));
    QScopedPointer<QObject> root(component.create());
    QVERIFY2(root, qPrintable(component.errorString()));
    auto *window = qobject_cast<QQuickWindow *>(root.data());
    QVERIFY(window);
    auto *dialog = root->findChild<QObject *>(QStringLiteral("reportUnavailableDialog"));
    QVERIFY(dialog);
    QTRY_VERIFY(dialog->property("visible").toBool());
    QVERIFY(QMetaObject::invokeMethod(dialog, "close"));
    QTRY_VERIFY(!dialog->property("visible").toBool());
    auto *card = root->findChild<QQuickItem *>(QStringLiteral("supportReportCard"));
    QVERIFY(card);
    QTRY_VERIFY(card->width() > 0);
    QTest::qWait(50);
    capture(window);
    for (const QString &field : {QStringLiteral("reportUsername"),
                                 QStringLiteral("reportEmail"),
                                 QStringLiteral("reportDescription")}) {
        auto *item = root->findChild<QObject *>(field);
        QVERIFY(item);
        item->setProperty("text", QString(field == QStringLiteral("reportDescription")
                                          ? 8000 : 254, QLatin1Char('x')));
    }
    QTest::qWait(50);
    const QRectF bounds(0, 0, card->width(), card->height());
    for (const QString &name : {QStringLiteral("reportUsername"),
                                QStringLiteral("reportEmail"),
                                QStringLiteral("reportDescriptionScroll"),
                                QStringLiteral("reportLogWarning"),
                                QStringLiteral("reportActions")}) {
        auto *item = root->findChild<QQuickItem *>(name);
        QVERIFY(item);
        const QRectF rectangle = item->mapRectToItem(
            card, QRectF(0, 0, item->width(), item->height()));
        QVERIFY2(bounds.adjusted(-1, -1, 1, 1).contains(rectangle), qPrintable(name));
    }
    auto *actions = root->findChild<QQuickItem *>(QStringLiteral("reportActions"));
    for (QQuickItem *button : actions->childItems()) {
        QVERIFY(button->x() >= 0);
        QVERIFY(button->x() + button->width() <= actions->width() + 1);
    }
    auto *submit = root->findChild<QObject *>(QStringLiteral("reportSubmit"));
    QVERIFY(submit);
    QVERIFY(!submit->property("enabled").toBool());
    auto *page = root->findChild<QObject *>(QStringLiteral("reportIssuePage"));
    QVERIFY(QMetaObject::invokeMethod(page, "submitReport"));
    QCOMPARE(controller.submissions, 0);
}

void PresentationLayoutTest::splitRouteIsConditionalAndNavigable_data()
{
    QTest::addColumn<int>("viewportWidth");
    QTest::addColumn<bool>("connected");
    QTest::addColumn<bool>("splitEnabled");
    QTest::addColumn<qreal>("fontScale");
    QTest::newRow("split-wide") << 900 << true << true << 1.0;
    QTest::newRow("split-compact") << 460 << true << true << 1.0;
    QTest::newRow("full-wide") << 900 << true << false << 1.0;
    QTest::newRow("full-compact") << 460 << true << false << 1.0;
    QTest::newRow("large-text") << 640 << true << true << 1.5;
    QTest::newRow("inactive") << 460 << false << true << 1.0;
}

void PresentationLayoutTest::splitRouteIsConditionalAndNavigable()
{
    QTest::failOnWarning(QRegularExpression(QStringLiteral(".*recursive rearrange.*")));
    QFETCH(int, viewportWidth);
    QFETCH(bool, connected);
    QFETCH(bool, splitEnabled);
    QFETCH(qreal, fontScale);
    const QFont originalFont = QGuiApplication::font();
    const auto restore = qScopeGuard([&] { QGuiApplication::setFont(originalFont); });
    QFont font = originalFont;
    font.setPointSizeF(font.pointSizeF() * fontScale);
    QGuiApplication::setFont(font);
    QQmlEngine engine;
    engine.rootContext()->setContextProperty(QStringLiteral("viewportWidth"), viewportWidth);
    engine.rootContext()->setContextProperty(QStringLiteral("testConnected"), connected);
    engine.rootContext()->setContextProperty(QStringLiteral("testSplit"), splitEnabled);
    QQmlComponent component(&engine);
    component.setData(R"(
        import QtQuick
        import QtQuick.Controls
        import org.kde.kirigami as Kirigami
        ApplicationWindow {
            width: viewportWidth; height: 720; visible: true
            ConnectionScene {
                objectName: "scene"
                width: parent.width
                connected: testConnected; splitTunneling: testSplit
                connectionState: testConnected ? "connected" : "disconnected"
                stateText: testConnected ? "Protected" : "Not connected"
                stateColor: testConnected ? Kirigami.Theme.positiveTextColor
                                          : Kirigami.Theme.neutralTextColor
                summaryText: testConnected && testSplit
                    ? "Your rules decide which traffic uses the VPN" : ""
                loggedIn: true; ready: true; accountName: "demo-user"
                destinationName: "Illinois"; destinationFlag: "US"
                serverName: "US-IL#1018"; protocolName: "Smart"
                p2p: true; streaming: true
                primaryText: testConnected ? "Disconnect" : "Connect"
                primaryEnabled: true
            }
        }
    )", QUrl::fromLocalFile(QStringLiteral(PROTON_VPN_KDE_SOURCE_DIR "/qml/LayoutFixture.qml")));
    QScopedPointer<QObject> root(component.create());
    QVERIFY2(root, qPrintable(component.errorString()));
    auto *window = qobject_cast<QQuickWindow *>(root.data());
    auto *scene = root->findChild<QQuickItem *>(QStringLiteral("scene"));
    auto *cloud = root->findChild<QQuickItem *>(QStringLiteral("splitInternetRoute"));
    QVERIFY(window && scene && cloud);
    auto *routeShape = root->findChild<QObject *>(QStringLiteral("connectionRouteShape"));
    QVERIFY(routeShape);
    const auto renderer = routeShape->metaObject()->enumerator(
        routeShape->metaObject()->indexOfEnumerator("RendererType"));
    QCOMPARE(routeShape->property("preferredRendererType").toInt(),
             renderer.keyToValue("CurveRenderer"));
    QTRY_VERIFY(scene->height() > 0);
    QTest::qWait(50);
    QCOMPARE(cloud->isVisible(), connected && splitEnabled);
    if (qEnvironmentVariableIntValue("PLASMA_VPN_EXPECT_CURVE_RENDERER") == 1) {
        QCOMPARE(routeShape->property("rendererType").toInt(),
                 renderer.keyToValue("CurveRenderer"));
    }
    QCOMPARE(scene->property("splitRouteVisible").toBool(), connected && splitEnabled);
    if (cloud->isVisible()) {
        const QRectF cloudBounds = cloud->mapRectToItem(
            scene, QRectF(0, 0, cloud->width(), cloud->height()));
        QVERIFY(QRectF(0, 0, scene->width(), scene->height()).contains(cloudBounds));
        QSignalSpy navigation(scene, SIGNAL(navigateRequested(QString)));
        QVERIFY(QMetaObject::invokeMethod(cloud, "clicked"));
        QCOMPARE(navigation.count(), 1);
        QCOMPARE(navigation.at(0).at(0).toString(), QStringLiteral("split-tunneling"));
    }
    capture(window);
    auto *device = root->findChild<QQuickItem *>(QStringLiteral("deviceRouteNode"));
    auto *vpn = root->findChild<QQuickItem *>(QStringLiteral("vpnRouteNode"));
    auto *group = root->findChild<QQuickItem *>(QStringLiteral("vpnEndpointGroup"));
    auto *diagram = root->findChild<QQuickItem *>(QStringLiteral("connectionRouteDiagram"));
    auto *facts = root->findChild<QQuickItem *>(QStringLiteral("connectionFacts"));
    QVERIFY(device && vpn && group && diagram && facts);
    if (connected) {
        QCOMPARE(scene->property("stateColor").value<QColor>(),
                 vpn->property("accentColor").value<QColor>());
        QVERIFY(scene->property("stateColor").value<QColor>()
                != cloud->property("accentColor").value<QColor>());
    }
    // Exercise native keyboard activation and focus traversal, not just the
    // clicked signal used by the geometry/endpoint-fact checks below.
    QSignalSpy keyboardNavigation(scene, SIGNAL(navigateRequested(QString)));
    device->forceActiveFocus(Qt::TabFocusReason);
    QTest::keyClick(window, Qt::Key_Space);
    QCOMPARE(keyboardNavigation.size(), 1);
    QCOMPARE(keyboardNavigation.at(0).at(0).toString(), QStringLiteral("settings"));
    QTest::keyClick(window, Qt::Key_Tab);
    QVERIFY(!device->hasActiveFocus());
    const auto nodeCenter = [diagram](QQuickItem *node) {
        return node->mapToItem(diagram, QPointF(node->width() / 2,
            node->property("routeCenterY").toReal()));
    };
    QVERIFY(qAbs(nodeCenter(device).y() - nodeCenter(vpn).y()) <= 1);
    QVERIFY(qAbs(nodeCenter(device).x() + nodeCenter(vpn).x() - diagram->width()) <= 1);
    if (connected) {
        const QPointF originalDevice = nodeCenter(device);
        const QPointF originalVpn = nodeCenter(vpn);
        scene->setProperty("splitTunneling", false);
        QTRY_VERIFY(!cloud->isVisible());
        QTest::qWait(50);
        const qreal fullHeight = scene->implicitHeight();
        scene->setProperty("splitTunneling", true);
        QTRY_VERIFY(cloud->isVisible());
        QTRY_VERIFY(scene->implicitHeight() > fullHeight + cloud->height());
        QCOMPARE(nodeCenter(device), originalDevice);
        QCOMPARE(nodeCenter(vpn), originalVpn);
        scene->setProperty("splitTunneling", false);
        QTRY_COMPARE(scene->implicitHeight(), fullHeight);

        // All facts remain with the VPN endpoint, including long values and
        // optional facts. Wrapping must not move the device/endpoint baseline.
        scene->setProperty("serverName", QString(100, QLatin1Char('W')));
        scene->setProperty("secureCore", true);
        scene->setProperty("entryCountry", QStringLiteral("A very long entry country"));
        scene->setProperty("forwardedPort", 45000);
        scene->setProperty("tor", true);
        scene->setProperty("smartRouting", true);
        QTest::qWait(50);
        const QRectF bounds(0, 0, group->width(), group->height());
        for (auto *chip : facts->childItems()) {
            QVERIFY(bounds.adjusted(-1, -1, 1, 1).contains(chip->mapRectToItem(
                group, QRectF(0, 0, chip->width(), chip->height()))));
        }
        QCOMPARE(nodeCenter(device), originalDevice);
        QCOMPARE(nodeCenter(vpn), originalVpn);
        QSignalSpy navigation(scene, SIGNAL(navigateRequested(QString)));
        QSignalSpy copied(scene, SIGNAL(copyPortRequested()));
        const auto chips = facts->childItems();
        QCOMPARE(chips.size(), 4);
        for (auto *chip : chips) {
            QVERIFY(QMetaObject::invokeMethod(chip, "clicked"));
        }
        QCOMPARE(navigation.size(), 3);
        QCOMPARE(navigation.at(0).at(0).toString(), QStringLiteral("inspector"));
        QCOMPARE(navigation.at(1).at(0).toString(), QStringLiteral("settings"));
        QCOMPARE(navigation.at(2).at(0).toString(), QStringLiteral("inspector"));
        QCOMPARE(copied.size(), 1);
    }
}

void PresentationLayoutTest::windowSizeIsOwnedByContent()
{
    QQmlEngine engine;
    QQmlComponent component(&engine);
    component.setData(R"(
        import QtQuick
        ContentSizedWindow {
            visible: true
            availableWidth: 1200; availableHeight: 1000
            preferredWidth: 860; preferredHeight: 500
        }
    )", QUrl::fromLocalFile(QStringLiteral(PROTON_VPN_KDE_SOURCE_DIR "/qml/LayoutFixture.qml")));
    QScopedPointer<QObject> root(component.create());
    QVERIFY2(root, qPrintable(component.errorString()));
    auto *window = qobject_cast<QQuickWindow *>(root.data());
    QVERIFY(window);
    QTRY_COMPARE(window->size(), QSize(860, 500));
    QCOMPARE(window->minimumSize(), window->size());
    QCOMPARE(window->maximumSize(), window->size());
    QVERIFY(!window->flags().testFlag(Qt::WindowMaximizeButtonHint));
    QVERIFY(window->flags().testFlag(Qt::WindowMinimizeButtonHint));
    root->setProperty("preferredHeight", 700);
    QTRY_COMPARE(window->height(), 700);
    QCOMPARE(window->minimumHeight(), 700);
    QCOMPARE(window->maximumHeight(), 700);
    root->setProperty("preferredHeight", 500);
    QTRY_COMPARE(window->height(), 500);
    root->setProperty("availableWidth", 600);
    root->setProperty("availableHeight", 400);
    QTRY_VERIFY(window->width() < 600 && window->height() < 400);
    QCOMPARE(window->minimumSize(), window->size());
    QCOMPARE(window->maximumSize(), window->size());
    root->setProperty("availableWidth", 1200);
    root->setProperty("availableHeight", 1000);
    QTRY_COMPARE(window->size(), QSize(860, 500));
    // Explicit diagnostic captures are fixed too, but independent of the
    // offscreen plugin's artificial monitor size.
    root->setProperty("captureWidth", 900);
    root->setProperty("captureHeight", 720);
    QTRY_COMPARE(window->size(), QSize(900, 720));
    QCOMPARE(window->minimumSize(), window->maximumSize());
}

QTEST_MAIN(PresentationLayoutTest)
#include "PresentationLayoutTest.moc"
