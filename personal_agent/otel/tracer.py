"""OpenTelemetry instrumentation for the personal agent.

Provides a module‑level ``tracer`` that can be used via ``with tracer.start_as_current_span(name):``.
"""

from __future__ import annotations

import os
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter, SimpleSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

# Configure tracer provider – chooses exporter based on ``OTEL_EXPORTER`` env var.
provider = TracerProvider()
exporter_type = os.getenv("OTEL_EXPORTER", "console").lower()
if exporter_type == "otlp":
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "localhost:4317")
    exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
    processor = BatchSpanProcessor(exporter)
elif exporter_type == "console":
    processor = SimpleSpanProcessor(ConsoleSpanExporter())
else:
    processor = SimpleSpanProcessor(ConsoleSpanExporter())
provider.add_span_processor(processor)
trace.set_tracer_provider(provider)

tracer = trace.get_tracer("personal-agent")
