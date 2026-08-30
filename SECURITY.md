# Security policy

## Supported versions

Until the project reaches 1.0, security fixes are provided only for the latest
tagged minor release.

| Release | Security fixes |
| --- | --- |
| 0.11.x | Supported |
| 0.10.x and earlier | Unsupported |

## Report a vulnerability privately

Do not open a public issue for a suspected vulnerability.

Use GitHub Private Vulnerability Reporting when it is available for this
repository. Otherwise, email `uglyegg@entropy.quest` with the subject
`[Plasma VPN security]`.

Include:

- the affected client and Proton Core versions;
- Fedora, Plasma, and Secret Service provider versions;
- the security impact and required attacker access;
- the smallest reproducible steps or proof of concept;
- sanitized logs or screenshots when they materially help.

Never send Proton credentials, session tokens, recovery codes, FIDO2 secrets,
private keys, Secret Service databases, or unreviewed support bundles. Use a
test account and the deterministic demo backend whenever possible.

The maintainer will make a best-effort acknowledgment within five business
days and provide an initial assessment or request for information within
fourteen days. These are response targets, not guaranteed remediation dates.

This independent community project does not operate a bug-bounty program and
cannot offer rewards on Proton's behalf.

## In scope

- the C++/Qt/Kirigami Control Center and resident Plasma agent;
- the Python community adapter and its versioned session D-Bus interface;
- encrypted authentication payload transport and secret handling;
- KRunner, System Settings, notification, shortcut, and tray integrations;
- Fedora packaging, systemd user services, activation, and process lifetime;
- community-owned support-report and diagnostic handling;
- interactions in which this client violates the documented boundary with
  Proton's official VPN Core.

Examples include credential disclosure, authentication-payload replay,
unintended command execution, arbitrary file access, privilege escalation,
unsafe D-Bus authorization behavior, or a community-client defect that changes
VPN security state contrary to the official Core.

## Security properties

The following properties are part of the project's security contract:

- plaintext authentication fields must not appear in D-Bus arguments,
  snapshots, notifications, or logs;
- authentication payloads must remain bounded, authenticated, encrypted,
  sealed against modification, and tied to a one-use key scoped to the actual
  D-Bus sender and intended operation;
- installed clients must authenticate and pin the packaged backend's unique
  D-Bus owner before sending secrets or state-changing requests;
- state-changing backend methods must authorize the actual D-Bus sender and
  revoke that authority when its unique name vanishes;
- unexpected third-party exception text must not cross the public D-Bus
  boundary;
- the community client must not implement or override VPN protocols,
  NetworkManager behavior, kill switch, split tunneling, server construction,
  or session persistence owned by Proton Core;
- the backend must remain an unprivileged user service and must fail safely
  when required official-Core behavior is unavailable;
- diagnostic and support artifacts must be explicitly requested, bounded, and
  never uploaded automatically.

The detailed design is documented in
[Authentication](docs/AUTHENTICATION.md),
[Architecture](docs/ARCHITECTURE.md), and
[Backend service hardening](docs/HARDENING.md).

The current maintainer-directed assessment and its closed historical findings
are published in the
[security and engineering assessment](docs/SECURITY-AUDIT-2026-08-30.md). It is
not an independent certification and does not replace private reporting of a
new suspected vulnerability.

## Known boundaries and exclusions

The design does not claim to defend against root, a debugger, or another
same-user process that can directly read client memory. Python and Qt may
retain immutable string copies until their allocators reuse them.

The following are outside this repository's disclosure scope:

- Proton's service, API, accounts, infrastructure, or official websites;
- vulnerabilities solely in unmodified official Proton packages;
- social engineering, phishing, credential stuffing, or account-support
  disputes;
- unsupported-distribution compatibility without a concrete security impact;
- theoretical hardening suggestions without a reproducible exploit path.

Findings exclusively affecting Proton should be reported through Proton's
official security response process:
https://proton.me/security/response-center

## Coordinated disclosure

Please allow reasonable time to reproduce, fix, package, and distribute a
confirmed issue before public disclosure. The maintainer will credit reporters
who request attribution and will preserve anonymity when requested, subject to
the limits of the communication and hosting services involved.
