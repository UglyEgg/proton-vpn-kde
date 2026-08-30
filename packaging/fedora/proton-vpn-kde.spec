# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

%bcond_without kstatusnotifier

Name:           proton-vpn-kde
Version:        0.11.2
Release:        24%{?dist}
Summary:        Proton VPN-compatible community client for KDE Plasma

License:        GPL-3.0-or-later
URL:            https://github.com/uglyegg/proton-vpn-kde
Source0:        %{name}-%{version}.tar.gz

BuildRequires:  cmake
BuildRequires:  desktop-file-utils
BuildRequires:  extra-cmake-modules
BuildRequires:  gcc-c++
BuildRequires:  kf6-kconfig-devel
BuildRequires:  kf6-kcoreaddons-devel
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
BuildRequires:  python3-coverage
BuildRequires:  python3-cryptography >= 45.0.1
BuildRequires:  python3-dbus-fast
BuildRequires:  python3-devel
BuildRequires:  python3-mypy
BuildRequires:  qt6-qtbase-devel
BuildRequires:  qt6-qtdeclarative-devel
BuildRequires:  qt6-linguist

Requires:       kf6-kirigami
Requires:       kf6-kglobalaccel
Requires:       kf6-kcmutils
Requires:       kf6-krunner
Requires:       python3-cryptography >= 45.0.1
Requires:       python3-dbus-fast
Requires:       python3-fido2
Requires:       python3-proton-vpn-api-core >= 5.5.6
Requires:       proton-keyring-secret-service-provider-agnostic >= 1
Requires:       qt6-qtdeclarative

%description
Plasma VPN is an unofficial native Qt 6 and Kirigami frontend compatible with
Proton VPN. It reuses Proton's official Python VPN core. VPN protocols,
NetworkManager integration, kill-switch behavior, split tunneling, and session
persistence remain owned by the official core. The frontend has no direct GTK
or GNOME Keyring dependency and uses the Freedesktop Secret Service provider
selected by the desktop session. The official API Core package may retain its
own desktop integration dependencies.

%prep
%autosetup -n %{name}-%{version}

%build
%cmake \
    -DBUILD_TESTING=ON \
    -DCMAKE_INSTALL_LIBEXECDIR=%{_libexecdir} \
    -DKDE_INSTALL_LIBEXECDIR=%{_libexecdir} \
    -DKDE_INSTALL_SBINDIR=%{_sbindir} \
    -DPROTON_VPN_KDE_ENABLE_SUPPORT_REPORT_SUBMISSION=OFF \
    -DPROTON_VPN_KDE_ENABLE_CRASH_REPORT_SUBMISSION=OFF \
%if %{without kstatusnotifier}
    -DCMAKE_DISABLE_FIND_PACKAGE_KF6StatusNotifierItem=ON \
%endif
    -DCMAKE_BUILD_TYPE=RelWithDebInfo
%cmake_build

%check
scripts/check-python-analysis.sh
%ctest

%install
%cmake_install
desktop-file-validate \
    %{buildroot}%{_datadir}/applications/proton-vpn-kde.desktop

%post
%systemd_user_post proton-vpn-kde-backend.service proton-vpn-kde-agent.service

%preun
%systemd_user_preun proton-vpn-kde-backend.service proton-vpn-kde-agent.service

%posttrans
%systemd_user_posttrans_with_restart proton-vpn-kde-backend.service proton-vpn-kde-agent.service

%files
%defattr(-,root,root,-)
%license LICENSE COPYING.md
%doc README.md CHANGELOG.md CONTRIBUTING.md SECURITY.md SUPPORT.md
%doc THIRD_PARTY_NOTICES.md docs
%{_bindir}/proton-vpn-kde
%{_bindir}/proton-vpn-kde-agent
%{_bindir}/proton-vpn-kde-backend
%{_libexecdir}/proton-vpn-kde/
%{_datadir}/applications/proton-vpn-kde.desktop
%{_datadir}/applications/kcm_proton_vpn_kde.desktop
%{_datadir}/dbus-1/services/quest.entropy.PlasmaVPN.Backend.service
%{_datadir}/dbus-1/services/quest.entropy.PlasmaVPN.Agent.service
%{_datadir}/dbus-1/services/quest.entropy.PlasmaVPN.ControlCenter.service
%{_datadir}/dbus-1/interfaces/quest.entropy.PlasmaVPN.Backend1.xml
%{_datadir}/dbus-1/interfaces/quest.entropy.PlasmaVPN.Agent1.xml
%{_datadir}/dbus-1/interfaces/quest.entropy.PlasmaVPN.ControlCenter1.xml
%{_datadir}/icons/hicolor/scalable/apps/plasma-vpn.svg
%{_datadir}/icons/hicolor/scalable/apps/plasma-vpn-light.svg
%{_datadir}/icons/hicolor/scalable/apps/plasma-vpn-dark.svg
%{_datadir}/knotifications6/proton-vpn-kde.notifyrc
%{_datadir}/proton-vpn-kde/translations/
%{_kf6_plugindir}/krunner/proton-vpn-kde-runner.so
%{_qt6_plugindir}/plasma/kcms/systemsettings/kcm_proton_vpn_kde.so
%{_userunitdir}/proton-vpn-kde-backend.service
%{_userunitdir}/proton-vpn-kde-agent.service

