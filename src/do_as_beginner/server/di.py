"""Lightweight runtime dependency-injection container.

A minimal DI container inspired by Litestar's dependency kernel (see
``.runtime/tasks/1788698341/research-di-design.md``): flat name-keyed
registration, type-first lookup with alias disambiguation, a nested
dependency graph resolved in topological order, and a singleton cache
held on each registration (app-level lifetime).

Public surface:

- ``DIContainer`` -- the container: ``register`` / ``get`` / ``aget`` / ``inject`` / ``ainject``.
- ``NamedDependency`` -- injection marker ``Annotated[T, NamedDependency(key)]``.
- ``DependencyError`` hierarchy.
- ``get_default_container`` / ``set_default_container`` -- process-wide default instance.
"""

import inspect
import types
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Any, cast, get_args, get_origin, get_type_hints, overload
from weakref import WeakKeyDictionary

__all__ = (
    "AmbiguousDependencyError",
    "AsyncDependencyError",
    "CircularDependencyError",
    "DIContainer",
    "DependencyError",
    "DependencyNotFoundError",
    "DuplicateDependencyError",
    "NamedDependency",
)


class DependencyError(Exception):
    """Base error for all dependency-injection failures."""


class DuplicateDependencyError(DependencyError):
    """Raised when a dependency key is registered more than once."""


class DependencyNotFoundError(DependencyError):
    """Raised when a dependency key or type is not registered."""


class AmbiguousDependencyError(DependencyError):
    """Raised when a type resolves to several candidates and no alias is given."""


class CircularDependencyError(DependencyError):
    """Raised when the dependency graph contains a cycle."""


class AsyncDependencyError(DependencyError):
    """Raised when the synchronous resolution path hits an async provider."""


