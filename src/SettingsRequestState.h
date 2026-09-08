// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#pragma once

#include <QtTypes>

namespace ProtonVpnKde
{
// Three settings projections share this request contract, not their values.
// A timed-out write requires a serialized read before another write is safe
// to admit locally. Failure of that read does not establish write completion.
class SettingsRequestState
{
public:
    [[nodiscard]] bool busy() const { return m_phase != Phase::Idle; }
    [[nodiscard]] bool needsRead() const { return m_phase == Phase::ReconcileNeeded; }
    [[nodiscard]] bool canRead() const { return !busy() || needsRead(); }
    [[nodiscard]] quint64 generation() const { return m_generation; }
    quint64 beginRead()
    {
        m_phase = needsRead() ? Phase::ReconcileRead : Phase::Read;
        return ++m_generation;
    }
    quint64 beginWrite()
    {
        m_phase = Phase::Write;
        return ++m_generation;
    }
    void complete(quint64 generation, bool success, bool completionUnknown)
    {
        if (generation != m_generation) {
            return;
        }
        const bool unresolved = (m_phase == Phase::Write && completionUnknown)
            || (m_phase == Phase::ReconcileRead && !success);
        m_phase = unresolved ? Phase::ReconcileNeeded : Phase::Idle;
    }
    void invalidate()
    {
        ++m_generation;
        m_phase = Phase::Idle;
    }

private:
    enum class Phase { Idle, Read, Write, ReconcileRead, ReconcileNeeded };
    quint64 m_generation = 0;
    Phase m_phase = Phase::Idle;
};
}
