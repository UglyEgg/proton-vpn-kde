// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#pragma once

#include <QObject>
#include <QString>

class DesktopReadiness;
class VpnController;

class CommunityReport final : public QObject
{
    Q_OBJECT
    Q_PROPERTY(QString preview READ preview NOTIFY changed)

public:
    CommunityReport(VpnController *controller, DesktopReadiness *readiness,
                    QObject *parent = nullptr);

    [[nodiscard]] QString preview() const;
    Q_INVOKABLE void refresh();
    Q_INVOKABLE bool copyPreview();

signals:
    void changed();

private:
    VpnController *m_controller;
    DesktopReadiness *m_readiness;
    QString m_preview;
};
