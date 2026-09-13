# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

%bcond_without kstatusnotifier

%global use_source_date_epoch_as_buildtime 1
%global _buildhost reproducible.invalid

Name:           proton-vpn-kde
Version:        0.13.0
Release:        0.10%{?dist}
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
BuildRequires:  plasma-breeze-common
BuildRequires:  plasma-integration
BuildRequires:  python3-coverage
BuildRequires:  python3-cryptography >= 45.0.1
BuildRequires:  python3-dbus-fast
BuildRequires:  python3-devel
BuildRequires:  python3-mypy
BuildRequires:  qt6-qtbase-devel
BuildRequires:  qt6-qtdeclarative-devel
BuildRequires:  qt6-linguist
BuildRequires:  ripgrep

Requires:       kf6-kirigami
Requires:       kf6-kglobalaccel
Requires:       kf6-kcmutils
Requires:       kf6-krunner
Requires:       /usr/bin/ip
Requires:       python3-cryptography >= 45.0.1
Requires:       python3-dbus-fast
Requires:       python3-fido2
Requires:       python3-proton-vpn-api-core >= 5.6.10
Requires:       proton-vpn-api-core-plasma-protun-secret >= 1
Requires:       proton-keyring-secret-service-owner-pinned >= 1
Requires:       qt6-qtdeclarative

%description
Plasma VPN is an unofficial native Qt 6 and Kirigami frontend compatible with
Proton VPN. It reuses Proton's official Python VPN core. VPN protocols,
NetworkManager integration, kill-switch behavior, split tunneling, and session
persistence remain owned by the official core. The separately packaged,
version-pinned API-Core overlay keeps Protun's secret inside its existing
unsaved NetworkManager profile so Plasma does not require a missing Protun
secret plugin. That same audited rebuild carries the project's independently
tested server-string memory reductions and an upstream diagnostic cleanup; its
Protun capability gates only the required connection semantic. The frontend
has no direct GTK or GNOME Keyring dependency and uses the Freedesktop Secret
Service provider selected by the desktop session. The official API Core
package may retain its own desktop integration dependencies.

%prep
%autosetup -n %{name}-%{version}
cp -p .source-commit SOURCE_COMMIT

%build
# RPM's changelog epoch has day precision. Give Qt resources the archive's
# exact commit timestamp so same-day upgrades invalidate cached QML.
# RCC gives SOURCE_DATE_EPOCH precedence over QT_RCC_SOURCE_DATE_OVERRIDE.
export SOURCE_DATE_EPOCH="$(stat -c %Y .source-commit)"
%cmake \
    -DBUILD_TESTING=ON \
    -DCMAKE_INSTALL_LIBEXECDIR=%{_libexecdir} \
    -DKDE_INSTALL_LIBEXECDIR=%{_libexecdir} \
    -DKDE_INSTALL_SBINDIR=%{_sbindir} \
    -DPROTON_VPN_KDE_RUNTIME_TRANSLATIONS_DIR=%{_datadir}/proton-vpn-kde/translations \
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
%systemd_user_post proton-vpn-kde-backend.service proton-vpn-kde-agent.service proton-vpn-kde-control-center.service

%preun
%systemd_user_preun proton-vpn-kde-backend.service proton-vpn-kde-agent.service proton-vpn-kde-control-center.service

%posttrans
%systemd_user_posttrans_with_restart proton-vpn-kde-backend.service proton-vpn-kde-agent.service proton-vpn-kde-control-center.service

%files
%defattr(-,root,root,-)
%license LICENSE COPYING.md
%doc README.md CHANGELOG.md CONTRIBUTING.md SECURITY.md SUPPORT.md
%doc THIRD_PARTY_NOTICES.md docs SOURCE_COMMIT
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
%{_datadir}/icons/hicolor/scalable/apps/quest.entropy.PlasmaVPN.svg
%{_datadir}/icons/hicolor/scalable/apps/plasma-vpn-light.svg
%{_datadir}/icons/hicolor/scalable/apps/plasma-vpn-dark.svg
%{_datadir}/knotifications6/proton-vpn-kde.notifyrc
%{_datadir}/proton-vpn-kde/translations/
%{_kf6_plugindir}/krunner/proton-vpn-kde-runner.so
%{_qt6_plugindir}/plasma/kcms/systemsettings/kcm_proton_vpn_kde.so
%{_userunitdir}/proton-vpn-kde-backend.service
%{_userunitdir}/proton-vpn-kde-agent.service
%{_userunitdir}/proton-vpn-kde-control-center.service

