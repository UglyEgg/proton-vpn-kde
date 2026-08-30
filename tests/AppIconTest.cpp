// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#include "AppIcon.h"

#include <QIcon>
#include <QImage>
#include <QPixmap>
#include <QSize>
#include <QtTest>

class AppIconTest final : public QObject
{
    Q_OBJECT

private slots:
    void embeddedIconDoesNotDependOnDesktopTheme();
    void embeddedStylesAreSelectable_data();
    void embeddedStylesAreSelectable();
    void monochromeStylesAreDistinct();
};

void AppIconTest::embeddedIconDoesNotDependOnDesktopTheme()
{
    QIcon::setThemeName(QStringLiteral("plasma-vpn-empty-test-theme"));

    const QIcon icon = ProtonVpnKde::applicationIcon();
    QVERIFY(!icon.isNull());

    const QPixmap pixmap = icon.pixmap(QSize(64, 64));
    QVERIFY(!pixmap.isNull());
    QCOMPARE(pixmap.size(), QSize(64, 64));
}

void AppIconTest::embeddedStylesAreSelectable_data()
{
    QTest::addColumn<QString>("style");
    QTest::addColumn<QString>("source");

    QTest::newRow("color")
        << QStringLiteral("color")
        << QStringLiteral(":/data/plasma-vpn.svg");
    QTest::newRow("light")
        << QStringLiteral("light")
        << QStringLiteral(":/data/plasma-vpn-light.svg");
    QTest::newRow("dark")
        << QStringLiteral("dark")
        << QStringLiteral(":/data/plasma-vpn-dark.svg");
    QTest::newRow("invalid-falls-back-to-color")
        << QStringLiteral("invalid")
        << QStringLiteral(":/data/plasma-vpn.svg");
}

void AppIconTest::embeddedStylesAreSelectable()
{
    QFETCH(QString, style);
    QFETCH(QString, source);

    QCOMPARE(ProtonVpnKde::applicationIconSource(style), source);
    const QPixmap pixmap = ProtonVpnKde::applicationIcon(style).pixmap(
        QSize(64, 64));
    QVERIFY(!pixmap.isNull());
    QCOMPARE(pixmap.size(), QSize(64, 64));
}

void AppIconTest::monochromeStylesAreDistinct()
{
    const QImage light = ProtonVpnKde::applicationIcon(
        QStringLiteral("light")).pixmap(QSize(64, 64)).toImage();
    const QImage dark = ProtonVpnKde::applicationIcon(
        QStringLiteral("dark")).pixmap(QSize(64, 64)).toImage();

    QVERIFY(!light.isNull());
    QVERIFY(!dark.isNull());
    QVERIFY(light != dark);
}

QTEST_MAIN(AppIconTest)

#include "AppIconTest.moc"
