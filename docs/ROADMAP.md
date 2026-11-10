# Roadmap

Open work only. Changes belong in the [changelog](../CHANGELOG.md); current
evidence and assurance limits belong in the
[assessment](SECURITY-AUDIT-2026-08-30.md).

## Priorities

- Triage reproducible client regressions separately from Proton-service faults.
- Revalidate downstream overlays when supported Proton packages change; retire
  patches only after released equivalents pass their compatibility gates.
- Collect Ubuntu 26.04 Plasma field reports and other providers' unlock UAT.
- Qualify prolonged outage, suspend/roaming, and resource-pressure recovery.
- Measure current-stack whole-client retention and desktop power transitions.
- Obtain independent authentication/D-Bus review before any audited claim.
- Translate Plasma-specific text with explicit provenance.

Live fault trials require separate authorization and the independent recovery
boundary in [Hardening](HARDENING.md#fault-test-isolation).

## Conditional work

FIDO2 requires Core's complete cancellable-selection contract. Upstream
submissions and branding changes require separate maintainer authorization.
Overlay scope and provenance belong in the
[overlay handoff](../packaging/fedora/api-core-overlay/README.md#patch-scope-and-upstream-handoff).

A future Plasma widget may use the agent for status/actions. It must not load
Python/Core into `plasmashell`; new integration surfaces require design review.