%changelog
* Sat Sep 12 2026 uglyegg <uglyegg@entropy.quest> - 0.13.0-0.10
- Complete SPDX provenance for installed Python templates and strict JSON sources
- Separate signed Core package identity from public source-tag provenance
- Align public/internal release history and refresh the application gallery

* Wed Sep 09 2026 uglyegg <uglyegg@entropy.quest> - 0.13.0-0.9
- Keep ordinary startup failures visible without repeated Secret Service prompts
- Distinguish restored sessions from failed VPN connector initialization

* Wed Sep 09 2026 uglyegg <uglyegg@entropy.quest> - 0.13.0-0.8
- Normalize inherited native loader settings before direct GUI/agent startup
- Preserve backend sender authorization and add kernel-environment regressions

* Wed Sep 09 2026 uglyegg <uglyegg@entropy.quest> - 0.13.0-0.7
- Point translation tests at build-owned catalogs and isolate fallback paths.
- Declare the Breeze schemes and KDE platform theme used by visual fixtures.
- Keep application translation paths, UI and networking unchanged.

* Wed Sep 09 2026 uglyegg <uglyegg@entropy.quest> - 0.13.0-0.6
- Isolate test desktop directories before Core imports and cache-path capture.
- Use explicit fake route/session probes and bounded fixture waits in tests.
- Add cold-import regression coverage; application runtime sources are unchanged.

* Wed Sep 09 2026 uglyegg <uglyegg@entropy.quest> - 0.13.0-0.5
- Consume startup auto-connect intent once and finish tray activation before exit.
- Report rejected preference writes and retain the actual stored UI state.
- Render confirmation data literally and repair offline benchmark fixtures.
- Include focused regression coverage and the bounded review evidence.

* Tue Sep 08 2026 uglyegg <uglyegg@entropy.quest> - 0.13.0-0.4
- Add opt-in login launch and shared window/tray and auto-connect settings.
- Smooth split-route graphics and improve text contrast and keyboard feedback.
- Simplify release highlights and refresh the project presentation.
- Stamp Qt resources with the source commit epoch to invalidate stale QML caches.

* Tue Sep 08 2026 uglyegg <uglyegg@entropy.quest> - 0.13.0-0.3
- Fit the window to the layout; disable manual resizing and maximizing.
- Center the horizontal route, group VPN facts and curve the outside-VPN fork.

* Tue Sep 08 2026 uglyegg <uglyegg@entropy.quest> - 0.13.0-0.2
- Integrate split routing into the connection graphic and contain the report form.
- Use an unambiguous desktop icon name across Plasma icon themes.
- Add compact, large-text and RTL presentation regressions.

* Thu Sep 03 2026 uglyegg <uglyegg@entropy.quest> - 0.13.0-0.1
- Begin the presentation-only progressive Plasma interface cycle.
- Add a CI gate that freezes the accepted 0.12.0 runtime mechanics.
- Make in-app release history concise and progressively disclosed.
- Fence asynchronous replies and side effects to their owning account,
  operation, settings, capture, survey, and connection generations.
- Retire manual and automatic connection owners before superseding operations,
  including Core 5.6.10 executor-backed NetworkManager work.
- Drain Core 5.6.10 queued replacement targets to confirmed Disconnected state
  and fail closed when the stable Down sequence cannot complete.
- Declare Core 5.6.10 as the package runtime floor; keep 5.5.6 static-only.
- Bound orderly and completion-unknown backend teardown with fail-closed
  systemd restart behavior.

* Tue Sep 01 2026 uglyegg <uglyegg@entropy.quest> - 0.12.0-0.29
- Suppress pre-readiness adapter snapshots during Core initialization.
- Publish one authoritative state after session services are ready.

* Tue Sep 01 2026 uglyegg <uglyegg@entropy.quest> - 0.12.0-0.28
- Bound Core connector restoration while capture recovery is pending.
- Retain the journal for nonzero retry when a system D-Bus dependency stalls.

* Tue Sep 01 2026 uglyegg <uglyegg@entropy.quest> - 0.12.0-0.27
- Retain capture recovery when Core cannot restore a logged-in session.
- Reject Core's synthetic logged-out disconnected recovery state.

