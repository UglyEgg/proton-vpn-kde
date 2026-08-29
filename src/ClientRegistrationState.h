#pragma once

#include <cstdint>
#include <optional>

namespace ProtonVpnKde
{
class ClientRegistrationState final
{
public:
    enum class Completion
    {
        Stale,
        Failed,
        Registered,
    };

    [[nodiscard]] std::optional<std::uint64_t> begin()
    {
        if (m_registered || m_inFlight) {
            return std::nullopt;
        }
        m_inFlight = true;
        return m_generation;
    }

    [[nodiscard]] Completion complete(std::uint64_t generation, bool succeeded)
    {
        if (generation != m_generation) {
            return Completion::Stale;
        }
        m_inFlight = false;
        m_registered = succeeded;
        return succeeded ? Completion::Registered : Completion::Failed;
    }

    void serviceChanged()
    {
        ++m_generation;
        m_registered = false;
        m_inFlight = false;
    }

    [[nodiscard]] bool registered() const { return m_registered; }
    [[nodiscard]] bool inFlight() const { return m_inFlight; }

private:
    std::uint64_t m_generation = 0;
    bool m_registered = false;
    bool m_inFlight = false;
};
}
