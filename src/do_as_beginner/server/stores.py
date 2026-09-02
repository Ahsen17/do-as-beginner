from typing import Any, ClassVar

__all__ = ("ServerStore",)


# TODO: need refactor
class ServerStore:
    """Server dependencies store"""

    items: ClassVar[dict[str, Any]] = {}

    @classmethod
    def add_dependency(cls, name: str, d: Any) -> None:

        if name in cls.items:
            raise KeyError(f"Dependency {name} already exists")

        cls.items[name] = d

    @classmethod
    def get_dependency(cls, name: str) -> Any:

        if name not in cls.items:
            raise KeyError(f"Dependency {name} does not exist")

        return cls.items[name]


def provide[T](name: str, cls: type[T]) -> T:

    dependency: Any = ServerStore.get_dependency(name)

    if not isinstance(dependency, cls):
        raise TypeError(
            f"Dependency {name!r} expected {cls.__qualname__}, but got {type(dependency).__qualname__}",
        )

    return dependency
