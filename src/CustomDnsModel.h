#pragma once

#include <QObject>
#include <QString>
#include <QVariantList>

class CustomDnsModel final : public QObject
{
    Q_OBJECT
    Q_PROPERTY(bool loaded READ loaded NOTIFY changed)
    Q_PROPERTY(bool busy READ busy NOTIFY changed)
    Q_PROPERTY(QString message READ message NOTIFY changed)
    Q_PROPERTY(bool paidFeaturesAvailable READ paidFeaturesAvailable NOTIFY changed)
    Q_PROPERTY(bool enabled READ enabled NOTIFY changed)
    Q_PROPERTY(QVariantList servers READ servers NOTIFY changed)
    Q_PROPERTY(int serverCount READ serverCount NOTIFY changed)
    Q_PROPERTY(bool restartRequired READ restartRequired NOTIFY changed)

public:
    explicit CustomDnsModel(QObject *parent = nullptr);

    [[nodiscard]] bool loaded() const;
    [[nodiscard]] bool busy() const;
    [[nodiscard]] QString message() const;
    [[nodiscard]] bool paidFeaturesAvailable() const;
    [[nodiscard]] bool enabled() const;
    [[nodiscard]] QVariantList servers() const;
    [[nodiscard]] int serverCount() const;
    [[nodiscard]] bool restartRequired() const;

    Q_INVOKABLE bool containsServer(const QString &address) const;
    Q_INVOKABLE bool isValidServerAddress(const QString &address) const;

    static QString normalizeServerAddress(const QString &address);
    bool applyJson(const QString &settingsJson, QString *errorMessage = nullptr);
    void reset(const QString &message = {});
    void setBusy(bool busy);
    void setMessage(const QString &message);
    void setRestartRequired(bool required);

signals:
    void changed();

private:
    bool m_loaded = false;
    bool m_busy = false;
    QString m_message;
    bool m_paidFeaturesAvailable = false;
    bool m_enabled = false;
    QVariantList m_servers;
    bool m_restartRequired = false;
};
