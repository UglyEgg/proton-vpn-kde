// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#include "LocationModels.h"

#include "LocationModelJson.h"

#include <QJsonArray>
#include <QJsonObject>

using ProtonVpnKde::LocationModelDetail::parseList;

ServerGroupModel::ServerGroupModel(QObject *parent)
    : QAbstractListModel(parent)
{
}

int ServerGroupModel::rowCount(const QModelIndex &parent) const
{
    return parent.isValid() ? 0 : static_cast<int>(m_entries.size());
}

QVariant ServerGroupModel::data(const QModelIndex &index, int role) const
{
    if (!index.isValid() || index.row() < 0 || index.row() >= m_entries.size()) {
        return {};
    }
    const Entry &entry = m_entries.at(index.row());
    switch (role) {
    case KindRole: return entry.kind;
    case NameRole: return entry.name;
    case ServerCountRole: return entry.serverCount;
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

QHash<int, QByteArray> ServerGroupModel::roleNames() const
{
    return {
        {KindRole, "kind"},
        {NameRole, "name"},
        {ServerCountRole, "serverCount"},
        {AccessibleRole, "accessible"},
        {UnderMaintenanceRole, "underMaintenance"},
        {SmartRoutingRole, "smartRouting"},
        {SecureCoreRole, "secureCore"},
        {TorRole, "tor"},
        {P2pRole, "p2p"},
        {StreamingRole, "streaming"},
    };
}

bool ServerGroupModel::resetFromJson(const QString &json, QString *errorMessage)
{
    QJsonArray items;
    if (!parseList(json, QStringLiteral("groups"), &items, errorMessage)) {
        return false;
    }

    QVector<Entry> entries;
    entries.reserve(items.size());
    for (const auto &value : items) {
        const QJsonObject item = value.toObject();
        const QString kind = item.value(QStringLiteral("kind")).toString();
        const QString name = item.value(QStringLiteral("name")).toString();
        if ((kind != QStringLiteral("location")
             && kind != QStringLiteral("secure-core")) || name.isEmpty()) {
            continue;
        }
        entries.append({
            kind,
            name,
            item.value(QStringLiteral("serverCount")).toInt(),
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

void ServerGroupModel::clear()
{
    if (m_entries.isEmpty()) {
        return;
    }
    beginResetModel();
    m_entries.clear();
    endResetModel();
}
