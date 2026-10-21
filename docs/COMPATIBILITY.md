# Compatibility

## Supported release baseline

Plasma VPN 0.14.5 is prepared for release; 0.14.4 remains the current public
package release. Fedora's normal-operation UAT is accepted for the new recovery
code. Both distributions pass candidate package checks. Publication requires
signed, exact-source artifacts. Ubuntu still needs Plasma field reports.
Exact validation scope is tracked in the [assessment](SECURITY-AUDIT-2026-08-30.md).

| Component | Fedora 44 | Ubuntu 26.04 |
| --- | --- | --- |
| Architecture | x86_64 | amd64 |
| Desktop | Plasma 6; systemd user services | Plasma 6; systemd user services |
| Qt / KDE | Qt 6.8+; Frameworks 6 | Qt 6.10.2; Frameworks 6.24 |
| Python | 3.14 with `os.pidfd_open` | 3.14 with `os.pidfd_open` |
| API Core overlay | `5.8.11-1.plasmavpn1` beta; stable minimum `5.8.3-2.plasmavpn1` | `5.6.10-12plasmavpn1` |
| Keyring overlay | `0.2.3-11.plasmavpn1` build; minimum `0.2.3-10.plasmavpn1` | `0.2.3-10plasmavpn1` |
| Secret Service | KeePassXC verified; provider-neutral implementation | Live provider UAT pending |
| Validation tier | Installed Plasma lifecycle accepted | Build, artifact, dependency, transaction, and removal checks; live lifecycle pending |

Build dependencies include C++20, CMake 3.24+, OpenSSL 3, and `dbus-fast` 2.20+.
Fedora's tested `cryptography` floor is 50.0.0; Ubuntu's packaged 46.0.5 passes
the backend suite. Specs and Debian control files are authoritative for complete
dependencies. Supported packages install under `/usr`; custom prefixes are not
supported runtime layouts.

Both client formats require:

```text
proton-vpn-api-core-plasma-protun-secret >= 1
proton-keyring-secret-service-owner-pinned >= 1
```

The version floors and capabilities prevent a stock Core/keyring update from
silently removing required integration behavior. Fedora's beta build input does
not raise the stable consumer floor. Optional memory optimization detection
never blocks VPN use.

## API-Core overlay

| Distribution | Vendor input | Reconstruction and patch policy |
| --- | --- | --- |
| Fedora | Signed `5.8.11-1.fc44` RPM | [Fedora overlay](../packaging/fedora/api-core-overlay/README.md) |
| Ubuntu | Pinned `5.6.10_amd64.deb` | [Ubuntu overlay](../packaging/debian/api-core-overlay/README.md) |

The overlays preserve the compiled vendor networking payload and apply only
manifested Python changes. They are modified Proton Core, not official builds.
Their manifests own vendor hashes, source references, changed paths, and patch
provenance.

The static public-API fixture is Core 5.5.6; it is never imported or executed.
The generic API floor is 5.6.10. Neither substitutes for the distribution
runtime baselines above. Fedora's exact floors are declared in
[`core-compatibility.json`](../packaging/fedora/core-compatibility.json).

## Keyring overlay

The [keyring package](../packaging/fedora/keyring-overlay/README.md) supplies
provider-neutral collection selection, reusable serialized connections,
same-user unique-owner pinning, and bounded provider-restart recovery. It
supports already-running and D-Bus-activated providers; GNOME Keyring is not
required.

Debian uses the same patch series. Provider selection and credential behavior
are specified in [Authentication](AUTHENTICATION.md#secret-service-provider).

## Authentication limitations

- Supported Core builds do not provide the complete cancellable multi-key
  FIDO2 selection contract. Security-key sign-in remains hidden; authenticator
  and recovery codes are supported.
- Account replacement requires Linux pidfds. Missing `os.pidfd_open` blocks
  replacement rather than assuming the outgoing process has retired.
- Core's human-verification challenge has no native completion callback; the
  client opens Proton's account flow without exporting the verification token.

## Compatibility policy

- A new Core baseline requires public-API checks, hash-checked lifecycle
  conformance, overlay policy, backend tests, clean builds, and disconnected
  startup acceptance.
- A new keyring baseline must pass the provider suite before supplying the
  owner-pinned capability.
- Live-supported targets require activation, authentication, browsing, settings,
  connection, recovery, and removal acceptance. Package-validated targets remain
  explicitly labeled until field evidence covers those operations.
- Run only one Proton frontend against a saved session.
- Proton's NetworkManager OpenVPN editor dependency remains intact; the Plasma
  frontend does not use the GTK editor.

These are tested integration bounds, not a support promise for future Proton,
distribution, Qt, or KDE releases. Evidence is owned by the
[assessment](SECURITY-AUDIT-2026-08-30.md); promotion gates are owned by the
[release procedure](RELEASING.md).
