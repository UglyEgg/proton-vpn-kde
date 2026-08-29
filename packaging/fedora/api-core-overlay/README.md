# Reproducible API Core overlay

This directory rebuilds the locally optimized API Core package from Proton's
exact signed Fedora `5.6.10-1.fc44` RPM. The vendor RPM is a build input only;
the workflow does not install Proton's GTK client and does not download or
combine payload files from any other package.

The first two applied patches share repeated immutable server strings. The
third stops `supports_fido2` from calling API Core's own deprecated capability
property while preserving its availability-and-registered-key truth table.
They do not replace Proton's server wrappers, networking, protocol
implementations, NetworkManager integration, kill switch, split tunneling,
authentication, or native helpers.

`overlay-manifest.json` pins:

- the vendor NEVRA, source RPM name, complete-RPM SHA-256, header SHA-256,
  payload SHA-256, and signing-key identity;
- all three runtime patch hashes and their upstream commit provenance;
- every permitted changed installed path;
- the before/after SHA-256 for four Python sources and their eight derived
  bytecode files.

`rebuild_overlay.py` extracts the pinned RPM without installing it, applies
both patches with zero fuzz, deterministically regenerates only the affected
bytecode, and compares the complete vendor and overlay trees. A path addition,
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
only the twelve manifest-listed file hashes changed.

The direct `NetworkManager-openvpn-gnome` dependency is deliberately retained
because it belongs to Proton's current Core package contract. Removing it may
be reasonable, but requires separate OpenVPN runtime evidence and is not part
of this representation-only overlay.
