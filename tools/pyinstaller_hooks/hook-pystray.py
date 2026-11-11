"""Collect Linux backends without importing a tray connected to a display."""

hiddenimports = ["pystray._appindicator", "pystray._gtk", "pystray._xorg"]


def hook(hook_api):
    # GTK's default hook otherwise collects every installed desktop theme/icon.
    hook_api.analysis.hooksconfig.setdefault("gi", {
        "icons": ["Adwaita"],
        "themes": [],
        "languages": ["en", "tr", "de", "es", "fr", "ru", "zh_CN"],
    })