@dataclass(frozen=True)
class NamedDependency:
    """Injection marker carrying an optional lookup key.

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


_EMPTY: Any = object()
"""Sentinel marking an unresolved registration."""


@dataclass
class _ParamSpec:
    """Static description of one callable parameter for DI decisions."""

    name: str
    marked: bool
    marker: NamedDependency | None
    annotation_type: type | None
    has_default: bool


@dataclass
class _Registration:
    """Runtime state of a single registered dependency."""

    key: str
    provider: Any
    resolved_type: type | None
    is_async: bool
    value: Any = _EMPTY
    params: list[_ParamSpec] | None = None


def _unwrap_type(annotation: Any) -> type | None:
    """Resolve ``Annotated[T, ...]`` / ``T | None`` down to a plain type."""

    if get_origin(annotation) is Annotated:
        annotation = get_args(annotation)[0]

    if get_origin(annotation) is types.UnionType:
        args = [a for a in get_args(annotation) if a is not type(None)]
        if len(args) == 1:
            annotation = args[0]

    return annotation if isinstance(annotation, type) else None


def _introspect_params(callable_: Any) -> list[_ParamSpec]:
    """Introspect a callable (or class) for DI decisions.

    ``inspect.signature`` on a class returns its ``__init__`` parameters (with
    ``self`` removed); ``get_type_hints`` on a class only resolves class-level
    annotations, so parameter hints fall back to ``param.annotation``, which
    preserves ``Annotated`` metadata for real types.
    """

    try:
        hints = get_type_hints(callable_, include_extras=True)
    except (NameError, TypeError):
        hints = {}

    params: list[_ParamSpec] = []
    for name, param in inspect.signature(callable_).parameters.items():
        if name == "self" or param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            continue

        annotation = hints.get(name, param.annotation)
        marked = False
        marker: NamedDependency | None = None
        base: Any = annotation

        if get_origin(annotation) is Annotated:
            args = get_args(annotation)
            base = args[0]
            for meta in args[1:]:
                if isinstance(meta, NamedDependency):
                    marked = True
                    marker = meta
                    break

        params.append(
            _ParamSpec(
                name=name,
                marked=marked,
                marker=marker,
                annotation_type=_unwrap_type(base),
                has_default=param.default is not inspect.Parameter.empty,
            )
        )

    return params


class DIContainer:
    """Lightweight runtime dependency-injection container.

    Registered dependencies resolve once (lazily on first access) and are then
    cached as process-wide singletons (see ``get``/``aget``).
    """

    __slots__ = ("_params_cache", "_registrations", "_type_index")

    def __init__(self) -> None:
        self._registrations: dict[str, _Registration] = {}
        self._type_index: dict[type, list[str]] = {}
        self._params_cache: WeakKeyDictionary[Callable[..., Any], list[_ParamSpec]] = WeakKeyDictionary()

    # -- registration -----------------------------------------------------

    def register(self, provider: Any, *, key: str | None = None) -> None:
        """Register a dependency.

        ``provider`` may be:

        - a class -- instantiated lazily, its constructor parameters are
          DI-resolved (or defaulted);
        - a (sync/async) factory callable -- called lazily, its parameters are
          DI-resolved (or defaulted); the return annotation is recorded as the
          resolved type;
        - a plain value -- registered as-is and cached immediately (this is how
          already-built instances, e.g. ``RedisFactory(config.redis)``, migrate).

        ``key`` defaults to the class/function name. Registering the same key
        twice raises :class:`DuplicateDependencyError`. Multiple providers of
        the same resolved type are allowed (with distinct keys); type-first
        lookup of such a type raises :class:`AmbiguousDependencyError` until an
        alias (``NamedDependency(key=...)``) is used.
        """

        default_key = getattr(provider, "__name__", None)
        dep_key = key or (default_key if isinstance(default_key, str) else repr(provider))

        if dep_key in self._registrations:
            raise DuplicateDependencyError(f"Dependency {dep_key!r} already registered")

        if isinstance(provider, type):
            registration = _Registration(
                key=dep_key,
                provider=provider,
                resolved_type=provider,
                is_async=False,
            )
        elif callable(provider):
            try:
                hints = get_type_hints(provider, include_extras=True)
            except (NameError, TypeError):
                hints = {}
            registration = _Registration(
                key=dep_key,
                provider=provider,
                resolved_type=_unwrap_type(hints.get("return")),
                is_async=inspect.iscoroutinefunction(provider),
            )
        else:
            registration = _Registration(
                key=dep_key,
                provider=provider,
                resolved_type=type(provider),
                is_async=False,
                value=provider,
            )

        self._registrations[dep_key] = registration
        if registration.resolved_type is not None:
            self._type_index.setdefault(registration.resolved_type, []).append(dep_key)

    # -- lookup -----------------------------------------------------------

    def _lookup(self, key_or_type: str | type) -> _Registration:
        """Resolve a key or type to its registration."""

        if isinstance(key_or_type, str):
            registration = self._registrations.get(key_or_type)
            if registration is None:
                raise DependencyNotFoundError(f"Dependency {key_or_type!r} does not exist")
            return registration

        candidates = self._type_index.get(key_or_type)
        if not candidates:
            raise DependencyNotFoundError(f"No dependency registered for type {key_or_type.__qualname__!r}")
        if len(candidates) > 1:
            raise AmbiguousDependencyError(
                f"Type {key_or_type.__qualname__!r} has multiple candidates {candidates!r}; "
                "use an alias (Annotated[T, NamedDependency(key=...)]) to disambiguate",
            )
        return self._registrations[candidates[0]]

    def _provider_params(self, registration: _Registration) -> list[_ParamSpec]:
        if registration.params is None:
            registration.params = _introspect_params(registration.provider)
        return registration.params

    # -- resolution -------------------------------------------------------

    @overload
    def get(self, key_or_type: str) -> Any: ...

    @overload
    def get[T](self, key_or_type: type[T]) -> T: ...

    def get[T](self, key_or_type: str | type[T]) -> T:
        """Resolve a dependency synchronously (singleton).

        Passing a type (``get(RedisFactory)``) returns that instance type;
        passing a registered key (``get("redis_factory")``) returns ``Any``,
        since the value type is only known at runtime.
        """

        registration = self._lookup(key_or_type)
        return cast("T", self._resolve_sync(registration, set()))

    @overload
    async def aget(self, key_or_type: str) -> Any: ...

    @overload
    async def aget[T](self, key_or_type: type[T]) -> T: ...

    async def aget[T](self, key_or_type: str | type[T]) -> T:
        """Resolve a dependency asynchronously (singleton).

        See :meth:`get` for the return-type behaviour.
        """

        registration = self._lookup(key_or_type)
        return cast("T", await self._resolve_async(registration, set()))

    def inject(self, fn: Callable[..., Any]) -> dict[str, Any]:
        """Synchronously resolve ``fn``'s DI parameters into a kwargs dict."""

        params = self._params_cache.setdefault(fn, _introspect_params(fn))
        resolved: dict[str, Any] = {}
        for spec in params:
            registration = self._consumer_target(spec)
            if registration is not None:
                resolved[spec.name] = self._resolve_sync(registration, set())
        return resolved

    async def ainject(self, fn: Callable[..., Any]) -> dict[str, Any]:
        """Asynchronously resolve ``fn``'s DI parameters into a kwargs dict."""

        params = self._params_cache.setdefault(fn, _introspect_params(fn))
        resolved: dict[str, Any] = {}
        for spec in params:
            registration = self._consumer_target(spec)
            if registration is not None:
                resolved[spec.name] = await self._resolve_async(registration, set())
        return resolved

    def _consumer_target(self, spec: _ParamSpec) -> _Registration | None:
        """Pick a registration for a consumer parameter, or None to skip it."""

        if spec.marked:
            if spec.marker is not None and spec.marker.key is not None:
                return self._lookup(spec.marker.key)
            if spec.annotation_type is not None:
                return self._lookup(spec.annotation_type)
            raise DependencyNotFoundError(f"Dependency marker for parameter {spec.name!r} has no key or type")
        if spec.annotation_type is not None and spec.annotation_type in self._type_index:
            return self._lookup(spec.annotation_type)
        return None

    def _provider_target(self, spec: _ParamSpec, owner: str) -> _Registration | None:
        """Pick a registration for a provider parameter, or None when defaulted."""

        if spec.marked:
            if spec.marker is not None and spec.marker.key is not None:
                return self._lookup(spec.marker.key)
            if spec.annotation_type is not None:
                return self._lookup(spec.annotation_type)
            raise DependencyNotFoundError(
                f"Dependency marker for parameter {spec.name!r} of provider {owner!r} has no key or type",
            )
        if spec.annotation_type is not None and spec.annotation_type in self._type_index:
            return self._lookup(spec.annotation_type)
        if spec.has_default:
            return None
        raise DependencyNotFoundError(
            f"Parameter {spec.name!r} of provider {owner!r} cannot be resolved (not registered, no default)",
        )

    def _resolve_sync(self, registration: _Registration, path: set[str]) -> Any:
        if registration.value is not _EMPTY:
            return registration.value
        if registration.key in path:
            raise CircularDependencyError(f"Circular dependency involving {registration.key!r}")
        if registration.is_async:
            raise AsyncDependencyError(
                f"Dependency {registration.key!r} is an async provider and cannot be resolved synchronously",
            )

        path.add(registration.key)
        try:
            kwargs: dict[str, Any] = {}
            for spec in self._provider_params(registration):
                sub = self._provider_target(spec, registration.key)
                if sub is not None:
                    kwargs[spec.name] = self._resolve_sync(sub, path)
            value = registration.provider(**kwargs)
        finally:
            path.discard(registration.key)

        registration.value = value
        return value

    async def _resolve_async(self, registration: _Registration, path: set[str]) -> Any:
        if registration.value is not _EMPTY:
            return registration.value
        if registration.key in path:
            raise CircularDependencyError(f"Circular dependency involving {registration.key!r}")

        path.add(registration.key)
        try:
            kwargs: dict[str, Any] = {}
            for spec in self._provider_params(registration):
                sub = self._provider_target(spec, registration.key)
                if sub is not None:
                    kwargs[spec.name] = await self._resolve_async(sub, path)
            if registration.is_async:
                value = await registration.provider(**kwargs)
            else:
                value = registration.provider(**kwargs)
        finally:
            path.discard(registration.key)

        registration.value = value
        return value


class _ContainerHolder:
    """Module-level default container holder (avoids mutating a module global)."""

    _instance: DIContainer | None = None


def get_default_container() -> DIContainer:
    """Return the process-wide default container, creating it on first use."""

    instance = _ContainerHolder._instance
    if instance is None:
        instance = DIContainer()
        _ContainerHolder._instance = instance
    return instance


def set_default_container(container: DIContainer) -> None:
    """Replace the process-wide default container (used by tests/overrides)."""

    _ContainerHolder._instance = container
