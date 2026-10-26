"""Refresh only explicitly tagged translated properties, without rebuilding controls."""

from dataclasses import fields, is_dataclass

from utils.i18n import Message, render


def refresh_translations(root) -> None:
    """Walk Flet's public dataclass fields; leave user input and runtime state intact."""
    visited = set()

    def visit(value):
        if id(value) in visited:
            return
        visited.add(id(value))
        if isinstance(value, (list, tuple)):
            for child in value:
                visit(child)
        elif isinstance(value, dict):
            for child in value.values():
                visit(child)
        elif is_dataclass(value) and not isinstance(value, type):
            for field in fields(value):
                if field.name.startswith("_") or field.name in {"data", "parent"}:
                    continue
                child = getattr(value, field.name, None)
                if isinstance(child, Message):
                    translated = render(child)
                    # Assign even if equal: keep translation metadata for future changes.
                    setattr(value, field.name, translated)
                else:
                    visit(child)

    visit(root)