%changelog
* Sun Aug 30 2026 uglyegg <uglyegg@entropy.quest> - 0.11.2-24
- Recover the Control Center after an unexpected backend service exit.
- Explain package-upgrade client authentication failures without retry churn.

* Sun Aug 30 2026 uglyegg <uglyegg@entropy.quest> - 0.11.2-23
- Make keep-connected tray shutdown explicit.
- Add a confirmed disconnect-and-quit path that fails safely on timeout.

* Sun Aug 30 2026 uglyegg <uglyegg@entropy.quest> - 0.11.2-22
- Keep server-browser cleanup scoped to its owning page context.
- Retry transiently empty country-group snapshots without manual refresh.

* Sun Aug 30 2026 uglyegg <uglyegg@entropy.quest> - 0.11.2-21
- Isolate deterministic demo behavior from the official Core adapter.

* Sun Aug 30 2026 uglyegg <uglyegg@entropy.quest> - 0.11.2-20
- Separate backend state models and payload validation from orchestration.

* Sun Aug 30 2026 uglyegg <uglyegg@entropy.quest> - 0.11.2-19
- Split the native controller by actions, locations, settings, and lifecycle.

* Sun Aug 30 2026 uglyegg <uglyegg@entropy.quest> - 0.11.2-18
- Test Python 3.11 with hash-pinned minimum backend dependencies.
- Verify the consumed public API against Proton's pinned Core 5.5.6 RPM.

* Sun Aug 30 2026 uglyegg <uglyegg@entropy.quest> - 0.11.2-17
- Respect the package builder's temporary directory during Python analysis.

* Sun Aug 30 2026 uglyegg <uglyegg@entropy.quest> - 0.11.2-16
- Generate native and Python D-Bus constants from installed XML contracts.
- Verify the live Python service signatures and authorization policy against XML.

* Sun Aug 30 2026 uglyegg <uglyegg@entropy.quest> - 0.11.2-15
- Add enforced SPDX provenance to project-authored source and build files.

* Sun Aug 30 2026 uglyegg <uglyegg@entropy.quest> - 0.11.2-14
- Add blocking Clang-Tidy and address/leak/undefined-behavior sanitizer CI.
- Remove avoidable Qt container conversions and make size narrowing explicit.

* Sun Aug 30 2026 uglyegg <uglyegg@entropy.quest> - 0.11.2-13
- Enforce Python type analysis and measured branch coverage in CI and RPM checks.

* Sun Aug 30 2026 uglyegg <uglyegg@entropy.quest> - 0.11.2-12
- Require the separately packaged provider-neutral Proton keyring capability.
- Build the audited keyring overlay and its source RPM in release CI.

* Sun Aug 30 2026 uglyegg <uglyegg@entropy.quest> - 0.11.2-11
- Remove the prescriptive upstream-engagement guide from the public documentation.
- Let GitHub render README prose without a fixed source-column width.
- Clarify the GTK-free frontend boundary without hiding Core's transitive dependency.

* Sun Aug 30 2026 uglyegg <uglyegg@entropy.quest> - 0.11.2-10
- Build and inspect source and binary RPMs in a dedicated Fedora CI workflow.
- Keep Proton VPN API Core as a runtime dependency, not an unused build dependency.

* Sun Aug 30 2026 uglyegg <uglyegg@entropy.quest> - 0.11.2-9
- Consolidate public documentation and separate current audit posture from history.
- Add a public-facing README gallery with reproducible demo screenshots.
- Record the downstream Proton keyring build required by verified KeePassXC support.
- Remove obsolete Fedora and runtime-diagnostics worklog documents.

* Sun Aug 30 2026 uglyegg <uglyegg@entropy.quest> - 0.11.2-8
- Remove the shared KRunner host from the backend trusted-client allowlist.
- Route four validated connection requests through explicit Control Center confirmation.
- Add adversarial coverage proving KRunner cannot call the backend directly.

