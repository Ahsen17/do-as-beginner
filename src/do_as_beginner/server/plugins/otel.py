import logging
import os
import socket
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from logging import _nameToLevel
from typing import TYPE_CHECKING

from opentelemetry import metrics, trace
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.django import DjangoInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from do_as_beginner.base import AppConfig
from do_as_beginner.server.core import AppPluginProtocol

if TYPE_CHECKING:
    from do_as_beginner.server.depi import Container


__all__ = ("OtelPlugin",)


class OtelPlugin(AppPluginProtocol):
    """Server plugin for OpenTelemetry (setup + shutdown facets).

    Shutdown is managed by the plugin registry's unified pipeline instead of
    self-registered ``atexit`` callbacks. The SDK providers keep their own
    default ``atexit`` registration as a last-resort fallback; because an
    explicit ``shutdown()`` unregisters it, the two paths cannot double-run.
    """

    def __init__(self) -> None:

        self._config = AppConfig.load()

        hostname = socket.gethostname()
        pid = os.getpid()

        self._otel_resource = Resource.create(
            {
                "service.name": self._config.server.name,
                "service.instance.id": f"{hostname}:{pid}",
                "deployment.environment.name": self._config.server.environment,
            }
        )
        self._tracer_provider: TracerProvider | None = None
        self._meter_provider: MeterProvider | None = None
        self._logger_provider: LoggerProvider | None = None

    def on_app_init(self, container: "Container") -> None:

        if not self._config.otel.enabled:
            return

        # Trace
        tracer_provider = TracerProvider(resource=self._otel_resource)
        tracer_provider.add_span_processor(
            BatchSpanProcessor(
                OTLPSpanExporter(
                    endpoint=self._config.otel.endpoint,
                    insecure=True,
                )
            )
        )
        trace.set_tracer_provider(tracer_provider)
        self._tracer_provider = tracer_provider

        # Metrics
        metric_reader = PeriodicExportingMetricReader(
            OTLPMetricExporter(
                endpoint=self._config.otel.endpoint,
                insecure=True,
            ),
            export_interval_millis=15_000,
        )
        meter_provider = MeterProvider(
            resource=self._otel_resource,
            metric_readers=[metric_reader],
        )
        metrics.set_meter_provider(meter_provider)
        self._meter_provider = meter_provider

        # Logs
        logger_provider = LoggerProvider(resource=self._otel_resource)
        logger_provider.add_log_record_processor(
            BatchLogRecordProcessor(
                OTLPLogExporter(
                    endpoint=self._config.otel.endpoint,
                    insecure=True,
                )
            )
        )
        set_logger_provider(logger_provider)
        self._logger_provider = logger_provider

        otel_log_handler = LoggingHandler(
            level=_nameToLevel[self._config.server.log_level],
            logger_provider=logger_provider,
        )

        for logger_name in ("do_as_beginner", "django.request"):
            python_logger = logging.getLogger(logger_name)
            python_logger.addHandler(otel_log_handler)

    def shutdown(self) -> None:
        """Flush and shut down the three providers (no-op when never set up)."""

        # The SDK's shutdown() is idempotent per provider and unregisters its
        # own atexit hook, so calling each here is safe.
        if self._tracer_provider is not None:
            self._tracer_provider.shutdown()
        if self._meter_provider is not None:
            self._meter_provider.shutdown()
        if self._logger_provider is not None:
            self._logger_provider.shutdown()

    @asynccontextmanager
    async def __lifespan__(self) -> AsyncGenerator[None, None]:

        if not self._config.otel.enabled:
            yield
            return

        DjangoInstrumentor().instrument()
        RequestsInstrumentor().instrument()

        try:
            yield

        finally:
            self.shutdown()
