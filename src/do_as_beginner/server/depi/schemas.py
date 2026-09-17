from typing import Any

from do_as_beginner.base import BaseStruct

__all__ = (
    "NamedDependency",
    "ParamSpec",
    "Registration",
)


EMPTY: Any = object()


class NamedDependency(BaseStruct):
    """Injection maker carrying an optional lookup key.

    Usage:

    - alias: ``Annotated[RedisFactory, NamedDependency("redis_a")]``
      resolves by the registered key ``"redis_a"`` (disambiguates same-type instances);
    - explicit type: ``Annotated[RedisFactory, NamedDependency()]``
      resolves by type (same as an implicit annotation);
    - implicit: ``redis: RedisFactory`` resolves by type when the type is registered.

    The marker also declares the parameter to be an injected dependency rather
    than a request/other parameter.
    """

    key: str | None = None


class ParamSpec(BaseStruct):
    """Static description of one callable parameter for DI decisions"""

    name: str
    marked: bool
    marker: NamedDependency | None
    annotation_type: type | None
    has_default: bool


class Registration(BaseStruct):
    """Runtime state of a single registered dependency"""

    key: str
    provider: Any
    resolved_type: type | None
    is_async: bool
    value: Any = EMPTY
    params: list[ParamSpec] | None = None