* Tue Sep 01 2026 uglyegg <uglyegg@entropy.quest> - 0.12.0-0.26
- Bound Secret Service restoration while packet-capture recovery is pending.
- Preserve durable recovery for nonzero systemd retry after provider timeout.

* Tue Sep 01 2026 uglyegg <uglyegg@entropy.quest> - 0.12.0-0.25
- Recover unconfirmed packet capture before interactive session restoration.

* Tue Sep 01 2026 uglyegg <uglyegg@entropy.quest> - 0.12.0-0.24
- Prevent idle startup from abandoning packet-capture recovery.

* Tue Sep 01 2026 uglyegg <uglyegg@entropy.quest> - 0.12.0-0.23
- Preserve unconfirmed packet-capture supervision across backend replacement.
- Retry bounded Core stop calls until capture completion is confirmed.

* Tue Sep 01 2026 uglyegg <uglyegg@entropy.quest> - 0.12.0-0.22
- Reject D-Bus authorization when owner loss races identity verification.
- Preserve the signed-out state when settings writes encounter session expiry.

* Tue Sep 01 2026 uglyegg <uglyegg@entropy.quest> - 0.12.0-0.21
- Reconcile ambiguous login, connection, and settings completion from Core.
- Compensate partially committed settings writes before resuming operation.

* Tue Sep 01 2026 uglyegg <uglyegg@entropy.quest> - 0.12.0-0.20
- Keep build-tree paths out of installed translation lookup metadata.
- Compare clean package rebuilds under one normalized RPM build path.

* Tue Sep 01 2026 uglyegg <uglyegg@entropy.quest> - 0.12.0-0.19
- Normalize RPM header build time and host metadata.
- Compare complete output sets from two independent package builds.

* Tue Sep 01 2026 uglyegg <uglyegg@entropy.quest> - 0.12.0-0.18
- Publish the backend D-Bus name only after its authorization ingress and
  exported service object are ready.

* Tue Sep 01 2026 uglyegg <uglyegg@entropy.quest> - 0.12.0-0.17
- Remove remote Control Center shutdown and authorize agent shutdown.
- Export only explicitly allowlisted native frontend slots.

* Tue Sep 01 2026 uglyegg <uglyegg@entropy.quest> - 0.12.0-0.16
- Reject mixed overlay patch line endings and truncated hunk content.
- Reapply a partially persisted kill-switch disable operation on retry.

* Tue Sep 01 2026 uglyegg <uglyegg@entropy.quest> - 0.12.0-0.15
- Parse overlay patch bytes only on LF boundaries.
- Reject bare carriage returns while accepting ordinary CRLF patches.

* Tue Sep 01 2026 uglyegg <uglyegg@entropy.quest> - 0.12.0-0.14
- Parse unified-diff hunk sizes in the overlay whitespace gate.
- Cover headers, context, normal additions, and ++-prefixed target content.

* Tue Sep 01 2026 uglyegg <uglyegg@entropy.quest> - 0.12.0-0.13
- Distinguish required unified-diff context markers from target whitespace.
- Check overlay-added target lines with a dedicated source gate.

* Tue Sep 01 2026 uglyegg <uglyegg@entropy.quest> - 0.12.0-0.12
- Keep capture setup inactive when Core rejects the selected destination.
- Sanitize provider assignment failures and preserve immediate retryability.

* Tue Sep 01 2026 uglyegg <uglyegg@entropy.quest> - 0.12.0-0.11
- Bound every Proton Core packet-capture stop attempt.
- Keep the original capture watchdog armed during compensation.
- Prove a non-returning Core stop cannot indefinitely block backend shutdown.

* Tue Sep 01 2026 uglyegg <uglyegg@entropy.quest> - 0.12.0-0.10
- Compensate cancelled and completion-unknown packet-capture starts.
- Keep reconnection enablement transactional and cleanup failure-safe.
- Preserve non-missing route-probe failures for bounded retry diagnostics.

* Tue Sep 01 2026 uglyegg <uglyegg@entropy.quest> - 0.12.0-0.9
- Sanitize the Control Center environment before D-Bus activation.
- Pin System Settings, Control Center, and resident-agent launch paths.
- Remove the route-probe executable preflight race.

