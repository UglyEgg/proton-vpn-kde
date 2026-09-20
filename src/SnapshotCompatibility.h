// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#pragma once

#include "SnapshotContract.generated.h"

#include <QJsonObject>
#include <QString>

namespace ProtonVpnKde
{
enum class SnapshotCompatibilityResult {
    Accepted,
    UnsupportedVersion,
    InvalidPayload,
};

inline SnapshotCompatibilityResult normalizeSnapshot(QJsonObject *snapshot)
{
    if (!snapshot) {
        return SnapshotCompatibilityResult::InvalidPayload;
    }
    const int version = snapshot->value(QStringLiteral("schemaVersion")).toInt();
    if (version == snapshotSchemaVersion) {
        return validateSnapshotV2(*snapshot)
            ? SnapshotCompatibilityResult::Accepted
            : SnapshotCompatibilityResult::InvalidPayload;
    }
    if (version != 1) {
        return SnapshotCompatibilityResult::UnsupportedVersion;
    }
    if (!validateSnapshotV1(*snapshot)) {
        return SnapshotCompatibilityResult::InvalidPayload;
    }
    snapshot->insert(QStringLiteral("schemaVersion"), snapshotSchemaVersion);
    snapshot->insert(QStringLiteral("vpnExitIpv4"), QString());
    snapshot->insert(QStringLiteral("vpnExitIpv6"), QString());
    snapshot->insert(QStringLiteral("deviceIpAtConnect"), QString());
    return validateSnapshotV2(*snapshot)
        ? SnapshotCompatibilityResult::Accepted
        : SnapshotCompatibilityResult::InvalidPayload;
}
} // namespace ProtonVpnKde
