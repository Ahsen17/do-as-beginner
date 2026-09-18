from typing import Any


def plugin_name(plugin: Any) -> str:
    """A plugin's ``name`` attribute, defaulting to its class name."""

    name = getattr(plugin, "name", None)
    return name if isinstance(name, str) and name else type(plugin).__name__
