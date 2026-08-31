// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#include "LocationModelJson.h"

#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QLocale>

namespace ProtonVpnKde::LocationModelDetail
{
bool parseList(const QString &json, const QString &key, QJsonArray *items,
               QString *errorMessage)
{
    QJsonParseError parseError;
    const QJsonDocument document = QJsonDocument::fromJson(json.toUtf8(), &parseError);
    if (parseError.error != QJsonParseError::NoError || !document.isObject()) {
        if (errorMessage) {
            *errorMessage = QObject::tr("The backend returned invalid location data");
        }
        return false;
    }

    const QJsonObject root = document.object();
    if (root.value(QStringLiteral("schemaVersion")).toInt() != 1
        || !root.value(key).isArray()) {
        if (errorMessage) {
            *errorMessage = QObject::tr("The backend returned unsupported location data");
        }
        return false;
    }

    *items = root.value(key).toArray();
    return true;
}

QString countryName(const QString &code)
{
    if (code == QStringLiteral("XK")) {
        return QObject::tr("Kosovo");
    }
    const QString isoCode = code == QStringLiteral("UK")
        ? QStringLiteral("GB") : code;
    const auto territory = QLocale::codeToTerritory(isoCode);
    if (territory == QLocale::AnyTerritory) {
        return code;
    }
    const QString name = QLocale::territoryToString(territory);
    return name.isEmpty() ? code : name;
}

QString countryFlag(const QString &code)
{
    const QString upper = code.toUpper() == QStringLiteral("UK")
        ? QStringLiteral("GB") : code.toUpper();
    if (upper.size() != 2 || !upper.at(0).isLetter() || !upper.at(1).isLetter()) {
        return {};
    }
    char32_t symbols[] = {
        static_cast<char32_t>(0x1F1E6 + upper.at(0).unicode() - 'A'),
        static_cast<char32_t>(0x1F1E6 + upper.at(1).unicode() - 'A'),
    };
    return QString::fromUcs4(symbols, 2);
}

QString foldSearchText(const QString &value)
{
    QString folded;
    const QString normalized = value.normalized(QString::NormalizationForm_D)
                                   .toCaseFolded();
    folded.reserve(normalized.size());
    for (const QChar character : normalized) {
        const QChar::Category category = character.category();
        if (category != QChar::Mark_NonSpacing
            && category != QChar::Mark_SpacingCombining
            && category != QChar::Mark_Enclosing) {
            folded.append(character);
        }
    }
    return folded;
}
}
