#include "LocationModels.h"

#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QHash>
#include <QLocale>
#include <algorithm>

namespace
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

CountryModel::CountryModel(QObject *parent)
    : QAbstractListModel(parent)
{
}

int CountryModel::rowCount(const QModelIndex &parent) const
{
    return parent.isValid() ? 0 : m_entries.size();
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
    for (const QJsonValue &value : items) {
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

LocationSearchModel::LocationSearchModel(QObject *parent)
    : QAbstractListModel(parent)
{
}

int LocationSearchModel::rowCount(const QModelIndex &parent) const
{
    return parent.isValid() ? 0 : m_entries.size();
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

    for (const QJsonValue &value : items) {
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

ServerModel::ServerModel(QObject *parent)
    : QAbstractListModel(parent)
{
}

int ServerModel::rowCount(const QModelIndex &parent) const
{
    return parent.isValid() ? 0 : m_entries.size();
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
    for (const QJsonValue &value : items) {
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
    for (const QJsonValue &value : items) {
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

ServerGroupModel::ServerGroupModel(QObject *parent)
    : QAbstractListModel(parent)
{
}

int ServerGroupModel::rowCount(const QModelIndex &parent) const
{
    return parent.isValid() ? 0 : m_entries.size();
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
    for (const QJsonValue &value : items) {
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
