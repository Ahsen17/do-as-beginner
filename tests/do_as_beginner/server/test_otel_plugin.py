"""Unit tests for OtelPlugin (R5): disabled-by-default and no self-registered atexit."""

import inspect

from do_as_beginner.server.depi import Container
from do_as_beginner.server.plugins import otel as otel_module
from do_as_beginner.server.plugins.otel import OtelPlugin


def test_otel_plugin_on_app_init_is_noop_when_disabled(default_container: Container) -> None:

    plugin = OtelPlugin()

    plugin.on_app_init(default_container)

    assert plugin._tracer_provider is None
    plugin.shutdown()  # must not raise


def test_otel_plugin_does_not_self_register_atexit() -> None:
    """Acceptance criterion (R5): shutdown is managed externally, not plugin-registered."""

    source = inspect.getsource(otel_module)

    assert "atexit.register" not in source
