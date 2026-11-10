# Roadmap

Open work only. Changes belong in the [changelog](../CHANGELOG.md); current
evidence and assurance limits belong in the
[assessment](SECURITY-AUDIT-2026-08-30.md).

## Active: 0.14.5 release preparation

The `feature/secret-service-unlock-prompt` branch includes bounded Fastest
failover, startup Secret Service admission, and one provider-owned unlock
request. Seven isolated reviews and bounded client corrections are accepted.
The approved Ubuntu Core 5.8.11 rebase passes source/Core/package rechecks.
Signed runtime candidate `2568b7e` passes Fedora/Ubuntu client package checks
and Ubuntu offline transactions. Installed normal Fedora UAT on `e7b4956` was
accepted November 10; corrected installed acceptance remains open. Public
release remains 0.14.4.

Remaining gates:

1. Complete affected normal installed acceptance; retain Ubuntu field-test
   limitations.
2. With maintainer authorization, push for final-head PR/CI, finalize public
   release metadata and merge.
3. Build from the signed tag, verify artifact reproducibility and signatures,
   publish, and verify Git mirrors and the OpenDesktop listing.

No live fault tests are authorized. Any future fault trial requires the
independent recovery boundary in [Hardening](HARDENING.md#fault-test-isolation).

## Priorities

- Triage reproducible client regressions separately from Proton-service faults.
- Revalidate downstream overlays when supported Proton packages change; retire
  patches only after released equivalents pass their compatibility gates.
- Collect Ubuntu 26.04 Plasma field reports and other providers' unlock UAT.
- Qualify prolonged outage, suspend/roaming, and resource-pressure recovery.
- Measure current-stack whole-client retention and desktop power transitions.
- Obtain independent authentication/D-Bus review before any audited claim.
- Translate Plasma-specific text with explicit provenance.

## Conditional work

FIDO2 requires Core's complete cancellable-selection contract. Upstream
submissions and branding changes require separate maintainer authorization.
Overlay scope and provenance belong in the
[overlay handoff](../packaging/fedora/api-core-overlay/README.md#patch-scope-and-upstream-handoff).

A future Plasma widget may use the agent for status/actions. It must not load
Python/Core into `plasmashell`; new integration surfaces require design review.
