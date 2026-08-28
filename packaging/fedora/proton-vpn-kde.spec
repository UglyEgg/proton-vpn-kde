%bcond_without kstatusnotifier

Name:           proton-vpn-kde
Version:        0.8.2
Release:        1%{?dist}
Summary:        Native KDE Plasma frontend for Proton VPN

License:        GPL-3.0-or-later
URL:            https://protonvpn.com/
Source0:        %{name}-%{version}.tar.gz

BuildRequires:  cmake
BuildRequires:  desktop-file-utils
BuildRequires:  extra-cmake-modules
BuildRequires:  gcc-c++
BuildRequires:  kf6-kconfig-devel
BuildRequires:  kf6-kcoreaddons-devel
BuildRequires:  kf6-kdbusaddons-devel
BuildRequires:  kf6-kglobalaccel-devel
BuildRequires:  kf6-kcmutils-devel
BuildRequires:  kf6-knotifications-devel
BuildRequires:  kf6-krunner-devel
BuildRequires:  kf6-kservice-devel
%if %{with kstatusnotifier}
BuildRequires:  kf6-kstatusnotifieritem-devel
%endif
BuildRequires:  ninja-build
BuildRequires:  openssl-devel
BuildRequires:  python3-cryptography
BuildRequires:  python3-dbus-fast
BuildRequires:  python3-devel
BuildRequires:  python3-proton-vpn-api-core
BuildRequires:  qt6-qtbase-devel
BuildRequires:  qt6-qtdeclarative-devel
BuildRequires:  qt6-linguist

Requires:       kf6-kirigami
Requires:       kf6-kdbusaddons
Requires:       kf6-kglobalaccel
Requires:       kf6-kcmutils
Requires:       kf6-krunner
Requires:       python3-cryptography
Requires:       python3-dbus-fast
Requires:       python3-fido2
Requires:       python3-proton-vpn-api-core >= 5.5.6
Requires:       qt6-qtdeclarative

%description
Proton VPN for KDE Plasma is a native Qt 6 and Kirigami frontend that reuses
Proton's official Python VPN core. Networking, protocols, NetworkManager,
kill-switch behavior, split tunneling, and session persistence remain owned by
the official core. The frontend has no GTK or GNOME Keyring dependency and
uses the Freedesktop Secret Service provider selected by the desktop session.

%prep
%autosetup -n %{name}-%{version}

%build
%cmake \
    -DBUILD_TESTING=ON \
%if %{without kstatusnotifier}
    -DCMAKE_DISABLE_FIND_PACKAGE_KF6StatusNotifierItem=ON \
%endif
    -DCMAKE_BUILD_TYPE=RelWithDebInfo
%cmake_build

%check
%ctest

%install
%cmake_install
install -d %{buildroot}%{_userunitdir}
mv %{buildroot}%{_libdir}/systemd/user/proton-vpn-kde-backend.service \
    %{buildroot}%{_userunitdir}/
desktop-file-validate \
    %{buildroot}%{_datadir}/applications/proton-vpn-kde.desktop

%post
%systemd_user_post proton-vpn-kde-backend.service

%preun
%systemd_user_preun proton-vpn-kde-backend.service

%posttrans
%systemd_user_posttrans_with_restart proton-vpn-kde-backend.service

%files
%license LICENSE COPYING.md
%doc README.md docs
%{_bindir}/proton-vpn-kde
%{_bindir}/proton-vpn-kde-backend
%{_libexecdir}/proton-vpn-kde/
%{_datadir}/applications/proton-vpn-kde.desktop
%{_datadir}/applications/kcm_proton_vpn_kde.desktop
%{_datadir}/dbus-1/services/proton.vpn.app.kde.backend.service
%{_datadir}/icons/hicolor/scalable/apps/proton-vpn-kde.svg
%{_datadir}/knotifications6/proton-vpn-kde.notifyrc
%{_datadir}/proton-vpn-kde/translations/
%{_kf6_plugindir}/krunner/proton-vpn-kde-runner.so
%{_qt6_plugindir}/plasma/kcms/systemsettings/kcm_proton_vpn_kde.so
%{_userunitdir}/proton-vpn-kde-backend.service

%changelog
* Fri Aug 28 2026 uglyegg <uglyegg@entropy.quest> - 0.8.2-1
- Enforce one backend owner and release disconnected idle backends on demand.
- Track live Plasma clients without sacrificing active-tunnel supervision.
- Defer country model construction until the Locations page is opened.

* Fri Aug 28 2026 uglyegg <uglyegg@entropy.quest> - 0.8.1-1
- Restart a running user backend after upgrades so the GUI and D-Bus API stay in sync.
- Add Plasma global shortcuts and native KRunner connection actions.
- Add a native System Settings module with live KConfig synchronization.

* Fri Aug 28 2026 uglyegg <uglyegg@entropy.quest> - 0.8.0-1
- Add a native custom-DNS editor with IPv4 and IPv6 validation.
- Preserve Proton core per-entry state and use its official save path.
- Reject NetShield conflicts without silently changing either feature.

* Fri Aug 28 2026 uglyegg <uglyegg@entropy.quest> - 0.7.0-1
- Add a native Plasma split-tunneling application editor.
- Discover installed applications through KService without GTK or Gio.
- Preserve Proton core's existing IP rules and compatibility constraints.

* Thu Aug 27 2026 uglyegg <uglyegg@entropy.quest> - 0.6.0-1
- Add native, conflict-aware Proton VPN settings.
- Keep settings persistence and feature constraints in the official core.
- Isolate D-Bus smoke tests from installed service activation.

* Thu Aug 27 2026 uglyegg <uglyegg@entropy.quest> - 0.5.0-1
- Package the native Qt 6 and Kirigami client with D-Bus activation.
- Add native sign-in with provider-neutral Secret Service persistence.
- Add incremental server load updates and load-based server ordering.
