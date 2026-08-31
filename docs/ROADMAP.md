# Roadmap

This roadmap contains planned work only. Completed user-visible changes belong
in the [changelog](../CHANGELOG.md), and closed security findings remain in the
[security assessment](SECURITY-AUDIT-2026-08-30.md).

Every item must preserve the project boundary: Proton's official Core owns VPN
protocols, NetworkManager integration, kill switch, IPv6 leak protection,
split tunneling, server selection, and session persistence. A Core change is an
independent upstream contribution, not a hidden part of this client.

## Post-release stabilization

- Send Proton a concise engineering introduction after the public tag and
  signed Fedora artifacts are available for review.
- Triage public-alpha reports against the documented support boundary and add
  regression coverage before changing behavior.
- Keep the compatibility matrix current as Proton Core, Fedora, Qt, and KDE
  Frameworks releases change.
- Expand the release battery to a second independently tested Plasma
  distribution before claiming broader Linux support.
- Seek an independent review of the authentication transport, D-Bus service
  identity, and sender-authorization design before describing the project as
  independently security-reviewed or stable.
- Complete translation coverage for Plasma-specific strings without guessing
  translations or obscuring their provenance.

## Connection Inspector

Add an on-demand Control Center page for richer connection details and bounded
diagnostics. It should:

- consume only existing non-sensitive backend state;
- collect nothing while the page is closed;
- avoid traffic inspection, history retention, remote telemetry, or new
  networking ownership; and
- keep the full Control Center out of the resident process.

## Optional Plasma widget

Provide a Plasma 6 widget for status and common connection actions. It should
reuse the resident agent and current authenticated backend path instead of
embedding Python or Proton Core in `plasmashell`. The agent and Control Center
must remain complete without the widget.

## Upstream opportunities

Provider-neutral Secret Service compatibility, small Core API hygiene fixes,
and terminology improvements should be proposed separately to the Proton
repository that owns each behavior. Each patch must stand on its own, include
focused tests, and avoid depending on this Plasma frontend.
