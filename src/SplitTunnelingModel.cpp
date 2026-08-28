#include "SplitTunnelingModel.h"

#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonParseError>
#include <QSet>

namespace
{
bool readBoolean(const QJsonObject &object, const QString &key, bool *value)
{
    const QJsonValue item = object.value(key);
    if (!item.isBool()) {
        return false;
    }
    *value = item.toBool();
    return true;
}

bool readCount(const QJsonObject &object, const QString &key, int *value)
{
    const QJsonValue item = object.value(key);
    if (!item.isDouble()) {
        return false;
    }
    const int count = item.toInt(-1);
    if (count < 0) {
        return false;
    }
    *value = count;
    return true;
}

bool readApplicationPaths(const QJsonObject &object, const QString &key,
                          QStringList *paths)
{
    const QJsonValue item = object.value(key);
    if (!item.isArray() || item.toArray().size() > 256) {
        return false;
    }
    QStringList parsedPaths;
    QSet<QString> seen;
    for (const QJsonValue pathValue : item.toArray()) {
        if (!pathValue.isString()) {
            return false;
        }
        const QString path = pathValue.toString();
        if (path.isEmpty() || path.size() > 4096
            || path.contains(QLatin1Char('\n'))
            || path.contains(QLatin1Char('\r')) || seen.contains(path)) {
            return false;
        }
        seen.insert(path);
        parsedPaths.append(path);
    }
    *paths = parsedPaths;
    return true;
}
}

SplitTunnelingModel::SplitTunnelingModel(QObject *parent)
    : QObject(parent)
{
}

bool SplitTunnelingModel::loaded() const { return m_loaded; }
bool SplitTunnelingModel::busy() const { return m_busy; }
QString SplitTunnelingModel::message() const { return m_message; }
bool SplitTunnelingModel::available() const { return m_available; }
bool SplitTunnelingModel::paidFeaturesAvailable() const
{
    return m_paidFeaturesAvailable;
}
bool SplitTunnelingModel::enabled() const { return m_enabled; }
QString SplitTunnelingModel::mode() const { return m_mode; }
int SplitTunnelingModel::modeIndex() const
{
    return m_mode == QStringLiteral("include") ? 1 : 0;
}
QStringList SplitTunnelingModel::selectedAppPaths() const
{
    return m_mode == QStringLiteral("include") ? m_includeAppPaths
                                                : m_excludeAppPaths;
}
int SplitTunnelingModel::selectedIpRangeCount() const
{
    return m_mode == QStringLiteral("include") ? m_includeIpRangeCount
                                                : m_excludeIpRangeCount;
}
QStringList SplitTunnelingModel::excludeAppPaths() const
{
    return m_excludeAppPaths;
}
QStringList SplitTunnelingModel::includeAppPaths() const
{
    return m_includeAppPaths;
}

bool SplitTunnelingModel::containsApplication(const QString &executable) const
{
    return selectedAppPaths().contains(executable);
}

bool SplitTunnelingModel::applyJson(const QString &settingsJson,
                                    QString *errorMessage)
{
    const auto fail = [errorMessage](const QString &message) {
        if (errorMessage) {
            *errorMessage = message;
        }
        return false;
    };
    if (settingsJson.size() > 1024 * 1024) {
        return fail(tr("The backend returned oversized split-tunneling settings"));
    }

    QJsonParseError parseError;
    const QJsonDocument document = QJsonDocument::fromJson(
        settingsJson.toUtf8(), &parseError);
    if (parseError.error != QJsonParseError::NoError || !document.isObject()) {
        return fail(tr("The backend returned invalid split-tunneling settings"));
    }

    const QJsonObject object = document.object();
    if (object.value(QStringLiteral("schemaVersion")).toInt() != 1) {
        return fail(tr("The backend uses an unsupported split-tunneling version"));
    }
    const QString mode = object.value(QStringLiteral("mode")).toString();
    if (mode != QStringLiteral("exclude") && mode != QStringLiteral("include")) {
        return fail(tr("The backend returned an invalid split-tunneling mode"));
    }

    bool available = false;
    bool paidFeaturesAvailable = false;
    bool enabled = false;
    int excludeIpRangeCount = 0;
    int includeIpRangeCount = 0;
    QStringList excludeAppPaths;
    QStringList includeAppPaths;
    if (!readBoolean(object, QStringLiteral("available"), &available)
        || !readBoolean(object, QStringLiteral("paidFeaturesAvailable"),
                        &paidFeaturesAvailable)
        || !readBoolean(object, QStringLiteral("enabled"), &enabled)
        || !readApplicationPaths(object, QStringLiteral("excludeAppPaths"),
                                 &excludeAppPaths)
        || !readApplicationPaths(object, QStringLiteral("includeAppPaths"),
                                 &includeAppPaths)
        || !readCount(object, QStringLiteral("excludeIpRangeCount"),
                      &excludeIpRangeCount)
        || !readCount(object, QStringLiteral("includeIpRangeCount"),
                      &includeIpRangeCount)) {
        return fail(tr("The backend returned incomplete split-tunneling settings"));
    }

    m_available = available;
    m_paidFeaturesAvailable = paidFeaturesAvailable;
    m_enabled = enabled;
    m_mode = mode;
    m_excludeAppPaths = excludeAppPaths;
    m_includeAppPaths = includeAppPaths;
    m_excludeIpRangeCount = excludeIpRangeCount;
    m_includeIpRangeCount = includeIpRangeCount;
    m_loaded = true;
    m_busy = false;
    m_message.clear();
    emit changed();
    return true;
}

void SplitTunnelingModel::reset(const QString &message)
{
    m_loaded = false;
    m_busy = false;
    m_message = message;
    m_available = false;
    m_enabled = false;
    m_excludeAppPaths.clear();
    m_includeAppPaths.clear();
    m_excludeIpRangeCount = 0;
    m_includeIpRangeCount = 0;
    emit changed();
}

void SplitTunnelingModel::setBusy(bool busy)
{
    if (m_busy == busy) {
        return;
    }
    m_busy = busy;
    emit changed();
}

void SplitTunnelingModel::setMessage(const QString &message)
{
    if (m_message == message) {
        return;
    }
    m_message = message;
    emit changed();
}