* Sun Aug 30 2026 uglyegg <uglyegg@entropy.quest> - 0.11.2-7
- Disable and persist anonymous crash reporting in unofficial builds.
- Explain the reporting policy in Settings and reject attempts to re-enable it.

* Sun Aug 30 2026 uglyegg <uglyegg@entropy.quest> - 0.11.2-6
- Make deepest server-browser requests win and retry transient empty snapshots.
- Keep Plasma pin actions available in search with native pin artwork.
- Add persistent state, city, and Secure Core group tray connections.

* Sun Aug 30 2026 uglyegg <uglyegg@entropy.quest> - 0.11.2-5
- Replace exclusive capability selection with AND-combinable checkboxes.
- Filter server browsing and scoped fastest actions by selected capabilities.
- Persist shared default fastest filters for every Plasma connection entry point.

* Sun Aug 30 2026 uglyegg <uglyegg@entropy.quest> - 0.11.2-4
- Queue server-browser requests across backend initialization.
- Add Proton-ranked fastest P2P, Streaming, Tor, and Secure Core selection.
- Validate and authorize the additive capability-selection D-Bus operation.

* Sun Aug 30 2026 uglyegg <uglyegg@entropy.quest> - 0.11.2-3
- Preserve procfs-based D-Bus client authorization under Fedora SELinux.
- Remove incompatible mount namespaces from the unprivileged user services.
- Retain NoNewPrivileges and interpreter, loader, and UI injection cleanup.

* Sun Aug 30 2026 uglyegg <uglyegg@entropy.quest> - 0.11.2-2
- Accept Fedora's immutable root-owned global systemd user-service policy.
- Continue rejecting user-owned, writable, and mixed-trust service overrides.
- Add host-ownership regression coverage for backend identity verification.

* Sun Aug 30 2026 uglyegg <uglyegg@entropy.quest> - 0.11.2-1
- Authenticate and pin the packaged backend's unique D-Bus owner.
- Authorize mutations by actual sender and bind secret keys to each operation.
- Roll back the Core kill-switch setting on every incomplete sign-out.
- Close unexpected descriptors and byte-bound optional support logs.
- Validate Core's packet-capture cap and serialize the 15-minute watchdog.
- Add the security audit and post-remediation regression evidence.
- Add selectable color, light-symbol, and dark-symbol interface icons.
- Apply icon changes live to the Control Center and resident tray agent.
- Expose the shared preference in both Settings and Plasma System Settings.
- Disable direct Proton support-report submission in unofficial builds.
- Distinguish Release Notes with a bound-notebook navigation icon.

* Sat Aug 29 2026 uglyegg <uglyegg@entropy.quest> - 0.11.1-1
- Embed the application mark for reliable window and tray presentation.
- Destroy removed Kirigami pages and prevent stale sign-in routing.
- Exercise settings changes through the frontend controller in regression tests.

* Sat Aug 29 2026 uglyegg <uglyegg@entropy.quest> - 0.11.0-1
- Adopt an original Plasma VPN identity and explicit community-client status.
- Move private session services into the quest.entropy.PlasmaVPN namespace.
- Add public-release CI, provenance, contribution, support, and release guidance.

* Sat Aug 29 2026 uglyegg <uglyegg@entropy.quest> - 0.10.2-1
- Keep Settings active after successful VPN configuration changes.
- Limit automatic Overview routing to the native sign-in flow.
- Add settings-navigation regression coverage.

* Sat Aug 29 2026 uglyegg <uglyegg@entropy.quest> - 0.10.1-1
- Route signed-out startup directly to the native sign-in page.
- Prevent authentication from racing backend and Proton connector startup.
- Explain delayed desktop Secret Service approval during sign-in.
- Add signed-out startup and pre-ready authentication regression coverage.

* Sat Aug 29 2026 uglyegg <uglyegg@entropy.quest> - 0.10.0-1
- Add responsive desktop and compact Kirigami navigation.
- Group connection, settings, account, and support content in native cards.
- Standardize location rows, semantic colors, typography, and RTL behavior.
- Add scaled-text, compact-window, RTL, hygiene, and screenshot checks.

* Sat Aug 29 2026 uglyegg <uglyegg@entropy.quest> - 0.9.0-2
- Release abandoned Secret Service startup after the frontend disappears.
- Protect explicit tray actions with a bounded transient backend lease.

* Sat Aug 29 2026 uglyegg <uglyegg@entropy.quest> - 0.9.0-1
- Split Plasma tray, shortcuts, and notifications into a lean resident agent.
- Let the full Control Center exit on close without disconnecting the VPN.
- Keep the agent lease-free so the disconnected Python backend can shut down.

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
