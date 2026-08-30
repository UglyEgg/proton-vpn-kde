%global __os_install_post %{nil}
%global debug_package %{nil}
%global __requires_exclude ^python3\.14dist\(.*\)$

Name:           python3-proton-vpn-api-core
Version:        5.6.10
Release:        6.plasmavpn1%{?dist}
Summary:        Proton VPN Core with a verified narrow overlay
License:        GPL-3.0-or-later
URL:            https://github.com/ProtonVPN/python-proton-vpn-api-core
Vendor:         Proton AG <opensource@proton.me>
Source0:        python3-proton-vpn-api-core-5.6.10-1.fc44.x86_64.rpm
Source1:        overlay-manifest.json
Source2:        rebuild_overlay.py
Patch0:         0001-share-repeated-server-endpoint-strings.patch
Patch1:         0002-share-server-strings-during-cache-decoding.patch
Patch2:         0003-avoid-deprecated-fido2-capability-query.patch

BuildRequires:  cpio
BuildRequires:  patch
BuildRequires:  python3
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
Proton's signed Fedora 5.6.10 API Core payload with two narrowly verified
representation-only patches that share repeated immutable server strings and
one diagnostic-hygiene patch that avoids a deprecated FIDO2 capability query.
The build fails unless the vendor RPM, patch hashes, changed path set, and
resulting installed-file hashes exactly match the checked-in manifest.

%prep
%{python3} %{SOURCE2} prepare \
    --manifest %{SOURCE1} \
    --vendor-rpm %{SOURCE0} \
    --source-directory %{_sourcedir} \
    --baseline-root vendor-rootfs \
    --overlay-root overlay-rootfs

%build

%check
%{python3} %{SOURCE2} verify-tree \
    --manifest %{SOURCE1} \
    --baseline-root vendor-rootfs \
    --overlay-root overlay-rootfs
%{python3} %{SOURCE2} verify-behavior --root overlay-rootfs

%install
mkdir -p %{buildroot}
cp -a overlay-rootfs/. %{buildroot}/
%{python3} %{SOURCE2} verify-tree \
    --manifest %{SOURCE1} \
    --baseline-root vendor-rootfs \
    --overlay-root %{buildroot}

%files
%defattr(-,root,root,-)
/usr/lib/NetworkManager/VPN/nm-protun.name
/usr/lib64/python3.14/site-packages/proton
/usr/lib64/python3.14/site-packages/proton_vpn_api_core-5.6.10.dist-info
/usr/libexec/nm-protun-auth-dialog
/usr/libexec/nm-protun-service
/usr/libexec/proton-vpn-kill-switch-service
/usr/share/dbus-1/system-services/me.proton.vpn.kill_switch.service
/usr/share/dbus-1/system.d/me.proton.vpn.kill_switch.conf
/usr/share/dbus-1/system.d/nm-protun-service.conf

%preun
# Runs before the package is removed, while the kill switch service and its
# D-Bus policy still exist, so D-Bus activation can still service the call.
# $1 == 0 means final removal rather than an upgrade: an upgrade must not turn
# the user's kill switch off.
if [ $1 -eq 0 ]; then
    if ! ks_error=$(busctl call \
            me.proton.vpn.kill_switch /me/proton/vpn/kill_switch \
            me.proton.vpn.kill_switch Disable 2>&1); then
        echo "warning: could not disable the Proton VPN kill switch: ${ks_error}" >&2
    fi
fi

%postun
# Runs after the old package is removed.
# The kill switch service is D-Bus activated by preun's Disable call, so it is
# running here. Left alone it would keep owning me.proton.vpn.kill_switch with a
# deleted binary. -f because the name exceeds the 15 character limit for -x.
pkill -f "^/usr/libexec/proton-vpn-kill-switch-service" || true

%changelog
* Sat Aug 29 2026 uglyegg <uglyegg@entropy.quest> - 5.6.10-6.plasmavpn1
- Reconstruct the overlay from Proton's exact signed Fedora payload.
- Verify the vendor, patch, path-set, and resulting installed-file hashes.
- Deterministically rebuild only bytecode derived from the three patched files.
- Avoid API Core's internal call to its deprecated FIDO2 capability property.
- Preserve the platform-availability and registered-key truth table.
