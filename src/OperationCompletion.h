// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#pragma once

#include <QtTypes>

namespace ProtonVpnKde
{
// One operation owns its reply and subsequent reconciliation obligation.
// A busy snapshot is progress, never a terminal completion receipt.
class OperationCompletion
{
public:
    enum class Phase { Idle, AwaitingReply, Reconciling };

    quint64 begin()
    {
        m_phase = Phase::AwaitingReply;
        return ++m_generation;
    }
    void invalidate()
    {
        ++m_generation;
        m_phase = Phase::Idle;
    }
    [[nodiscard]] quint64 generation() const { return m_generation; }
    void reconcile(quint64 generation)
    {
        if (generation == m_generation && m_phase != Phase::Idle) {
            m_phase = Phase::Reconciling;
        }
    }
    void finish(quint64 generation)
    {
        if (generation == m_generation) {
            m_phase = Phase::Idle;
        }
    }
    [[nodiscard]] bool settleIfIdle(quint64 generation, bool idle)
    {
        if (generation != m_generation || m_phase != Phase::Reconciling || !idle) {
            return false;
        }
        m_phase = Phase::Idle;
        return true;
    }

private:
    quint64 m_generation = 0;
    Phase m_phase = Phase::Idle;
};
}
