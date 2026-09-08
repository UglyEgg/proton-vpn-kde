// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#include <QDir>
#include <QQmlComponent>
#include <QQmlContext>
#include <QQmlEngine>
#include <QQuickItem>
#include <QQuickWindow>
#include <QScopeGuard>
#include <QScopedPointer>
#include <QSignalSpy>
#include <QtTest>

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

private:
    void capture(QQuickWindow *window);
};

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
    QTest::newRow("split-wide") << 900 << true << true;
    QTest::newRow("split-compact") << 460 << true << true;
    QTest::newRow("full-compact") << 460 << true << false;
    QTest::newRow("inactive") << 460 << false << true;
}

void PresentationLayoutTest::splitRouteIsConditionalAndNavigable()
{
    QFETCH(int, viewportWidth);
    QFETCH(bool, connected);
    QFETCH(bool, splitEnabled);
    QQmlEngine engine;
    engine.rootContext()->setContextProperty(QStringLiteral("viewportWidth"), viewportWidth);
    engine.rootContext()->setContextProperty(QStringLiteral("testConnected"), connected);
    engine.rootContext()->setContextProperty(QStringLiteral("testSplit"), splitEnabled);
    QQmlComponent component(&engine);
    component.setData(R"(
        import QtQuick
        import QtQuick.Controls
        ApplicationWindow {
            width: viewportWidth; height: 720; visible: true
            ConnectionScene {
                objectName: "scene"
                width: parent.width
                connected: testConnected; splitTunneling: testSplit
                stateText: testConnected ? "Protected" : "Not connected"
                loggedIn: true; ready: true; accountName: "demo-user"
                destinationName: "Illinois"; destinationFlag: "US"
                serverName: "US-IL#1018"; protocolName: "Smart"
                primaryText: testConnected ? "Disconnect" : "Connect"
            }
        }
    )", QUrl::fromLocalFile(QStringLiteral(PROTON_VPN_KDE_SOURCE_DIR "/qml/LayoutFixture.qml")));
    QScopedPointer<QObject> root(component.create());
    QVERIFY2(root, qPrintable(component.errorString()));
    auto *window = qobject_cast<QQuickWindow *>(root.data());
    auto *scene = root->findChild<QQuickItem *>(QStringLiteral("scene"));
    auto *cloud = root->findChild<QQuickItem *>(QStringLiteral("splitInternetRoute"));
    QVERIFY(window && scene && cloud);
    QTRY_VERIFY(scene->height() > 0);
    QTest::qWait(50);
    QCOMPARE(cloud->isVisible(), connected && splitEnabled);
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
}

QTEST_MAIN(PresentationLayoutTest)
#include "PresentationLayoutTest.moc"
