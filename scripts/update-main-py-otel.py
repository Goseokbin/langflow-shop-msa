#!/usr/bin/env python3
"""
Script to add OpenTelemetry initialization to main.py files
"""

import os
import re

OTEL_IMPORTS = """
# OpenTelemetry imports
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
"""

OTEL_INIT = """
# Initialize OpenTelemetry
otel_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "instana-otel-collector-statefulset.instana-otel-collector:4317")
resource = Resource.create({{"service.name": "{service_name}"}})
trace.set_tracer_provider(TracerProvider(resource=resource))
otlp_exporter = OTLPSpanExporter(endpoint=otel_endpoint, insecure=True)
trace.get_tracer_provider().add_span_processor(BatchSpanProcessor(otlp_exporter))
logger.info(f"OpenTelemetry initialized, sending traces to {{otel_endpoint}}")
"""

INSTRUMENTATION = """
# Instrument FastAPI and SQLAlchemy
FastAPIInstrumentor.instrument_app(app)
SQLAlchemyInstrumentor().instrument(engine=engine)
"""

services = {
    "product-service": "services/product-service/app/main.py",
    "order-service": "services/order-service/app/main.py",
    "cart-service": "services/cart-service/app/main.py",
    "api-gateway": "services/api-gateway/app/main.py",
}

for service_name, file_path in services.items():
    print(f"Processing {service_name}...")
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Check if already has OTEL
    if "OpenTelemetry" in content:
        print(f"  ⏭️  {service_name} already has OpenTelemetry, skipping")
        continue
    
    # Add imports after existing imports
    import_section_end = content.find('\n\n')
    if import_section_end == -1:
        import_section_end = content.find('from .database')
    
    # Insert OTEL imports
    content = content[:import_section_end] + OTEL_IMPORTS + content[import_section_end:]
    
    # Add OTEL initialization after logger setup
    logger_pos = content.find('logger = logging.getLogger(__name__)')
    if logger_pos != -1:
        next_line = content.find('\n', logger_pos) + 1
        otel_init = OTEL_INIT.format(service_name=service_name)
        content = content[:next_line] + otel_init + content[next_line:]
    
    # Add instrumentation before @app.on_event("startup")
    startup_pos = content.find('@app.on_event("startup")')
    if startup_pos != -1:
        content = content[:startup_pos] + INSTRUMENTATION + '\n' + content[startup_pos:]
    
    # Update startup message
    content = content.replace(
        'logger.info("', 
        'logger.info("'
    ).replace(
        ' started successfully")',
        ' started successfully with OpenTelemetry instrumentation")'
    )
    
    with open(file_path, 'w') as f:
        f.write(content)
    
    print(f"  ✅ Updated {file_path}")

print("\n🎉 All main.py files updated with OpenTelemetry!")

# Made with Bob
