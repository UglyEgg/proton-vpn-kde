// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#pragma once

#include <QString>

class QJsonArray;

namespace ProtonVpnKde::LocationModelDetail
{
bool parseList(const QString &json, const QString &key, QJsonArray *items,
               QString *errorMessage);
QString countryName(const QString &code);
QString countryFlag(const QString &code);
QString foldSearchText(const QString &value);
}
