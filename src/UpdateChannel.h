// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#pragma once

#include <QByteArray>
#include <QObject>
#include <QString>
#include <QStringList>

class QProcess;

struct ProtonPackageChannelState
{
    bool available = false;
    bool betaEnabled = false;
};

class UpdateChannel final : public QObject
{
    Q_OBJECT
    Q_PROPERTY(bool available READ available NOTIFY changed)
    Q_PROPERTY(bool betaEnabled READ betaEnabled NOTIFY changed)
    Q_PROPERTY(bool busy READ busy NOTIFY changed)
    Q_PROPERTY(bool error READ error NOTIFY changed)
    Q_PROPERTY(QString message READ message NOTIFY changed)

public:
    explicit UpdateChannel(QObject *parent = nullptr);

    [[nodiscard]] bool available() const;
    [[nodiscard]] bool betaEnabled() const;
    [[nodiscard]] bool busy() const;
    [[nodiscard]] bool error() const;
    [[nodiscard]] QString message() const;

    Q_INVOKABLE void refresh();
    Q_INVOKABLE void setBetaEnabled(bool enabled);

    [[nodiscard]] static ProtonPackageChannelState packageState(
        const QByteArray &packageQueryOutput);
    [[nodiscard]] static QStringList switchArguments(bool enableBeta);

signals:
    void changed();

private:
    enum class Operation {
        None,
        Query,
        SwitchToStable,
        SwitchToBeta,
    };

    void startQuery();
    void onFinished(int exitCode);
    void setBusy(bool busy);

    QProcess *m_process = nullptr;
    Operation m_operation = Operation::None;
    bool m_available = false;
    bool m_betaEnabled = false;
    bool m_busy = false;
    bool m_error = false;
    QString m_message;
};
