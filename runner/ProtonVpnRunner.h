// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#pragma once

#include <KRunner/AbstractRunner>

class ProtonVpnRunner final : public KRunner::AbstractRunner
{
    Q_OBJECT

public:
    ProtonVpnRunner(QObject *parent, const KPluginMetaData &metadata);

    void match(KRunner::RunnerContext &context) override;
    void run(const KRunner::RunnerContext &context,
             const KRunner::QueryMatch &match) override;

private:
    void addMatch(KRunner::RunnerContext &context, int action,
                  const QString &argument = {});
};
