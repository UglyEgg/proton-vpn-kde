// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#pragma once

#include <QByteArray>
#include <QObject>
#include <QString>
#include <QStringList>

class DesktopReadiness final : public QObject
{
    Q_OBJECT
    Q_PROPERTY(QString secretServiceState READ secretServiceState NOTIFY secretServiceStateChanged)
    Q_PROPERTY(QString coreCapabilityState READ coreCapabilityState NOTIFY packageCapabilityStatesChanged)
    Q_PROPERTY(QString keyringCapabilityState READ keyringCapabilityState NOTIFY packageCapabilityStatesChanged)

public:
    explicit DesktopReadiness(QObject *parent = nullptr);
    ~DesktopReadiness() override;

    [[nodiscard]] QString secretServiceState() const;
    [[nodiscard]] QString coreCapabilityState() const;
    [[nodiscard]] QString keyringCapabilityState() const;
    Q_INVOKABLE void refresh();
    Q_INVOKABLE void refreshSecretService();
    Q_INVOKABLE void refreshPackageCapabilities();

    [[nodiscard]] static QString classifySecretService(
        const QStringList &registeredNames,
        const QStringList &activatableNames);
    [[nodiscard]] static bool containsPackageCapability(
        const QByteArray &output, const QByteArray &capability);

signals:
    void secretServiceStateChanged();
    void packageCapabilityStatesChanged();

private:
    void setSecretServiceState(const QString &state);
    void setPackageCapabilityStates(const QString &core,
                                    const QString &keyring);
    QString m_secretServiceState = QStringLiteral("unknown");
    QString m_coreCapabilityState = QStringLiteral("unknown");
    QString m_keyringCapabilityState = QStringLiteral("unknown");
    quint64 m_generation = 0;
    class QProcess *m_packageQuery = nullptr;
    class QTimer *m_packageTimeout = nullptr;
    bool m_packageTimedOut = false;
};
