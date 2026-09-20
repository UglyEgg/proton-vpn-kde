// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#include "CommunityReport.h"

#include "CommunityReportFormat.h"
#include "DesktopReadiness.h"
#include "VpnController.h"
#include "VpnSettingsModel.h"

#include <QClipboard>
#include <QCoreApplication>
#include <QGuiApplication>
#include <QSysInfo>

CommunityReport::CommunityReport(VpnController *controller,
                                 DesktopReadiness *readiness, QObject *parent)
    : QObject(parent)
    , m_controller(controller)
    , m_readiness(readiness)
{
}

QString CommunityReport::preview() const
{
    return m_preview;
}

void CommunityReport::refresh()
{
    const CommunityReportFacts facts{
        QCoreApplication::applicationVersion(),
        m_controller->coreVersion(),
        QSysInfo::productType(),
        QString::fromLatin1(qVersion()),
        m_readiness->secretServiceState(),
        m_controller->state(),
        m_controller->errorCode(),
        m_controller->backendAvailable(),
        m_controller->ready(),
        m_controller->snapshotHealthy(),
        m_controller->startupCompatible(),
        m_controller->coreMemoryOptimized(),
        m_controller->telemetryEnabled(),
        m_controller->settings()->loaded(),
        m_controller->settings()->telemetry(),
    };
    m_preview = formatCommunityReport(facts);
    emit changed();
}

bool CommunityReport::copyPreview()
{
    if (m_preview.isEmpty()) {
        return false;
    }
    QClipboard *clipboard = QGuiApplication::clipboard();
    if (!clipboard) {
        return false;
    }
    clipboard->setText(m_preview);
    return true;
}
