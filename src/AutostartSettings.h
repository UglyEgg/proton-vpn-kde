// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#pragma once

#include <QObject>
#include <QString>

// Created only by a settings surface; the tray agent needs no file watcher.
class AutostartSettings final : public QObject
{
    Q_OBJECT
    Q_PROPERTY(bool enabled READ enabled WRITE setEnabled NOTIFY changed)
    Q_PROPERTY(bool configurable READ configurable NOTIFY changed)
    Q_PROPERTY(QString errorMessage READ errorMessage NOTIFY changed)
public:
    explicit AutostartSettings(QObject *parent = nullptr);
    bool enabled() const { return m_enabled; }
    bool configurable() const { return m_configurable; }
    QString errorMessage() const { return m_errorMessage; }
    void setEnabled(bool enabled);
    Q_INVOKABLE void refresh();

signals:
    void changed();

private:
    QString entryPath() const;
    bool m_enabled = false;
    bool m_configurable = true;
    QString m_errorMessage;
};
