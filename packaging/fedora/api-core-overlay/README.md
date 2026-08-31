# Reproducible API Core overlay

This directory rebuilds the optional optimized API Core package from Proton's
exact signed Fedora `5.6.10-1.fc44` RPM. The vendor RPM is a build input only;
the workflow does not install Proton's GTK client and does not download or
combine payload files from any other package.

The first two applied patches share repeated immutable server strings. The
third stops `supports_fido2` from calling API Core's own deprecated capability
property while preserving its availability-and-registered-key truth table.
The fourth marks Protun's ephemeral WireGuard private key as system-owned
instead of `AGENT_OWNED`. Proton already creates this NetworkManager profile
with `save_to_disk=False`; NetworkManager therefore keeps the supplied key in
the unsaved connection instead of asking a desktop secret agent to return it.
On Fedora, NetworkManager may materialize that unsaved profile in its root-only
volatile `/run/NetworkManager/system-connections` directory. The profile is
removed on disconnect and cannot survive a reboot, but this is privileged
runtime storage rather than a process-memory-only claim. The change removes
the desktop-keyring copy and the requirement for a GNOME- or Plasma-specific
NetworkManager secret agent. It does not change the key, protocol, server,
routing, kill switch, split tunneling, account authentication, or native
helper.

`overlay-manifest.json` pins:

- the vendor NEVRA, source RPM name, complete-RPM SHA-256, header SHA-256,
  payload SHA-256, signing-key fingerprint, official key URL, and complete
  signing-key SHA-256;
- all four runtime patch hashes and their provenance;
- every permitted changed installed path;
- the before/after SHA-256 for five Python sources and their ten derived
  bytecode files.

`rebuild_overlay.py` extracts the pinned RPM without installing it, applies
all patches with zero fuzz, deterministically regenerates only the affected
bytecode, and compares the complete vendor and overlay trees. It imports the
pinned signing key into a temporary unprivileged RPM database solely to verify
the vendor RPM, so a clean builder does not depend on a preconfigured system
keyring. A path addition,
removal, mode or hardlink change, unrecorded content change, stale patch, wrong
Python version, or unexpected output hash fails the build. The completed RPM
must also retain Proton's exact dependency, conflict, obsolete, and package
scriptlet sets.

Build and verify with:

```bash
packaging/fedora/api-core-overlay/build_overlay_rpm.sh \
    /path/to/python3-proton-vpn-api-core-5.6.10-1.fc44.x86_64.rpm
```

The resulting SRPM contains the signed vendor RPM, manifest, verifier, and
patches. The binary RPM contains the same payload paths as Proton's RPM, with
only the fifteen manifest-listed file hashes changed.

The direct `NetworkManager-openvpn-gnome` dependency is deliberately retained
because it belongs to Proton's current Core package contract. Removing it may
be reasonable, but requires separate OpenVPN runtime evidence and is not part
of this overlay.
