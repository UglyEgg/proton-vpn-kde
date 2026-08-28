#pragma once

#include <QAbstractListModel>
#include <QString>

class InstalledApplicationModel final : public QAbstractListModel
{
    Q_OBJECT

public:
    enum Role {
        NameRole = Qt::UserRole + 1,
        ExecutableRole,
        IconNameRole,
        DesktopIdRole,
        CommentRole,
    };
    Q_ENUM(Role)

    explicit InstalledApplicationModel(QObject *parent = nullptr);

    [[nodiscard]] int rowCount(
        const QModelIndex &parent = QModelIndex()) const override;
    [[nodiscard]] QVariant data(const QModelIndex &index,
                                int role = Qt::DisplayRole) const override;
    [[nodiscard]] QHash<int, QByteArray> roleNames() const override;

    Q_INVOKABLE void reload();
    Q_INVOKABLE QString nameForExecutable(const QString &executable) const;

    static QString executableFromExecLine(const QString &execLine);
    static bool isSafeVpnApplicationChoice(const QString &executable);

private:
    struct Application {
        QString name;
        QString executable;
        QString iconName;
        QString desktopId;
        QString comment;
    };

    QList<Application> m_applications;
};
