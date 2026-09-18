"""Plugin registry: duplicate-name validation and a read-only facet index."""

from collections.abc import Iterator

from .exceptions import DuplicatePluginError
from .protocol import PluginProtocol
from .utils import plugin_name

__all__ = ("PluginRegistry",)


class PluginRegistry:
    """Read-only facet index over the registered plugins (Litestar-style).

    - Registration order is preserved everywhere; lifecycle loops live in the
      composition root (``PluginCore``), which iterates the facet buckets.
    - Duplicate plugin names fail eagerly at construction.
    """

    def __init__(self, *plugins: PluginProtocol) -> None:

        self._plugins: list[PluginProtocol] = list(plugins)

        seen: set[str] = set()
        for plugin in self._plugins:
            name = plugin_name(plugin)
            if name in seen:
                msg = f"Plugin name {name!r} is already registered"
                raise DuplicatePluginError(msg)
            seen.add(name)

    @property
    def plugins(self) -> tuple[PluginProtocol, ...]:

        return tuple(self._plugins)

    def __iter__(self) -> Iterator[PluginProtocol]:

        return iter(self._plugins)
