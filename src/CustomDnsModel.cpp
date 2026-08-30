#include "CustomDnsModel.h"

#include <QHostAddress>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonParseError>
#include <QVariantMap>

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
}

CustomDnsModel::CustomDnsModel(QObject *parent)
    : QObject(parent)
{
}

bool CustomDnsModel::loaded() const { return m_loaded; }
bool CustomDnsModel::busy() const { return m_busy; }
QString CustomDnsModel::message() const { return m_message; }
bool CustomDnsModel::paidFeaturesAvailable() const
{
    return m_paidFeaturesAvailable;
}
bool CustomDnsModel::enabled() const { return m_enabled; }
QVariantList CustomDnsModel::servers() const { return m_servers; }
int CustomDnsModel::serverCount() const
{
    return static_cast<int>(m_servers.size());
}
bool CustomDnsModel::restartRequired() const { return m_restartRequired; }

QString CustomDnsModel::normalizeServerAddress(const QString &address)
{
    const QString candidate = address.trimmed();
    if (candidate.isEmpty() || candidate.size() > 64) {
        return {};
    }
    QHostAddress parsed;
    if (!parsed.setAddress(candidate) || !parsed.scopeId().isEmpty()) {
        return {};
    }
    return parsed.toString();
}

bool CustomDnsModel::containsServer(const QString &address) const
{
    const QString normalized = normalizeServerAddress(address);
    if (normalized.isEmpty()) {
        return false;
    }
    for (const QVariant &serverValue : m_servers) {
        const QString existing = serverValue.toMap().value(
            QStringLiteral("address")).toString();
        if (normalizeServerAddress(existing) == normalized) {
            return true;
        }
    }
    return false;
}

bool CustomDnsModel::isValidServerAddress(const QString &address) const
{
    return !normalizeServerAddress(address).isEmpty();
}

bool CustomDnsModel::applyJson(const QString &settingsJson,
                               QString *errorMessage)
{
    const auto fail = [errorMessage](const QString &message) {
        if (errorMessage) {
            *errorMessage = message;
        }
        return false;
    };
    if (settingsJson.size() > qsizetype{256} * 1024) {
        return fail(tr("The backend returned oversized custom-DNS settings"));
    }

    QJsonParseError parseError;
    const QJsonDocument document = QJsonDocument::fromJson(
        settingsJson.toUtf8(), &parseError);
    if (parseError.error != QJsonParseError::NoError || !document.isObject()) {
        return fail(tr("The backend returned invalid custom-DNS settings"));
    }

    const QJsonObject object = document.object();
    if (object.value(QStringLiteral("schemaVersion")).toInt() != 1) {
        return fail(tr("The backend uses an unsupported custom-DNS version"));
    }
    const QJsonValue serversValue = object.value(QStringLiteral("servers"));
    if (!serversValue.isArray() || serversValue.toArray().size() > 256) {
        return fail(tr("The backend returned an invalid custom-DNS server list"));
    }

    bool paidFeaturesAvailable = false;
    bool enabled = false;
    if (!readBoolean(object, QStringLiteral("paidFeaturesAvailable"),
                     &paidFeaturesAvailable)
        || !readBoolean(object, QStringLiteral("enabled"), &enabled)) {
        return fail(tr("The backend returned incomplete custom-DNS settings"));
    }

    QVariantList servers;
    for (const QJsonValue serverValue : serversValue.toArray()) {
        if (!serverValue.isObject()) {
            return fail(tr("The backend returned an invalid custom-DNS server"));
        }
        const QJsonObject server = serverValue.toObject();
        const QJsonValue addressValue = server.value(QStringLiteral("address"));
        const QJsonValue enabledValue = server.value(QStringLiteral("enabled"));
        if (!addressValue.isString() || !enabledValue.isBool()) {
            return fail(tr("The backend returned an invalid custom-DNS server"));
        }
        const QString address = normalizeServerAddress(addressValue.toString());
        if (address.isEmpty()) {
            return fail(tr("The backend returned an invalid custom-DNS server"));
        }
        servers.append(QVariantMap{
            {QStringLiteral("address"), address},
            {QStringLiteral("enabled"), enabledValue.toBool()},
        });
    }

    m_paidFeaturesAvailable = paidFeaturesAvailable;
    m_enabled = enabled;
    m_servers = servers;
    m_loaded = true;
    m_busy = false;
    m_message.clear();
    emit changed();
    return true;
}

void CustomDnsModel::reset(const QString &message)
{
    m_loaded = false;
    m_busy = false;
    m_message = message;
    m_paidFeaturesAvailable = false;
    m_enabled = false;
    m_servers.clear();
    m_restartRequired = false;
    emit changed();
}

void CustomDnsModel::setBusy(bool busy)
{
    if (m_busy == busy) {
        return;
    }
    m_busy = busy;
    emit changed();
}

void CustomDnsModel::setMessage(const QString &message)
{
    if (m_message == message) {
        return;
    }
    m_message = message;
    emit changed();
}

void CustomDnsModel::setRestartRequired(bool required)
{
    if (m_restartRequired == required) {
        return;
    }
    m_restartRequired = required;
    emit changed();
}
