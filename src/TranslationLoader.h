#pragma once

class QCoreApplication;
class QLocale;

namespace TranslationLoader
{
[[nodiscard]] bool install(QCoreApplication &application,
                           const QLocale &locale);
void installSystemLocale(QCoreApplication &application);
}
