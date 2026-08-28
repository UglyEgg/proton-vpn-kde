%bcond_without kstatusnotifier

Name:           proton-vpn-kde
Version:        0.6.0
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
BuildRequires:  kf6-knotifications-devel
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

Requires:       kf6-kirigami
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

%files
%license LICENSE COPYING.md
%doc README.md docs
%{_bindir}/proton-vpn-kde
%{_bindir}/proton-vpn-kde-backend
%{_libexecdir}/proton-vpn-kde/
%{_datadir}/applications/proton-vpn-kde.desktop
%{_datadir}/dbus-1/services/proton.vpn.app.kde.backend.service
%{_datadir}/icons/hicolor/scalable/apps/proton-vpn-kde.svg
%{_datadir}/knotifications6/proton-vpn-kde.notifyrc
%{_userunitdir}/proton-vpn-kde-backend.service

%changelog
* Thu Aug 27 2026 uglyegg <uglyegg@entropy.quest> - 0.6.0-1
- Add native, conflict-aware Proton VPN settings.
- Keep settings persistence and feature constraints in the official core.
- Isolate D-Bus smoke tests from installed service activation.

* Thu Aug 27 2026 uglyegg <uglyegg@entropy.quest> - 0.5.0-1
- Package the native Qt 6 and Kirigami client with D-Bus activation.
- Add native sign-in with provider-neutral Secret Service persistence.
- Add incremental server load updates and load-based server ordering.
