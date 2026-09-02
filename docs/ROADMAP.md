# Roadmap

This roadmap contains planned work only. Completed user-visible changes belong
in the [changelog](../CHANGELOG.md), and closed security findings remain in the
[security assessment](SECURITY-AUDIT-2026-08-30.md).

Every item must preserve the project boundary: Proton's official Core owns VPN
protocols, NetworkManager integration, kill switch, IPv6 leak protection,
split tunneling, server selection, and session persistence. A Core change is an
independent upstream contribution, not a hidden part of this client.

## 0.13.0: progressive Plasma experience

Version 0.13.0 is a presentation-only release based on the accepted 0.12.0
mechanics. Its design principle is progressive disclosure: begin with the one
clear task or decision most people need, then reveal relevant depth in context
as the person asks for it. The interface should feel simple on first use and
grow with the user without creating separate novice and expert modes.

This does not mean hiding operational truth. Connection and protection state,
the consequences of an action, authentication requirements, errors, and the
next safe recovery step remain visible at the point where they matter. Details
may be collapsed; safety state may not be.

The implementation constraints are:

- Use native Qt 6, Kirigami, and KDE Frameworks controls. System colors,
  typography, spacing, icon theme, font scaling, directionality, contrast, and
  motion preferences remain authoritative.
- Keep one obvious primary action per task surface. Reveal filters, exact
  servers, diagnostics, and uncommon settings from the relevant summary
  instead of presenting the complete control surface at once.
- Preserve a stable navigation and spatial model as more detail appears. A
  user should not be moved to another section merely because a setting changed
  or an asynchronous operation completed.
- Prefer recognition over recall: show selected criteria and active effects in
  plain language, with technical identifiers available one level deeper.
- Keep advanced disclosure contextual. Do not create an undifferentiated
  Advanced page or use nested accordions as a place to hide design debt.
- Change no backend, VPN, authentication, recovery, D-Bus, resident-agent,
  KRunner, packaging-overlay, or Proton Core mechanics. CI compares those paths
  with accepted revision `ec27fdc` and rejects drift.

### Delivery sequence

1. Freeze the accepted mechanics and retain the existing behavioral and
   security battery as the release invariant.
2. Inventory each user journey, its primary action, essential state, optional
   depth, and recovery path before changing navigation.
3. Simplify the application shell and Overview while retaining immediate
   connection, protection, and account visibility.
4. Make server discovery progress from fastest suitable connection, through
   visible capability criteria, to country, city, state, and exact-server
   selection.
5. Group Settings by user intent and disclose uncommon choices beside the
   setting they refine; keep applied changes on the same page.
6. Refine sign-in, two-factor, security-key, Secret Service approval, error,
   and recovery presentation without altering their established sequencing.
7. Treat Connection Inspector, release history, support status, and technical
   details as on-demand depth rather than primary navigation competition.
8. Verify compact and wide windows, keyboard-only use, screen-reader names,
   1.5x text, right-to-left layout, light and dark schemes, high contrast, and
   reduced motion before repeating the full release battery.

### Information-architecture target

The initial audit found a capable but flat application shell: eight peer
navigation entries give connection tasks, diagnostics, project information,
and an intentionally unavailable reporting proof of concept equal visual
weight. Individual pages are already structured around native cards, but their
depth is generally exposed all at once. Version 0.13.0 will preserve those
working components and alter their presentation hierarchy rather than replace
them.

| Current surface | What already works | Presentation debt to resolve |
| --- | --- | --- |
| Overview | Clear connection state and connect action | Fold secondary server and technical detail into contextual disclosure without hiding protection state |
| Countries and servers | Full hierarchy, search, capability combinations, pins, and fastest match | Establish a visible path from intent to criteria to exact server and keep selected criteria recognizable |
| Settings | Complete native controls grouped into focused components | Lead with common outcomes and reveal exceptions locally instead of showing every choice with equal emphasis |
| Sign in and Account | Correct startup routing and explicit multi-step authentication | Present only the active authentication step while keeping Secret Service waits and recovery unmistakable |
| Connection Inspector | Bounded, read-only, on-demand detail | Open it from connection context and secondary navigation rather than competing with daily connection tasks |
| Release Notes, About, and reporting | Attribution, history, support boundary, and project status remain reachable | Place project information in a secondary destination; keep disabled reporting visibly unavailable without making it a primary task |

| User intent | First layer | Disclosed depth |
| --- | --- | --- |
| Get protected | Current state and one connect or disconnect action | Chosen criteria, server, protocol, and protection details |
| Choose a destination | Fastest suitable choice and visible capability filters | Country, state or city, exact server, load, and capabilities |
| Adjust behavior | Common settings grouped by outcome | Contextual exceptions, custom DNS, and split tunneling |
| Understand a problem | Plain-language state and one safe recovery action | Technical error, component status, and diagnostics |
| Inspect a connection | Short live summary | The existing read-only Connection Inspector |
| Manage identity | Sign-in requirement or current account | Two-factor, security key, plan, and sign-out actions |

Release Notes, About, support status, and other project information remain
available but move out of the primary task hierarchy. Exact navigation changes
will follow the journey inventory rather than precede it.

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
- Add a publication-mode release-metadata gate that requires a dated changelog
  entry and final Fedora release number while preserving the current local-soak
  workflow for unreleased feature branches.
- Reassess release-workflow trust boundaries if CI later gains secrets,
  persistent runners, package-signing authority, or artifact publication; the
  current pull-request build has none of those authorities.

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
