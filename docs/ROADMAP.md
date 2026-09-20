# Roadmap

Completed behavior belongs in the [changelog](../CHANGELOG.md). Security and
review results belong in the [assessment](SECURITY-AUDIT-2026-08-30.md).

All work preserves the product boundary: Proton Core owns VPN protocols,
NetworkManager, routing, protection, server selection, and persisted sessions.
Core patches are versioned and reviewed as independent downstream overlays or
upstream contributions.

## 0.13 release line

0.13.0 establishes the progressive Plasma interface and current runtime model:

- graphical connection and split-route presentation;
- native server discovery, settings, authentication, and account surfaces;
- an on-demand Control Center and Inspector with a lean resident agent;
- opt-in login launch, window/tray startup, and saved auto-connect;
- generation-owned asynchronous operations and completion-unknown handling;
- bounded backend lifetime and capture recovery;
- provider-neutral Secret Service support; and
- Fedora 44 packages for the client, keyring overlay, and API-Core overlay.

The release branch passed the seven-perspective review and its bounded
remediation series. Version-specific results are maintained in the assessment,
compatibility matrix, and release workflow rather than duplicated here.

## 0.14 release line

0.14.1 adds connection-time address visibility, on-demand local readiness,
privacy-bounded community diagnostics, and Fedora Core 5.7 compatibility. It
keeps optional connection telemetry off in community packages and exposes the
state without changing Proton Core's networking authority. Its seven-review
battery, bounded remediation, corrected-diff re-review, package validation,
and focused installed acceptance are complete.

## Post-release priorities

1. Triage reports against the documented support and Core boundaries.
2. Require a regression for each accepted defect before changing behavior.
3. Revalidate on every Proton Core, Fedora, Qt, or KDE Frameworks update.
4. Collect Ubuntu 26.04 Plasma field reports before promoting the packages
   from package-validated to live-supported.
5. Obtain independent review of authentication transport, D-Bus identity, and
   sender authorization before using a security-reviewed or stable label.
6. Translate Plasma-specific strings without guessing or obscuring provenance.
7. Reassess workflow trust if CI gains secrets, persistent runners, package
   signing, or publication authority.

## Plasma integration

An optional Plasma 6 widget may expose status and common actions through the
resident agent. It must not embed Python or Proton Core in `plasmashell`, and
the agent and Control Center must remain complete without it.

Potential later integrations require a separate design review:

- native NetworkManager status correlation without duplicating Core ownership;
- richer read-only connection telemetry without traffic history;
- desktop power/network transition observability; and
- distribution-native packaging beyond Fedora and Ubuntu 26.04.

## Upstream opportunities

### Proton VPN API Core

Prepare independent submissions for:

- the dependency-ordered server string-sharing series;
- deprecated FIDO2-query removal;
- Protun transient-secret ownership;
- queued target preservation; and
- validated protection-profile activation.

The [overlay handoff checklist](../packaging/fedora/api-core-overlay/README.md#patch-scope-and-upstream-handoff)
records provenance, patch order, tests, attribution, and source-format work.
Each proposal must stand without this frontend and must not include speculative
Core refactoring.

### Proton keyring

Submit default-alias recovery, Secret Service connection reuse, and same-user
unique-owner pinning as one provider-neutral series. Include focused tests and
preserve actual authorship. Do not introduce KeePassXC-specific behavior.

### FIDO2 cancellation

A future Core can re-enable security keys by carrying its public cancellation
event through multi-key selection, assertion, and PIN work and exposing a
capability only when all workers quiesce on cancellation.

Upstream submission and any public statement of Proton acceptance require
separate maintainer approval.
