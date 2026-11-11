"""Tray doubles that never import a native GUI backend."""
from types import SimpleNamespace
from unittest.mock import Mock


class MenuItem:
    def __init__(self, text, action, **kwargs):
        self._text = text
        self.action = action

    @property
    def text(self):
        return self._text(self) if callable(self._text) else self._text


class Menu:
    SEPARATOR = object()

    def __init__(self, *items):
        self.items = items


def fake_tray_api():
    icon = Mock(HAS_MENU=True)
    type(icon.return_value).HAS_MENU = True
    return SimpleNamespace(Icon=icon, Menu=Menu, MenuItem=MenuItem)
