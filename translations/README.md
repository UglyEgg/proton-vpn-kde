# Translations

The Qt catalogs in this directory reuse exact, unambiguous translations from
the Proton VPN GTK app v4.18.0 catalogs at commit
`8e3897b6fe81840eef4762f2377c5a985754edea`. Those source catalogs are
Copyright (c) 2023 Proton AG and licensed under GPL-3.0-or-later, the same
license as this project. No GTK or Gettext component is required at build or
runtime.

Only identical English source strings are imported. If Proton uses different
translations for the same English text in different semantic contexts, the
entry is deliberately omitted rather than guessed. Plasma-specific strings
remain marked for translation and fall back to English until translated.

Refresh the imported catalogs from a checked-out official source tree with:

```bash
scripts/import-proton-translations.py \
  /path/to/proton-vpn-gtk-app/proton/vpn/app/gtk/locale
```
