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
        .clientVersion = QCoreApplication::applicationVersion(),
        .coreVersion = m_controller->coreVersion(),
        .osFamily = QSysInfo::productType(),
        .qtVersion = QString::fromLatin1(qVersion()),
        .secretServiceState = m_readiness->secretServiceState(),
        .vpnState = m_controller->state(),
        .errorCode = m_controller->errorCode(),
        .backendAvailable = m_controller->backendAvailable(),
        .backendReady = m_controller->ready(),
        .snapshotHealthy = m_controller->snapshotHealthy(),
        .startupCompatible = m_controller->startupCompatible(),
        .coreMemoryOptimized = m_controller->coreMemoryOptimized(),
        .telemetryBuildEnabled = m_controller->telemetryBuildEnabled(),
        .telemetryRuntimeAvailable =
            m_controller->settings()->telemetryAvailable(),
        .telemetryPreferenceKnown = m_controller->settings()->loaded(),
        .telemetryEnabled = m_controller->settings()->telemetry(),
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
