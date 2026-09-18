from typing import TYPE_CHECKING, Any

from .protocol import AppPluginProtocol, CLIPluginProtocol, PluginProtocol

if TYPE_CHECKING:
    from do_as_beginner.base import AppConfig


def plugin_name(plugin: Any) -> str:
    """A plugin's ``name`` attribute, defaulting to its class name."""

    name = getattr(plugin, "name", None)
    return name if isinstance(name, str) and name else type(plugin).__name__


def discover_plugins(config: "AppConfig") -> list[PluginProtocol]:
    """Instantiate every plugin class that inherits a plugin protocol.

    Discovery is subclass-based: any class visible via import that subclasses
    ``PluginProtocol``/``AppPluginProtocol``/``CLIPluginProtocol`` is found by
    ``__subclasses__()`` (the same import-visibility precedent as
    ``BaseController`` route registration). Built-ins live in
    ``do_as_beginner.plugins``; user plugins are any imported subclass of the
    protocols. The protocol classes themselves are excluded.

    Construction convention: ``cls(config: AppConfig)`` -- a plugin reads its
    configuration from the loaded ``AppConfig`` in its constructor.
    """

    protocols = {PluginProtocol, AppPluginProtocol, CLIPluginProtocol}
    # Built-ins only exist to discovery once their modules are imported; import
    # the built-in plugin package here so they are found in every entrypoint
    # without a hard-coded registration path (lazy: avoids the module-level
    # import cycle with ``do_as_beginner.plugins``).
    import do_as_beginner.plugins  # noqa: PLC0415,F401  # imported for subclass registration

    # dict.fromkeys dedupes a class found under two roots while keeping deterministic order
    classes = dict.fromkeys(
        cls
        for root in (PluginProtocol, AppPluginProtocol, CLIPluginProtocol)
        for cls in root.__subclasses__()  # runtime discovery: imported subclasses only
        if cls not in protocols
    )
    return [cls(config) for cls in classes]  # type: ignore[call-arg,misc]  # convention: __init__(config: AppConfig)
