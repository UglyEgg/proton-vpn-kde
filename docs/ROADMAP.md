# Roadmap

This file contains open work. Shipped changes belong in the
[changelog](../CHANGELOG.md); validation status belongs in the
[assessment](SECURITY-AUDIT-2026-08-30.md). Architecture and security ownership
remain unchanged.

## Active: 0.14.5 release preparation

Implementation and focused offline regressions are on
`fix/fastest-bounded-failover`. The branch also consolidates documentation.
The seven isolated reviews, affected corrected-diff rechecks, Fedora native/RPM
checks, and normal installed UAT are accepted. The assessment owns exact build
identities and validation limits. Public release remains 0.14.4.

Remaining release work:

1. Sign the release-preparation commit after source/metadata/seal checks.
2. Validate final Fedora/Ubuntu release artifacts, including repeatability,
   from immutable signed source. The local UAT RPM is not a publication build.
3. With maintainer approval, push the branch for PR/CI, finalize public-facing
   status, merge, tag, sign artifacts, publish, and verify both Git mirrors and
   the OpenDesktop listing.

No live fault tests are authorized. Any future fault trial requires the
independent recovery mechanism described in [Hardening](HARDENING.md).

## Priorities

- Triage reproducible client regressions; keep Proton-service problems separate.
- Revalidate downstream overlays when supported Proton packages change.
- Collect Ubuntu 26.04 Plasma field reports before promoting its validation tier.
- Obtain independent review of authentication transport and D-Bus authorization.
- Translate Plasma-specific text with explicit provenance.
- Validate whole-client retention and desktop power/network transitions.

## Upstream opportunities

Retire an overlay only after a released upstream equivalent passes its
compatibility gates. Source provenance and independent patch scope belong in
the [overlay handoff](../packaging/fedora/api-core-overlay/README.md#patch-scope-and-upstream-handoff),
not a duplicated PR-status ledger.

FIDO2 remains conditional on Core's complete cancellable-selection contract.
Any upstream submission, acceptance claim, or branding change needs separate
maintainer authorization.

## Optional Plasma integration

A future Plasma widget may use the resident agent for status and common
actions. It must not load Python/Core into `plasmashell`, and the existing
agent and Control Center must remain usable without it. New integration
surfaces require a design review before implementation.
