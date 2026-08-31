// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#include "LocationModels.h"

#include "LocationModelJson.h"

#include <QJsonArray>
#include <QJsonObject>
#include <algorithm>

using ProtonVpnKde::LocationModelDetail::parseList;

ServerModel::ServerModel(QObject *parent)
    : QAbstractListModel(parent)
{
}

int ServerModel::rowCount(const QModelIndex &parent) const
{
    return parent.isValid() ? 0 : static_cast<int>(m_entries.size());
}

QVariant ServerModel::data(const QModelIndex &index, int role) const
{
    if (!index.isValid() || index.row() < 0 || index.row() >= m_entries.size()) {
        return {};
    }
    const Entry &entry = m_entries.at(index.row());
    switch (role) {
    case NameRole: return entry.name;
    case LocationRole: return entry.location;
    case EntryCountryRole: return entry.entryCountry;
    case LoadRole: return entry.load;
    case AccessibleRole: return entry.accessible;
    case UnderMaintenanceRole: return entry.underMaintenance;
    case SmartRoutingRole: return entry.smartRouting;
    case SecureCoreRole: return entry.secureCore;
    case TorRole: return entry.tor;
    case P2pRole: return entry.p2p;
    case StreamingRole: return entry.streaming;
    default: return {};
    }
}

QHash<int, QByteArray> ServerModel::roleNames() const
{
    return {
        {NameRole, "name"},
        {LocationRole, "location"},
        {EntryCountryRole, "entryCountry"},
        {LoadRole, "load"},
        {AccessibleRole, "accessible"},
        {UnderMaintenanceRole, "underMaintenance"},
        {SmartRoutingRole, "smartRouting"},
        {SecureCoreRole, "secureCore"},
        {TorRole, "tor"},
        {P2pRole, "p2p"},
        {StreamingRole, "streaming"},
    };
}

bool ServerModel::resetFromJson(const QString &json, QString *errorMessage)
{
    QJsonArray items;
    if (!parseList(json, QStringLiteral("servers"), &items, errorMessage)) {
        return false;
    }

    QVector<Entry> entries;
    entries.reserve(items.size());
    for (const auto &value : items) {
        const QJsonObject item = value.toObject();
        const QString name = item.value(QStringLiteral("name")).toString();
        if (name.isEmpty()) {
            continue;
        }
        entries.append({
            name,
            item.value(QStringLiteral("location")).toString(),
            item.value(QStringLiteral("entryCountry")).toString(),
            std::clamp(item.value(QStringLiteral("load")).toInt(), 0, 100),
            !item.contains(QStringLiteral("accessible"))
                || item.value(QStringLiteral("accessible")).toBool(),
            item.value(QStringLiteral("underMaintenance")).toBool(),
            item.value(QStringLiteral("smartRouting")).toBool(),
            item.value(QStringLiteral("secureCore")).toBool(),
            item.value(QStringLiteral("tor")).toBool(),
            item.value(QStringLiteral("p2p")).toBool(),
            item.value(QStringLiteral("streaming")).toBool(),
        });
    }

    beginResetModel();
    m_entries = std::move(entries);
    endResetModel();
    return true;
}

bool ServerModel::updateLoadsFromJson(const QString &json, QString *errorMessage)
{
    QJsonArray items;
    if (!parseList(json, QStringLiteral("loads"), &items, errorMessage)) {
        return false;
    }

    QHash<QString, int> loads;
    loads.reserve(items.size());
    for (const auto &value : items) {
        const QJsonObject item = value.toObject();
        const QString name = item.value(QStringLiteral("name")).toString();
        if (!name.isEmpty()) {
            loads.insert(
                name,
                std::clamp(item.value(QStringLiteral("load")).toInt(), 0, 100));
        }
    }

    for (int row = 0; row < m_entries.size(); ++row) {
        Entry &entry = m_entries[row];
        const auto load = loads.constFind(entry.name);
        if (load == loads.cend() || entry.load == *load) {
            continue;
        }
        entry.load = *load;
        const QModelIndex changed = index(row);
        emit dataChanged(changed, changed, {LoadRole});
    }
    return true;
}

void ServerModel::clear()
{
    if (m_entries.isEmpty()) {
        return;
    }
    beginResetModel();
    m_entries.clear();
    endResetModel();
}
