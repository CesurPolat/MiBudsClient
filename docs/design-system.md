# MiBudsClient UI design guide

This guide is the shared reference for UI changes. Follow the existing Flet components and the application constraints in `AGENTS.md`. It describes the current visual direction and practical rules for extending it; it does not imply that a device supports a feature or that every older screen already follows every rule.

## Direction and layout

MiBudsClient is a compact desktop companion: dark, quiet, clear, and centered on the connected earbuds. Prefer familiar controls, short labels, and useful feedback over decoration. Avoid adding dense dashboards, unnecessary animations, or technical protocol details to normal user flows.

- Keep the home screen focused on device status and frequently used controls. Put less frequent configuration in Settings.
- Settings uses a left navigation rail and one selected section on the right. Use the existing shared section surface in `ui/components/settings_card.py` for every section; do not add an extra outer card or border to only some sections. Inner controls may have their own boundaries when they clarify an interaction.
- Preserve the selected section and input state when resizing, switching screens, changing language, or receiving unrelated updates. If a device-specific section becomes unavailable, return to General.
- The default window is 655 ? 440 and the minimum is 420 ? 400. At widths below 500, Settings uses the compact icon rail; preserve translated tooltips and the visible section heading. Ensure long content can be reached by scrolling and controls do not clip or overflow at minimum width.
- Reuse the existing home layout breakpoint and sizing behavior in `ui/components/app_layout.py`; do not introduce a competing breakpoint without a concrete need.

## Visual tokens

Use `ui/constants.py` as the source for shared application tokens, and reuse the existing Settings surface before introducing new values. If a new shared style is needed, centralize it rather than copying literals across components.

| Role | Current reference |
| --- | --- |
| Application background | `COLOR_BG` / `#000000` |
| Home cards | `COLOR_CARD_BG` / `#1A1A1A` |
| Settings shell | `#0E1218`, border `#27313D` |
| Settings section surface | `#151B24`, border `#293443`, radius 16 |
| Selected navigation item | `#23364C`, border `#436A91`, icon `#9BC7FF` |
| Primary / secondary text | `COLOR_TEXT_PRIMARY` / `COLOR_TEXT_SECONDARY` |
| Dividers | `COLOR_DIVIDER` |
| Charging / battery / low battery | `COLOR_CHARGING`, `COLOR_BATTERY`, `COLOR_BATTERY_LOW` |

Use the existing 20-pixel card radius and 10-pixel icon radius where appropriate; the shared settings surface uses 16 pixels. Favor spacing in the existing 4, 8, 12, 16 rhythm. Section titles are currently 17 px semibold; ordinary labels are typically 12?14 px. Let translated labels wrap when needed. Status colors are supplemental: include text or an icon so meaning is not conveyed by color alone.

## Controls and interaction

- Reuse `SettingItem`, `ToggleSettingItem`, `DeviceImage`, and existing Flet controls where they fit. Keep icons, corner radii, padding, borders, and selection treatments consistent between equivalent controls.
- Use clear selected, disabled, loading, and error states. Avoid persistent success messages for routine reads when the resulting controls already show success; keep actionable errors, empty states, and loading feedback visible.
- Device-specific controls follow existing connection and capability checks. Display device-confirmed settings, and keep unconfirmed or unavailable data clearly distinct; use a placeholder instead of inventing values. Keep custom EQ hidden until explicitly re-enabled and retain the home preset controls.
- Keep interactions keyboard accessible with meaningful labels or tooltips, visible focus, and comfortable click targets. Icon-only navigation must have localized tooltips. Avoid hover-only information.
- Use existing translation helpers (`t`, `message`, `render`, and `refresh_translations`) for user-facing text. Follow `docs/localization.md` when adding keys, including every catalog and its source ledger. Check long translations and RTL layouts.
- Use `get_resource_path()` for local assets; keep bundled UI assets under `assets/`. Reuse cached device images and provide a graceful placeholder when an image is unavailable.
- Keep callbacks and asynchronous device operations in the existing controller flow. Do not block the Flet UI thread, reset form state during redraw, or enable a backend solely because a catalog lists a capability.

## Review checklist

For a UI change, review the affected screens at default and minimum window sizes and at a wider size. Check navigation selection, scrolling, text wrapping, focus, loading/error/empty states, connection changes, language switching, and relevant Windows/Linux behavior. Verify screenshots or the live UI when available; if visual verification is unavailable, say so. Run relevant tests plus the build and single-instance checks required by `AGENTS.md`.
