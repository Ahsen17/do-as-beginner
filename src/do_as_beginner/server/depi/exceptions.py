from do_as_beginner.shared import ApplicationError

__all__ = (
    "AmbiguousDependencyError",
    "AsyncDependencyError",
    "CircularDependencyError",
    "DependencyError",
    "DependencyNotFoundError",
    "DuplicateDependencyError",
)


class DependencyError(ApplicationError):
    """Base error for all dependency-injection failures"""


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
