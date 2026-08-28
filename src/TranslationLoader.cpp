#include "TranslationLoader.h"

#include <QCoreApplication>
#include <QLibraryInfo>
#include <QLocale>
#include <QStringList>
#include <QTranslator>
#include <QVariant>

namespace
{
constexpr auto installedProperty = "protonVpnKdeTranslationsInstalled";

bool loadCatalog(QCoreApplication &application, const QLocale &locale,
                 const QString &catalog, const QString &directory)
{
    auto *translator = new QTranslator(&application);
    if (!translator->load(locale, catalog, QStringLiteral("_"), directory)) {
        delete translator;
        return false;
    }
    application.installTranslator(translator);
    return true;
}

bool loadCatalogFile(QCoreApplication &application, const QString &fileName,
                     const QString &directory)
{
    auto *translator = new QTranslator(&application);
    if (!translator->load(fileName, directory)) {
        delete translator;
        return false;
    }
    application.installTranslator(translator);
    return true;
}

QString regionalFallback(const QLocale &locale)
{
    if (locale.language() == QLocale::Spanish
        && locale.territory() != QLocale::Spain) {
        return QStringLiteral("es_LA");
    }
    return {};
}
}

bool TranslationLoader::install(QCoreApplication &application,
                                const QLocale &locale)
{
    const QVariant previousResult = application.property(installedProperty);
    if (previousResult.isValid()) {
        return previousResult.toBool();
    }

    loadCatalog(application, locale, QStringLiteral("qtbase"),
                QLibraryInfo::path(QLibraryInfo::TranslationsPath));

    QStringList directories{
        QStringLiteral(PROTON_VPN_KDE_BUILD_TRANSLATIONS_DIR),
        QStringLiteral(PROTON_VPN_KDE_INSTALL_TRANSLATIONS_DIR),
    };
    directories.removeDuplicates();

    bool loaded = false;
    for (const QString &directory : directories) {
        if (loadCatalog(application, locale, QStringLiteral("proton-vpn-kde"),
                        directory)) {
            loaded = true;
            break;
        }
        const QString fallback = regionalFallback(locale);
        if (!fallback.isEmpty()
            && loadCatalogFile(application,
                               QStringLiteral("proton-vpn-kde_%1.qm").arg(fallback),
                               directory)) {
            loaded = true;
            break;
        }
    }
    application.setProperty(installedProperty, loaded);
    return loaded;
}

void TranslationLoader::installSystemLocale(QCoreApplication &application)
{
    static_cast<void>(install(application, QLocale::system()));
}
