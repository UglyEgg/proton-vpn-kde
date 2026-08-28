#include "InstalledApplicationModel.h"

#include <KApplicationTrader>
#include <KService>
#include <KShell>

#include <algorithm>
#include <limits>

#include <QCollator>
#include <QDir>
#include <QFileInfo>
#include <QHash>
#include <QRegularExpression>
#include <QStandardPaths>

namespace
{
int fixedArgumentCount(const QString &execLine)
{
    KShell::Errors parseError = KShell::NoError;
    const QStringList arguments = KShell::splitArgs(
        execLine.trimmed(), KShell::AbortOnMeta, &parseError);
    if (parseError != KShell::NoError || arguments.isEmpty()) {
        return std::numeric_limits<int>::max();
    }

    int count = 0;
    for (qsizetype index = 1; index < arguments.size(); ++index) {
        const QString &argument = arguments.at(index);
        if (!argument.startsWith(QLatin1Char('%'))
            && !argument.startsWith(QStringLiteral("@@"))) {
            ++count;
        }
    }
    return count;
}

int desktopIdPenalty(const KService::Ptr &service,
                     const QString &executable)
{
    const QString desktopId = service->desktopEntryName().section(
        QLatin1Char('.'), -1);
    const QString commandName = QFileInfo(
        QDir::cleanPath(executable)).fileName();
    return desktopId.compare(commandName, Qt::CaseInsensitive) == 0 ? 0 : 1;
}
}

InstalledApplicationModel::InstalledApplicationModel(QObject *parent)
    : QAbstractListModel(parent)
{
    reload();
}

int InstalledApplicationModel::rowCount(const QModelIndex &parent) const
{
    return parent.isValid() ? 0 : m_applications.size();
}

QVariant InstalledApplicationModel::data(const QModelIndex &index, int role) const
{
    if (!index.isValid() || index.row() < 0
        || index.row() >= m_applications.size()) {
        return {};
    }
    const Application &application = m_applications.at(index.row());
    switch (role) {
    case Qt::DisplayRole:
    case NameRole:
        return application.name;
    case ExecutableRole:
        return application.executable;
    case IconNameRole:
        return application.iconName;
    case DesktopIdRole:
        return application.desktopId;
    case CommentRole:
        return application.comment;
    default:
        return {};
    }
}

QHash<int, QByteArray> InstalledApplicationModel::roleNames() const
{
    return {
        {NameRole, "applicationName"},
        {ExecutableRole, "executable"},
        {IconNameRole, "iconName"},
        {DesktopIdRole, "desktopId"},
        {CommentRole, "applicationComment"},
    };
}

void InstalledApplicationModel::reload()
{
    QList<Application> applications;
    QHash<QString, qsizetype> executableIndexes;
    QHash<QString, QPair<int, int>> executableScores;
    const KService::List services = KApplicationTrader::query(
        [](const KService::Ptr &service) {
            return service && service->isApplication() && !service->noDisplay()
                && !service->exec().trimmed().isEmpty();
        });
    for (const KService::Ptr &service : services) {
        const QString executable = executableFromExecLine(service->exec());
        const QString name = service->name().trimmed();
        if (name.isEmpty() || executable.isEmpty()
            || !isSafeVpnApplicationChoice(executable)) {
            continue;
        }

        const QPair<int, int> score{
            fixedArgumentCount(service->exec()),
            desktopIdPenalty(service, executable),
        };
        const auto existing = executableIndexes.constFind(executable);
        if (existing != executableIndexes.cend()
            && executableScores.value(executable) <= score) {
            continue;
        }

        const Application application{
            name,
            executable,
            service->icon().trimmed(),
            service->desktopEntryName().trimmed(),
            service->comment().trimmed(),
        };
        if (existing == executableIndexes.cend()) {
            executableIndexes.insert(executable, applications.size());
            applications.append(application);
        } else {
            applications[existing.value()] = application;
        }
        executableScores.insert(executable, score);
    }

    QCollator collator;
    collator.setCaseSensitivity(Qt::CaseInsensitive);
    collator.setNumericMode(true);
    std::sort(applications.begin(), applications.end(),
              [&collator](const Application &left, const Application &right) {
                  const int nameOrder = collator.compare(left.name, right.name);
                  return nameOrder != 0
                      ? nameOrder < 0
                      : left.executable < right.executable;
              });

    beginResetModel();
    m_applications = applications;
    endResetModel();
}

QString InstalledApplicationModel::nameForExecutable(
    const QString &executable) const
{
    for (const Application &application : m_applications) {
        if (application.executable == executable) {
            return application.name;
        }
    }
    const QString command = executable.section(QLatin1Char(' '), 0, 0);
    const QString fallback = QFileInfo(command).fileName();
    return fallback.isEmpty() ? executable : fallback;
}

QString InstalledApplicationModel::executableFromExecLine(
    const QString &execLine)
{
    QString normalized = execLine.trimmed();
    if (normalized.isEmpty() || normalized.size() > 16384) {
        return {};
    }

    KShell::Errors parseError = KShell::NoError;
    const QStringList arguments = KShell::splitArgs(
        normalized, KShell::AbortOnMeta, &parseError);
    if (parseError != KShell::NoError || arguments.isEmpty()) {
        return {};
    }
    const QString command = arguments.constFirst();
    const QString commandName = QFileInfo(command).fileName();

    if (commandName == QStringLiteral("flatpak")) {
        static const QRegularExpression forwardingMarker(
            QStringLiteral(R"(\s+@@)"));
        const QRegularExpressionMatch marker = forwardingMarker.match(normalized);
        if (marker.hasMatch()) {
            normalized.truncate(marker.capturedStart());
        }
        return normalized.trimmed();
    }

    if (command.startsWith(QStringLiteral("/snap/bin/"))) {
        const QString appName = command.mid(QStringLiteral("/snap/bin/").size())
                                    .section(QLatin1Char('.'), 0, 0);
        if (appName.isEmpty()) {
            return {};
        }
        return QStringLiteral("/snap/%1/").arg(appName);
    }

    if (QFileInfo(command).isAbsolute()) {
        return QDir::cleanPath(command);
    }
    return QStandardPaths::findExecutable(command);
}

bool InstalledApplicationModel::isSafeVpnApplicationChoice(
    const QString &executable)
{
    if (executable.isEmpty() || executable == QStringLiteral("/")) {
        return false;
    }
    const QString lowered = executable.toCaseFolded();
    return !lowered.contains(QStringLiteral("proton-vpn-kde"))
        && !lowered.contains(QStringLiteral("protonvpn-app"));
}
