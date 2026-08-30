# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

Name:           python3-proton-keyring-linux
Version:        0.2.3
Release:        4.plasmavpn1%{?dist}
Summary:        Provider-neutral Proton Secret Service adapter

License:        GPL-3.0-only
URL:            https://github.com/ProtonVPN/python-proton-keyring-linux
Source0:        python-proton-keyring-linux-%{version}.tar.gz
Source1:        overlay-manifest.json
Source2:        keyring-overlay-README.md
Patch0:         0001-provider-agnostic-secret-service.patch
Patch1:         0002-avoid-missing-entry-traceback.patch
BuildArch:      noarch

BuildRequires:  pyproject-rpm-macros
BuildRequires:  python3-devel
BuildRequires:  python3-keyring
BuildRequires:  python3-proton-core
BuildRequires:  python3-pytest
BuildRequires:  python3-secretstorage
BuildRequires:  python3-setuptools

Requires:       python3-keyring
Requires:       python3-proton-core
Requires:       python3-secretstorage
Suggests:       gnome-keyring
Provides:       proton-keyring-secret-service-provider-agnostic = 1
Conflicts:      python3-proton-keyring-linux-secretservice < 0.1.0
Obsoletes:      python3-proton-keyring-linux-secretservice < 0.1.0

%{?python_disable_dependency_generator}

%description
Proton's Linux keyring adapter with a narrow, provider-neutral Freedesktop
Secret Service compatibility patch. The adapter honors the default collection
alias, safely handles a sole advertised collection when that alias is stale,
and keeps one bounded D-Bus client connection so desktop providers can remember
authorization decisions. It does not contain KDE- or KeePassXC-specific logic.

This is an unofficial downstream rebuild maintained by the Plasma VPN project.

%prep
%autosetup -p1 -n python-proton-keyring-linux-%{version}
install -m 0644 %{SOURCE1} overlay-manifest.json
install -m 0644 %{SOURCE2} keyring-overlay-README.md

%build
%pyproject_wheel

%install
%pyproject_install
%pyproject_save_files proton

%check
python3 -m pytest -o addopts='' -q \
    tests/test_linuxkeyring.py tests/test_secretservice_backend.py
%pyproject_check_import

%files -f %{pyproject_files}
%license LICENSE
%doc overlay-manifest.json keyring-overlay-README.md

%changelog
* Sun Aug 30 2026 uglyegg <uglyegg@entropy.quest> - 0.2.3-4.plasmavpn1
- Rebuild the upstream v0.2.3 source with provider-neutral Secret Service support.
- Reuse one bounded D-Bus client connection for remembered provider approval.
- Avoid an error-level traceback when a requested keyring entry is already absent.
- Replace the GNOME Keyring hard dependency with a provider-neutral suggestion.
