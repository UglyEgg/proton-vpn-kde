%bcond_without kstatusnotifier

Name:           proton-vpn-kde
Version:        0.8.8
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
    -DCMAKE_INSTALL_LIBEXECDIR=%{_libexecdir} \
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
%defattr(-,root,root,-)
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
* Sat Aug 29 2026 uglyegg <uglyegg@entropy.quest> - 0.8.8-1
- Eliminate application-authored QML diagnostics across native page navigation.
- Add an installed-Core behavior probe and visible warning when the memory overlay is absent.
- Add a version-bounded navigation and clean-shutdown diagnostics smoke test.

* Sat Aug 29 2026 uglyegg <uglyegg@entropy.quest> - 0.8.7-1
- Use absolute backend paths for systemd and D-Bus activation.
- Prevent privilege gain and isolate temporary support attachments.
- Mount system directories read-only without restricting Proton user state.

* Sat Aug 29 2026 uglyegg <uglyegg@entropy.quest> - 0.8.6-2
- Normalize installed payload ownership to root in package metadata.

* Sat Aug 29 2026 uglyegg <uglyegg@entropy.quest> - 0.8.6-1
- Add a generation-scoped scalar projection for interactive global search.
- Keep load, maintenance, and plan availability live in official Core objects.
- Reduce measured full-cache search latency without changing result behavior.

* Sat Aug 29 2026 uglyegg <uglyegg@entropy.quest> - 0.8.5-1
- Remove the obsolete flat-country server endpoint and frontend fallback.
- Keep country browsing exclusively on the grouped location and Secure Core path.
- Add isolated D-Bus coverage for country-to-group-to-server navigation.
- Keep absolute Fedora libexec paths relocatable in staged package validation.

* Sat Aug 29 2026 uglyegg <uglyegg@entropy.quest> - 0.8.4-1
- Recover automatically from transient backend initialization failures.
- Retry reply-confirmed client registration across backend restarts.
- Observe control-operation replies and preserve bounded reconnection retries.

* Sat Aug 29 2026 uglyegg <uglyegg@entropy.quest> - 0.8.3-1
- Sanitize every exported D-Bus method through one stable error boundary.
- Preserve bounded backend-authored validation guidance without exposing raw errors.
- Prevent reconnection exception text from reaching observable client state.

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
