// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#include "LocationModels.h"

#include "LocationModelJson.h"

#include <QJsonArray>
#include <QJsonObject>
#include <algorithm>

using namespace ProtonVpnKde::LocationModelDetail;

CountryModel::CountryModel(QObject *parent)
    : QAbstractListModel(parent)
{
}

int CountryModel::rowCount(const QModelIndex &parent) const
{
    return parent.isValid() ? 0 : static_cast<int>(m_entries.size());
}

QVariant CountryModel::data(const QModelIndex &index, int role) const
{
    if (!index.isValid() || index.row() < 0 || index.row() >= m_entries.size()) {
        return {};
    }
    const Entry &entry = m_entries.at(index.row());
    switch (role) {
    case CodeRole: return entry.code;
    case NameRole: return entry.name;
    case FlagRole: return entry.flag;
    case ServerCountRole: return entry.serverCount;
    case AccessibleRole: return entry.accessible;
    case UnderMaintenanceRole: return entry.underMaintenance;
    case FreeRole: return entry.free;
    default: return {};
    }
}

QHash<int, QByteArray> CountryModel::roleNames() const
{
    return {
        {CodeRole, "code"},
        {NameRole, "name"},
        {FlagRole, "flag"},
        {ServerCountRole, "serverCount"},
        {AccessibleRole, "accessible"},
        {UnderMaintenanceRole, "underMaintenance"},
        {FreeRole, "free"},
    };
}

bool CountryModel::resetFromJson(const QString &json, QString *errorMessage)
{
    QJsonArray items;
    if (!parseList(json, QStringLiteral("countries"), &items, errorMessage)) {
        return false;
    }

    QVector<Entry> entries;
    entries.reserve(items.size());
    for (const auto &value : items) {
        const QJsonObject item = value.toObject();
        const QString code = item.value(QStringLiteral("code")).toString().toUpper();
        if (code.size() != 2) {
            continue;
        }
        entries.append({
            code,
            countryName(code),
            countryFlag(code),
            item.value(QStringLiteral("serverCount")).toInt(),
            !item.contains(QStringLiteral("accessible"))
                || item.value(QStringLiteral("accessible")).toBool(),
            item.value(QStringLiteral("underMaintenance")).toBool(),
            item.value(QStringLiteral("free")).toBool(),
        });
    }
    std::sort(entries.begin(), entries.end(), [](const Entry &left, const Entry &right) {
        if (left.accessible != right.accessible) {
            return left.accessible;
        }
        if (left.underMaintenance != right.underMaintenance) {
            return !left.underMaintenance;
        }
        return QString::localeAwareCompare(left.name, right.name) < 0;
    });

    beginResetModel();
    m_entries = std::move(entries);
    endResetModel();
    return true;
}

void CountryModel::clear()
{
    if (m_entries.isEmpty()) {
        return;
    }
    beginResetModel();
    m_entries.clear();
    endResetModel();
}
