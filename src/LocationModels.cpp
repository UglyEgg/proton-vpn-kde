#include "LocationModels.h"

#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
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
        });
    }
    std::sort(entries.begin(), entries.end(), [](const Entry &left, const Entry &right) {
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
    case LoadRole: return entry.load;
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
        {LoadRole, "load"},
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
            item.value(QStringLiteral("load")).toInt(),
            item.value(QStringLiteral("p2p")).toBool(),
            item.value(QStringLiteral("streaming")).toBool(),
        });
    }

    beginResetModel();
    m_entries = std::move(entries);
    endResetModel();
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

LocationFilterProxyModel::LocationFilterProxyModel(QObject *parent)
    : QSortFilterProxyModel(parent)
{
    setDynamicSortFilter(true);
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

bool LocationFilterProxyModel::filterAcceptsRow(
    int sourceRow, const QModelIndex &sourceParent) const
{
    if (m_filterText.isEmpty()) {
        return true;
    }
    const QModelIndex index = sourceModel()->index(sourceRow, 0, sourceParent);
    for (const int role : m_searchRoles) {
        if (index.data(role).toString().contains(m_filterText, Qt::CaseInsensitive)) {
            return true;
        }
    }
    return false;
}
