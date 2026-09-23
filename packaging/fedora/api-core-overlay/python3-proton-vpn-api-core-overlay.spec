# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

%global __os_install_post %{nil}
%global debug_package %{nil}
%global __requires_exclude ^python3\.14dist\(.*\)$
%global use_source_date_epoch_as_buildtime 1

Name:           python3-proton-vpn-api-core
Version:        5.8.3
Release:        1.plasmavpn1%{?dist}
Summary:        Proton VPN Core with a verified narrow overlay
License:        GPL-3.0-or-later
URL:            https://github.com/ProtonVPN/python-proton-vpn-api-core
Vendor:         Plasma VPN contributors
Source0:        python3-proton-vpn-api-core-5.8.3-1.fc44.x86_64.rpm
Source1:        overlay-manifest.json
Source2:        rebuild_overlay.py
Source3:        protonvpn-fedora-44-public-key.asc
Source4:        test_killswitch_activation.py
Source5:        overlay-manifest.json.license
Patch0:         0001-share-repeated-server-list-strings.patch
Patch1:         0002-avoid-deprecated-fido2-capability-query.patch
Patch2:         0003-explicitly-activate-protection-profiles.patch

BuildRequires:  cpio
BuildRequires:  NetworkManager-libnm
BuildRequires:  patch
BuildRequires:  python3
BuildRequires:  python3-devel
BuildRequires:  python3-dbus-fast
BuildRequires:  python3-distro
BuildRequires:  python3-fido2
BuildRequires:  python3-gobject
BuildRequires:  python3-jinja2
BuildRequires:  python3-packaging
BuildRequires:  python3-proton-core >= 0.5.0
BuildRequires:  python3-pynacl
BuildRequires:  python3-pyxdg
BuildRequires:  python3-sentry-sdk
BuildRequires:  rpm

Requires:       NetworkManager
Requires:       NetworkManager-openvpn
Requires:       NetworkManager-openvpn-gnome
Requires:       gobject-introspection
Requires:       python3-dbus-fast
Requires:       python3-distro
Requires:       python3-fido2
Requires:       python3-gobject
Requires:       python3-jinja2
Requires:       python3-packaging
Requires:       python3-proton-core >= 0.5.0
Requires:       python3-pynacl
Requires:       python3-sentry-sdk
Requires:       systemd
Provides:       python-proton-vpn-api-core = %{version}-%{release}
Provides:       python3.14-proton-vpn-api-core = %{version}-%{release}
Provides:       python3.14dist(proton-vpn-api-core) = %{version}
Provides:       python3dist(proton-vpn-api-core) = %{version}
Provides:       proton-vpn-api-core-plasma-protun-secret = 1

Conflicts:      proton-vpn-cli < 1.0.1~rc1
Conflicts:      proton-vpn-gtk-app < 4.17.1~rc10
Conflicts:      python3-proton-vpn-network-manager < 0.13.5

Obsoletes:      proton-vpn-linux
Obsoletes:      python3-proton-vpn-api-core < 5.5.6
Obsoletes:      python3-proton-vpn-connection
Obsoletes:      python3-proton-vpn-killswitch
Obsoletes:      python3-proton-vpn-lib
Obsoletes:      python3-proton-vpn-local-agent
Obsoletes:      python3-proton-vpn-logger
Obsoletes:      python3-proton-vpn-network-manager
Obsoletes:      python3-proton-vpn-session

%description
Proton's signed Fedora 5.8.3 API Core payload with narrowly verified memory,
diagnostic-hygiene, and Plasma interoperability patches. Proton's upstream
Protun implementation keeps the WireGuard private key in its existing unsaved
NetworkManager profile with system-owned secret flags. NetworkManager holds it
only for the lifetime of the unsaved connection, including root-only volatile
runtime storage when it materializes the profile under /run. The build fails
unless the vendor RPM, patch hashes, changed path set, and resulting
installed-file hashes exactly match the checked-in manifest.

%prep
%{python3} ../../SOURCES/rebuild_overlay.py prepare \
    --manifest ../../SOURCES/overlay-manifest.json \
    --vendor-rpm ../../SOURCES/python3-proton-vpn-api-core-5.8.3-1.fc44.x86_64.rpm \
    --signing-key ../../SOURCES/protonvpn-fedora-44-public-key.asc \
    --source-directory ../../SOURCES \
    --baseline-root vendor-rootfs \
    --overlay-root overlay-rootfs

%build

%check
%{python3} ../../SOURCES/rebuild_overlay.py verify-tree \
    --manifest ../../SOURCES/overlay-manifest.json \
    --baseline-root vendor-rootfs \
    --overlay-root overlay-rootfs
%{python3} ../../SOURCES/rebuild_overlay.py verify-behavior --root overlay-rootfs
%{python3} ../../SOURCES/test_killswitch_activation.py --root overlay-rootfs

