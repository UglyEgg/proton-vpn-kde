// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#pragma once

class QCoreApplication;
class QLocale;

namespace TranslationLoader
{
[[nodiscard]] bool install(QCoreApplication &application,
                           const QLocale &locale);
void installSystemLocale(QCoreApplication &application);
}
