#pragma once

#include <QAbstractListModel>
#include <QSortFilterProxyModel>
#include <QVector>

class CountryModel final : public QAbstractListModel
{
    Q_OBJECT

public:
    enum Role {
        CodeRole = Qt::UserRole + 1,
        NameRole,
        FlagRole,
        ServerCountRole,
    };

    explicit CountryModel(QObject *parent = nullptr);

    [[nodiscard]] int rowCount(const QModelIndex &parent = {}) const override;
    [[nodiscard]] QVariant data(const QModelIndex &index, int role) const override;
    [[nodiscard]] QHash<int, QByteArray> roleNames() const override;

    bool resetFromJson(const QString &json, QString *errorMessage = nullptr);
    void clear();

private:
    struct Entry {
        QString code;
        QString name;
        QString flag;
        int serverCount = 0;
    };

    QVector<Entry> m_entries;
};

class ServerModel final : public QAbstractListModel
{
    Q_OBJECT

public:
    enum Role {
        NameRole = Qt::UserRole + 1,
        LocationRole,
        LoadRole,
        P2pRole,
        StreamingRole,
    };

    explicit ServerModel(QObject *parent = nullptr);

    [[nodiscard]] int rowCount(const QModelIndex &parent = {}) const override;
    [[nodiscard]] QVariant data(const QModelIndex &index, int role) const override;
    [[nodiscard]] QHash<int, QByteArray> roleNames() const override;

    bool resetFromJson(const QString &json, QString *errorMessage = nullptr);
    void clear();

private:
    struct Entry {
        QString name;
        QString location;
        int load = 0;
        bool p2p = false;
        bool streaming = false;
    };

    QVector<Entry> m_entries;
};

class LocationFilterProxyModel final : public QSortFilterProxyModel
{
    Q_OBJECT
    Q_PROPERTY(QString filterText READ filterText WRITE setFilterText NOTIFY filterTextChanged)

public:
    explicit LocationFilterProxyModel(QObject *parent = nullptr);

    [[nodiscard]] QString filterText() const;
    void setFilterText(const QString &filterText);
    void setSearchRoles(const QList<int> &roles);

signals:
    void filterTextChanged();

protected:
    [[nodiscard]] bool filterAcceptsRow(
        int sourceRow, const QModelIndex &sourceParent) const override;

private:
    QString m_filterText;
    QList<int> m_searchRoles;
};
