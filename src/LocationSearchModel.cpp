// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#include "LocationModels.h"

#include "LocationModelJson.h"

#include <QJsonArray>
#include <QJsonObject>
#include <algorithm>

using namespace ProtonVpnKde::LocationModelDetail;

LocationSearchModel::LocationSearchModel(QObject *parent)
    : QAbstractListModel(parent)
{
}

int LocationSearchModel::rowCount(const QModelIndex &parent) const
{
    return parent.isValid() ? 0 : static_cast<int>(m_entries.size());
}

QVariant LocationSearchModel::data(const QModelIndex &index, int role) const
{
    if (!index.isValid() || index.row() < 0 || index.row() >= m_entries.size()) {
        return {};
    }
    const Entry &entry = m_entries.at(index.row());
    switch (role) {
    case KindRole: return entry.kind;
    case NameRole: return entry.name;
    case CountryCodeRole: return entry.countryCode;
    case CountryNameRole: return entry.countryName;
    case CountryFlagRole: return entry.countryFlag;
    case LocationRole: return entry.location;
    case GroupKindRole: return entry.groupKind;
    case GroupNameRole: return entry.groupName;
    case LoadRole: return entry.load;
    case ServerCountRole: return entry.serverCount;
    case AccessibleRole: return entry.accessible;
    case UnderMaintenanceRole: return entry.underMaintenance;
    default: return {};
    }
}

QHash<int, QByteArray> LocationSearchModel::roleNames() const
{
    return {
        {KindRole, "kind"},
        {NameRole, "name"},
        {CountryCodeRole, "countryCode"},
        {CountryNameRole, "countryName"},
        {CountryFlagRole, "countryFlag"},
        {LocationRole, "location"},
        {GroupKindRole, "groupKind"},
        {GroupNameRole, "groupName"},
        {LoadRole, "load"},
        {ServerCountRole, "serverCount"},
        {AccessibleRole, "accessible"},
        {UnderMaintenanceRole, "underMaintenance"},
    };
}

bool LocationSearchModel::resetFromJson(const QString &json,
                                        const CountryModel &countries,
                                        const QString &query,
                                        QString *errorMessage)
{
    QJsonArray items;
    if (!parseList(json, QStringLiteral("results"), &items, errorMessage)) {
        return false;
    }

    QVector<Entry> entries;
    entries.reserve(countries.rowCount() + items.size());
    const QString needle = foldSearchText(query.simplified());
    for (int row = 0; row < countries.rowCount(); ++row) {
        const QModelIndex index = countries.index(row);
        const QString code = index.data(CountryModel::CodeRole).toString();
        const QString name = index.data(CountryModel::NameRole).toString();
        const bool underMaintenance =
            index.data(CountryModel::UnderMaintenanceRole).toBool();
        if (underMaintenance
            || (!foldSearchText(code).contains(needle)
                && !foldSearchText(name).contains(needle))) {
            continue;
        }
        entries.append({
            QStringLiteral("country"),
            name,
            code,
            name,
            index.data(CountryModel::FlagRole).toString(),
            {},
            {},
            {},
            -1,
            index.data(CountryModel::ServerCountRole).toInt(),
            index.data(CountryModel::AccessibleRole).toBool(),
            underMaintenance,
        });
    }

    for (const auto &value : items) {
        const QJsonObject item = value.toObject();
        const QString kind = item.value(QStringLiteral("kind")).toString();
        const QString name = item.value(QStringLiteral("name")).toString();
        const QString code = item.value(QStringLiteral("countryCode"))
                                 .toString().toUpper();
        if ((kind != QStringLiteral("location")
             && kind != QStringLiteral("server"))
            || name.isEmpty() || code.size() != 2) {
            continue;
        }
        entries.append({
            kind,
            name,
            code,
            countryName(code),
            countryFlag(code),
            item.value(QStringLiteral("location")).toString(),
            item.value(QStringLiteral("groupKind")).toString(
                QStringLiteral("location")),
            item.value(QStringLiteral("groupName")).toString(),
            kind == QStringLiteral("server")
                ? std::clamp(item.value(QStringLiteral("load")).toInt(), 0, 100)
                : -1,
            0,
            !item.contains(QStringLiteral("accessible"))
                || item.value(QStringLiteral("accessible")).toBool(),
            item.value(QStringLiteral("underMaintenance")).toBool(),
        });
    }

    const auto sectionRank = [](const QString &kind) {
        if (kind == QStringLiteral("country")) {
            return 0;
        }
        if (kind == QStringLiteral("location")) {
            return 1;
        }
        return 2;
    };
    std::sort(entries.begin(), entries.end(), [&sectionRank](const Entry &left,
                                                             const Entry &right) {
        const int leftRank = sectionRank(left.kind);
        const int rightRank = sectionRank(right.kind);
        if (leftRank != rightRank) {
            return leftRank < rightRank;
        }
        if (left.accessible != right.accessible) {
            return left.accessible;
        }
        return QString::localeAwareCompare(left.name, right.name) < 0;
    });

    beginResetModel();
    m_entries = std::move(entries);
    endResetModel();
    return true;
}

void LocationSearchModel::clear()
{
    if (m_entries.isEmpty()) {
        return;
    }
    beginResetModel();
    m_entries.clear();
    endResetModel();
}
