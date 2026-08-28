import atexit
import os
import socket
from typing import TYPE_CHECKING

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
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
                "server.name": self._config.server.name,
                "server.env": self._config.server.environment,
                "server.instance": f"{hostname}:{pid}",
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

        atexit.register(tracer_provider.shutdown)
        atexit.register(meter_provider.shutdown)
