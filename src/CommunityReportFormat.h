// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#pragma once

#include <QString>

struct CommunityReportFacts
{
    QString clientVersion;
    QString coreVersion;
    QString osFamily;
    QString qtVersion;
    QString secretServiceState;
    QString vpnState;
    QString errorCode;
    bool backendAvailable = false;
    bool backendReady = false;
    bool snapshotHealthy = false;
    bool startupCompatible = false;
    bool coreMemoryOptimized = false;
};

[[nodiscard]] QString formatCommunityReport(const CommunityReportFacts &facts);
