# Ubuntu API-Core overlay

Reconstructs Proton's authenticated repository package
`python3-proton-vpn-api-core_5.8.11_amd64.deb`. The four patch inputs are pinned
local copies of the Fedora 5.8.11 series: server string sharing, FIDO2 capability
query, explicit protection-profile activation, and the empty initial route event
guard. Only six Python source bodies differ; compiled networking is unchanged.
The boot unit moves from the aliased /lib path to /usr/lib with its bytes and
mode pinned in the manifest; every other installed path is preserved.

`overlay-manifest.json` owns archive/control/script hashes, source-base metadata,
patch hashes, changed paths/modes and result hashes. Proton supplies the Protun
system-owned transient secret behavior; the capability verifier checks it.
No obsolete private-key patch is applied to this vendor version.

The boot-protection unit retains Proton's disabled default and existing user
choice. Generated systemd hooks and preserved Python/removal hooks retain its
upgrade and final-removal behavior. Installation must not enable permanent mode.

The original archive has a new 5.8.11 identity; the published 5.6.10 original is
not replaced. The source package carries the verified vendor binary because
public tags do not provide complete compiled Protun build inputs. It does not
rebuild those components. Build and qualification commands are owned by the
[release procedure](../../../docs/RELEASING.md).
