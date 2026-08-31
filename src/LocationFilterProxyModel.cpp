// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#include "LocationModels.h"

LocationFilterProxyModel::LocationFilterProxyModel(QObject *parent)
    : QSortFilterProxyModel(parent)
{
    setDynamicSortFilter(true);
    setSortCaseSensitivity(Qt::CaseInsensitive);
    setSortLocaleAware(true);
}

QString LocationFilterProxyModel::filterText() const
{
    return m_filterText;
}

void LocationFilterProxyModel::setFilterText(const QString &filterText)
{
    const QString simplified = filterText.simplified();
    if (m_filterText == simplified) {
        return;
    }
    beginFilterChange();
    m_filterText = simplified;
    endFilterChange(QSortFilterProxyModel::Direction::Rows);
    emit filterTextChanged();
}

void LocationFilterProxyModel::setSearchRoles(const QList<int> &roles)
{
    beginFilterChange();
    m_searchRoles = roles;
    endFilterChange(QSortFilterProxyModel::Direction::Rows);
}

void LocationFilterProxyModel::setAvailabilityRoles(int accessibleRole,
                                                    int maintenanceRole)
{
    m_accessibleRole = accessibleRole;
    m_maintenanceRole = maintenanceRole;
    invalidate();
}

void LocationFilterProxyModel::setFeatureRoles(
    const QHash<QString, int> &roles)
{
    beginFilterChange();
    m_featureRoles = roles;
    endFilterChange(QSortFilterProxyModel::Direction::Rows);
}

void LocationFilterProxyModel::setRequiredFeatures(
    const QStringList &features)
{
    QStringList normalized;
    for (const QString &feature : features) {
        const QString candidate = feature.trimmed().toLower();
        if (m_featureRoles.contains(candidate)
            && !normalized.contains(candidate)) {
            normalized.append(candidate);
        }
    }
    if (m_requiredFeatures == normalized) {
        return;
    }
    beginFilterChange();
    m_requiredFeatures = normalized;
    endFilterChange(QSortFilterProxyModel::Direction::Rows);
}

void LocationFilterProxyModel::sortByRole(int role, Qt::SortOrder order)
{
    setSortRole(role);
    sort(0, order);
}

bool LocationFilterProxyModel::filterAcceptsRow(
    int sourceRow, const QModelIndex &sourceParent) const
{
    const QModelIndex index = sourceModel()->index(sourceRow, 0, sourceParent);
    if (!m_filterText.isEmpty()) {
        bool textMatches = false;
        for (const int role : m_searchRoles) {
            if (index.data(role).toString().contains(
                    m_filterText, Qt::CaseInsensitive)) {
                textMatches = true;
                break;
            }
        }
        if (!textMatches) {
            return false;
        }
    }
    for (const QString &feature : m_requiredFeatures) {
        if (!index.data(m_featureRoles.value(feature)).toBool()) {
            return false;
        }
    }
    return true;
}

bool LocationFilterProxyModel::lessThan(const QModelIndex &sourceLeft,
                                        const QModelIndex &sourceRight) const
{
    if (m_accessibleRole >= 0) {
        const bool leftAccessible = sourceLeft.data(m_accessibleRole).toBool();
        const bool rightAccessible = sourceRight.data(m_accessibleRole).toBool();
        if (leftAccessible != rightAccessible) {
            return leftAccessible;
        }
    }
    if (m_maintenanceRole >= 0) {
        const bool leftMaintenance = sourceLeft.data(m_maintenanceRole).toBool();
        const bool rightMaintenance = sourceRight.data(m_maintenanceRole).toBool();
        if (leftMaintenance != rightMaintenance) {
            return !leftMaintenance;
        }
    }
    return QSortFilterProxyModel::lessThan(sourceLeft, sourceRight);
}
