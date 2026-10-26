# Translation sources and review

The app supports 24 language families and 27 selectable locales. All catalogs
contain the complete set of English keys and matching named parameters. Runtime
translation uses only the bundled `assets/locales/*.json` files, with English
fallback for missing or malformed translations.

## Supplied Android resources

The user supplied XML resources extracted from Xiaomi Earbuds **1.37.1i**. The
offline importer maps equivalent earbud concepts to stable MiBudsClient keys.
`localization_sources.json` records the resource name, relative XML file and
source-file SHA-256 for each directly imported translation. Other entries are
authored or adapted desktop text, including composed status messages. The original
XML files and the user's absolute source directory are not runtime dependencies.

English callback strings are kept compatible. Turkish and Simplified Chinese
retain existing desktop messages while shared terminology is checked against the
source. Other locales have complete desktop catalogs as well. The source has no
earbud-specific strings for Estonian, Finnish, Hindi, Hungarian or Swedish, so
those app terms are authored too. These translations have had structural and
context review; this does not represent native-speaker review of every language.

## Context decisions

- Android `in` is normalized to standard Indonesian `id`.
- Portuguese uses separate `pt-BR` and `pt-PT` catalogs. Chinese uses `zh-CN`,
  `zh-TW` and `zh-HK`; script and region are respected during locale detection.
- English AU/CA/GB/IN, Spanish regional and French CA packages add framework
  strings, not different translations of our app concepts. They resolve to their
  language catalog. `en-XC` is not offered as a user language.
- Malay combines its base resources with the Malaysian app resources. Resource
  overlays never leak between sibling Chinese or Portuguese regions.
- The Chinese alarm-side selector means **left only/right only**, so neutral side
  resources are used for batteries and gesture selectors. **Go to** is not copied
  into the tray's **Open** action. Portuguese **N/A** is replaced with **Unassigned**.
- **Noise cancellation** is not imported as **Noise control**. Android's
  **Automatic game mode** is not used to describe our desktop fullscreen,
  inclusion/exclusion, and hold-until-close policy.
- Android references, formatting tokens and mobile-specific instructions are
  not copied into unrelated desktop messages. Technical error details, process
  names and device names remain unchanged. Arabic changes the page direction
  immediately, and switching back restores left-to-right layout.

## Rechecking a resource export

Run from the repository root, pointing to an extracted folder with the supplied
language-directory structure:

```powershell
python tools/import_xiaomi_translations.py "PATH_TO_EXTRACTED_TRANSLATIONS"
python tools/import_xiaomi_translations.py "PATH_TO_EXTRACTED_TRANSLATIONS" --write
python -m unittest discover -s tests
```

The default is a dry run. `--write` updates only the reviewed mappings and a few
explicit context corrections, preserves desktop text, and refreshes the source
ledger. It never edits the source folder or reads an APK. Adding a language also
requires its native name in `utils/i18n.py`, a complete catalog, and source-ledger
coverage. No new translation service or runtime dependency is required.
