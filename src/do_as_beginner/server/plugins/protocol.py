# TODO: Server plugin protocol, including cli part.


__all__ = ("PluginProtocol",)


class PluginProtocol:
    """Protocol for server plugins."""

    def setup(self) -> None: ...
