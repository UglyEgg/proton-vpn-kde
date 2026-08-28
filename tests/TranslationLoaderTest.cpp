#include "TranslationLoader.h"

#include <QCoreApplication>
#include <QLocale>
#include <QTest>

class TranslationLoaderTest final : public QObject
{
    Q_OBJECT

private slots:
    void loadsProtonRegionalFallbackFromCompiledCatalog()
    {
        QVERIFY(TranslationLoader::install(*QCoreApplication::instance(),
                                           QLocale(QStringLiteral("es_MX"))));
        QCOMPARE(QCoreApplication::translate("CountryPage", "Upgrade"),
                 QStringLiteral("Actualizar"));
    }
};

QTEST_GUILESS_MAIN(TranslationLoaderTest)

#include "TranslationLoaderTest.moc"
