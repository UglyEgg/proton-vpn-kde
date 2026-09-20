# Ubuntu API-Core overlay

This source package reconstructs Proton's exact signed-repository
`python3-proton-vpn-api-core_5.6.10_amd64.deb` with the five reviewed Plasma
VPN patches. Patches shared byte-for-byte with Fedora are read from the Fedora
overlay; version-specific Debian overrides live in `patches/`. The vendor
archive, control metadata, maintainer scripts, resolved patch set, installed
path set, file modes, and resulting hashes are checked against
`overlay-manifest.json`.

The official public source tag does not contain the complete build inputs for
the compiled Protun dependency. The Debian source package therefore carries
the exact vendor binary package as a verified upstream component, matching the
Fedora overlay's preserve-and-patch trust boundary. It does not rebuild or
replace Proton's compiled networking components.

Only six Python source files differ from the vendor payload. The required
Protun behavior is tied to
`0004-keep-protun-private-key-ephemeral.patch` and exposed as the versioned
`proton-vpn-api-core-plasma-protun-secret` package capability.