* Tue Sep 01 2026 uglyegg <uglyegg@entropy.quest> - 0.12.0-0.8
- Pin project-owned helper commands to their packaged Fedora paths.
- Ignore the demo-only idle-timeout override in production backend mode.
- Refresh the exact security-gate evidence and hostile PATH regression.

* Tue Sep 01 2026 uglyegg <uglyegg@entropy.quest> - 0.12.0-0.7
- Sanitize native-loader and runtime search overrides before backend imports.
- Generate service, launcher, client, and package policy from one contract.
- Document process-identity checks within a realistic same-user threat boundary.

* Tue Sep 01 2026 uglyegg <uglyegg@entropy.quest> - 0.12.0-0.6
- Reconcile late authentication, cancellation, and logout/reconnect races.
- Recover same-owner operation timeouts without declaring the backend dead.
- Bind binary/source artifacts and translations to exact reviewed inputs.

* Mon Aug 31 2026 uglyegg <uglyegg@entropy.quest> - 0.12.0-0.5
- Reconcile partial authentication and logout failures with persisted Core state.
- Require the runtime iproute command used by reconnect readiness probes.
- Enforce exact snapshot, translation, overlay, and source-RPM provenance.

* Mon Aug 31 2026 uglyegg <uglyegg@entropy.quest> - 0.12.0-0.4
- Support Secret Service providers started by desktop autostart.
- Require same-user provider selection and unique-owner pinning.

* Mon Aug 31 2026 uglyegg <uglyegg@entropy.quest> - 0.12.0-0.3
- Recover from transient same-owner snapshot timeouts without false offline state.
- Fence account reads and session startup across logout and partial failures.
- Confirm tray and global-shortcut connection changes in the Control Center.
- Require a same-user, uniquely pinned Secret Service provider overlay.

* Mon Aug 31 2026 uglyegg <uglyegg@entropy.quest> - 0.12.0-0.2
- Bind asynchronous frontend replies to the authenticated backend generation.
- Keep readiness-probe failures retryable and add backend-replacement tests.
- Refresh exact shared translations and candidate review evidence.

* Mon Aug 31 2026 uglyegg <uglyegg@entropy.quest> - 0.12.0-0.1
- Add an on-demand, read-only Connection Inspector using existing Core state.
- Replace periodic backend ownership polling with D-Bus owner-loss events and
  a one-shot idle deadline.
- Begin the local 0.12.0 feature soak without changing Proton Core networking.

* Mon Aug 31 2026 uglyegg <uglyegg@entropy.quest> - 0.11.3-1
- Recover Protun reconnects without a Plasma NetworkManager secret plugin.
- Clear stale signed-in state when the backend stops and expose a bounded
  manual service retry when session restoration stalls.
- Build and require the independently verified API-Core overlay.

* Mon Aug 31 2026 uglyegg <uglyegg@entropy.quest> - 0.11.2-29
- Recover Protun reconnects without a Plasma NetworkManager secret plugin.
- Clear stale account state when the backend stops and offer a bounded manual
  restart when Secret Service session restoration does not complete.
- Require and release the independently verified API-Core overlay.

* Sun Aug 30 2026 uglyegg <uglyegg@entropy.quest> - 0.11.2-28
- Finalize the public-alpha release metadata.
- Run Fedora CI as an unprivileged builder and stage the complete client and
  provider-neutral keyring binary/source artifact set.
- Make QML smoke tests independent of X11 and legacy GitHub Actions runtimes.

* Sun Aug 30 2026 uglyegg <uglyegg@entropy.quest> - 0.11.2-27
- Refresh exact release-candidate acceptance and performance evidence.
- Add a reproducible isolated demo-stack memory measurement.

* Sun Aug 30 2026 uglyegg <uglyegg@entropy.quest> - 0.11.2-26
- Decompose backend adapters, QML settings/dialogs, location models, and
  native controller lifecycle code behind unchanged public interfaces.

* Sun Aug 30 2026 uglyegg <uglyegg@entropy.quest> - 0.11.2-25
- Reconcile public documentation with the latest installed acceptance evidence.
- Fold all pre-release 0.11.2 changes into the versioned changelog.
- Make Clang-Tidy independent of the build-directory name.

* Sun Aug 30 2026 uglyegg <uglyegg@entropy.quest> - 0.11.2-24
- Recover the Control Center after an unexpected backend service exit.
- Explain package-upgrade client authentication failures without retry churn.
- Make the reconnect release test independent of scheduler timing.

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