%install
mkdir -p "$RPM_BUILD_ROOT"
cp -a overlay-rootfs/. "$RPM_BUILD_ROOT/"
%{python3} ../../SOURCES/rebuild_overlay.py verify-tree \
    --manifest ../../SOURCES/overlay-manifest.json \
    --baseline-root vendor-rootfs \
    --overlay-root "$RPM_BUILD_ROOT"

%files
%defattr(-,root,root,-)
/usr/lib/NetworkManager/VPN/nm-protun.name
/usr/lib64/python3.14/site-packages/proton
/usr/lib64/python3.14/site-packages/proton_vpn_api_core-5.8.3.dist-info
/usr/lib/systemd/system/proton-vpn-kill-switch-boot.service
/usr/libexec/nm-protun-service
/usr/libexec/proton-vpn-kill-switch-service
/usr/share/dbus-1/system-services/me.proton.vpn.kill_switch.service
/usr/share/dbus-1/system.d/me.proton.vpn.kill_switch.conf
/usr/share/dbus-1/system.d/nm-protun-service.conf

%preun
# Turn the kill switch off before the package goes away.
# $1 == 0 is final removal, not an upgrade.
if [ $1 -eq 0 ]; then
    if ! ks_error=$(busctl call \
            me.proton.vpn.kill_switch /me/proton/vpn/kill_switch \
            me.proton.vpn.kill_switch Disable 2>&1); then
        echo "warning: could not disable the Proton VPN kill switch: ${ks_error}" >&2
    fi

    # The symlink was created at runtime, so no package owns it and a
    # plain "remove" leaves it in place. The Disable call above should already remove it
    # but the extra redundancy is added due to the criticality of leaving this unit enabled.
    systemctl disable proton-vpn-kill-switch-boot.service >/dev/null 2>&1 || true
fi

%postun
# A running instance would keep owning me.proton.vpn.kill_switch with a deleted
# binary, blocking activation of the replacement. It may not be running at all,
# hence || true.
# -f because the name exceeds the 15 characters -x matches against.
pkill -f "^/usr/libexec/proton-vpn-kill-switch-service" || true

%changelog
* Wed Sep 23 2026 uglyegg <uglyegg@entropy.quest> - 5.8.3-1.plasmavpn1
- Rebase the verified overlay onto Proton's signed Fedora 5.8.3 payload
- Consume Proton's upstream Protun private-key ownership implementation
- Consolidate the string-sharing series and retain only three bounded patches

* Sun Sep 20 2026 uglyegg <uglyegg@entropy.quest> - 5.7.0-1.plasmavpn1
- Rebase the verified overlay onto Proton's signed Fedora 5.7.0 payload
- Preserve the permanent firewall kill-switch unit and safe-removal contract
- Retain all five bounded Plasma compatibility patches and their regressions

* Sat Sep 12 2026 uglyegg <uglyegg@entropy.quest> - 5.6.20-3.plasmavpn1
- Separate signed vendor-package identity from public source-tag provenance
- Record SPDX provenance for the strict-JSON overlay manifest

* Sat Sep 12 2026 uglyegg <uglyegg@entropy.quest> - 5.6.20-2.plasmavpn1
- Rebase the verified overlay onto Proton's signed Fedora 5.6.20 payload
- Preserve Proton's updated dependency and package-script contracts
- Re-run protection activation and client lifecycle compatibility checks
- Keep RPM metadata stable across distinct clean build roots

* Wed Sep 09 2026 uglyegg <uglyegg@entropy.quest> - 5.6.10-12.plasmavpn1
- Normalize the comparison copy to match NetworkManager's stored protection profiles
- Cover normalized-profile reuse without relaxing settings checks or changing requests

* Wed Sep 09 2026 uglyegg <uglyegg@entropy.quest> - 5.6.10-11.plasmavpn1
- Reuse matching protection profiles and explicitly activate them through NetworkManager
- Bound cancellation and cover manual-disconnect recovery with offline regression tests

* Tue Sep 01 2026 uglyegg <uglyegg@entropy.quest> - 5.6.10-10.plasmavpn1
- Identify the unofficial rebuild with its downstream community vendor.

* Mon Aug 31 2026 uglyegg <uglyegg@entropy.quest> - 5.6.10-9.plasmavpn1
- Expose the manifest-bound Protun interoperability capability and derive the
  output identity from the same verified manifest.

* Mon Aug 31 2026 uglyegg <uglyegg@entropy.quest> - 5.6.10-8.plasmavpn1
- Keep Protun's key system-owned inside its unsaved NetworkManager profile.
- Pass the supplied key directly without requiring a desktop secret agent.
- Retain the existing connection-scoped, volatile profile lifecycle.

* Sat Aug 29 2026 uglyegg <uglyegg@entropy.quest> - 5.6.10-6.plasmavpn1
- Reconstruct the overlay from Proton's exact signed Fedora payload.
- Verify the vendor, patch, path-set, and resulting installed-file hashes.
- Deterministically rebuild only bytecode derived from the three patched files.
- Avoid API Core's internal call to its deprecated FIDO2 capability property.
- Preserve the platform-availability and registered-key truth table.
