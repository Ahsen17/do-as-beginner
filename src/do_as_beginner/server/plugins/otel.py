import atexit
import logging
import os
import socket
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

from .protocol import PluginProtocol

if TYPE_CHECKING:
    from do_as_beginner.base import AppConfig


__all__ = ("OtelPlugin",)


class OtelPlugin(PluginProtocol):
    """Server plugin for OpenTelemetry."""

    def __init__(self, config: "AppConfig") -> None:

        self._config = config

        hostname = socket.gethostname()
        pid = os.getpid()

        self._otel_resource = Resource.create(
            {
                "service.name": self._config.server.name,
                "service.instance.id": f"{hostname}:{pid}",
                "deployment.environment.name": self._config.server.environment,
            }
        )

    def setup(self) -> None:

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

        otel_log_handler = LoggingHandler(
            level=_nameToLevel[self._config.server.log_level],
            logger_provider=logger_provider,
        )

        for logger_name in ("do_as_beginner", "django.request"):
            python_logger = logging.getLogger(logger_name)
            python_logger.addHandler(otel_log_handler)

        DjangoInstrumentor().instrument()
        RequestsInstrumentor().instrument()

        atexit.register(tracer_provider.shutdown)
        atexit.register(meter_provider.shutdown)
        atexit.register(logger_provider.shutdown)
