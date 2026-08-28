#pragma once

#include <QObject>
#include <QString>
#include <QStringList>

class SplitTunnelingModel final : public QObject
{
    Q_OBJECT
    Q_PROPERTY(bool loaded READ loaded NOTIFY changed)
    Q_PROPERTY(bool busy READ busy NOTIFY changed)
    Q_PROPERTY(QString message READ message NOTIFY changed)
    Q_PROPERTY(bool available READ available NOTIFY changed)
    Q_PROPERTY(bool paidFeaturesAvailable READ paidFeaturesAvailable NOTIFY changed)
    Q_PROPERTY(bool enabled READ enabled NOTIFY changed)
    Q_PROPERTY(QString mode READ mode NOTIFY changed)
    Q_PROPERTY(int modeIndex READ modeIndex NOTIFY changed)
    Q_PROPERTY(QStringList selectedAppPaths READ selectedAppPaths NOTIFY changed)
    Q_PROPERTY(QStringList selectedIpRanges READ selectedIpRanges NOTIFY changed)
    Q_PROPERTY(int selectedIpRangeCount READ selectedIpRangeCount NOTIFY changed)

public:
    explicit SplitTunnelingModel(QObject *parent = nullptr);

    [[nodiscard]] bool loaded() const;
    [[nodiscard]] bool busy() const;
    [[nodiscard]] QString message() const;
    [[nodiscard]] bool available() const;
    [[nodiscard]] bool paidFeaturesAvailable() const;
    [[nodiscard]] bool enabled() const;
    [[nodiscard]] QString mode() const;
    [[nodiscard]] int modeIndex() const;
    [[nodiscard]] QStringList selectedAppPaths() const;
    [[nodiscard]] QStringList selectedIpRanges() const;
    [[nodiscard]] int selectedIpRangeCount() const;
    [[nodiscard]] QStringList excludeAppPaths() const;
    [[nodiscard]] QStringList includeAppPaths() const;
    [[nodiscard]] QStringList excludeIpRanges() const;
    [[nodiscard]] QStringList includeIpRanges() const;

    Q_INVOKABLE bool containsApplication(const QString &executable) const;

    bool applyJson(const QString &settingsJson, QString *errorMessage = nullptr);
    void reset(const QString &message = {});
    void setBusy(bool busy);
    void setMessage(const QString &message);

signals:
    void changed();

private:
    bool m_loaded = false;
    bool m_busy = false;
    QString m_message;
    bool m_available = false;
    bool m_paidFeaturesAvailable = false;
    bool m_enabled = false;
    QString m_mode = QStringLiteral("exclude");
    QStringList m_excludeAppPaths;
    QStringList m_includeAppPaths;
    QStringList m_excludeIpRanges;
    QStringList m_includeIpRanges;
};
