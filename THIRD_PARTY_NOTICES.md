# Third-party notices

## Proton VPN Linux Core

This project interoperates with separately installed, official Proton VPN Linux
packages, including `python3-proton-vpn-api-core`, its protocol implementations,
and Proton's split-tunneling daemon. Those components are not vendored or
redistributed in this repository. Their copyrights and licenses remain with
their respective owners.

The community adapter calls Proton Core rather than replacing VPN protocols,
NetworkManager integration, kill switch, split tunneling, session persistence,
or server construction.

## Translations

Qt catalogs under `translations/` contain exact, unambiguous translations
derived from Proton VPN GTK app v4.18.0 at commit
`8e3897b6fe81840eef4762f2377c5a985754edea`.

The source catalogs are Copyright (c) 2023 Proton AG and distributed under
`GPL-3.0-or-later`. Only entries whose English source strings match exactly are
imported. See `translations/README.md` for the reproducible import process.

## API Core overlay patches

Files under `packaging/fedora/api-core-overlay/patches/` are source patches for
the separately packaged GPL-licensed Proton VPN API Core. The overlay build
records the exact accepted upstream package version and patch digests. The
overlay is optional and does not replace or redistribute the complete upstream
source repository.

## Names and marks

Proton, Proton VPN, and associated marks are owned by Proton AG. They are used
in this repository only to describe compatibility and identify the upstream
service and packages. The project does not bundle Proton's logo and does not
claim affiliation, review, sponsorship, or endorsement.
