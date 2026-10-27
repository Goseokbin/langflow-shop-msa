#!/usr/bin/env python3
"""
Script to add OpenTelemetry environment variables to deployment YAML files
"""

import re

OTEL_ENV_VARS = """        # OpenTelemetry configuration
        - name: OTEL_EXPORTER_OTLP_ENDPOINT
          value: "instana-otel-collector-statefulset.instana-otel-collector:4317"
        - name: OTEL_EXPORTER_OTLP_INSECURE
          value: "true"
        - name: OTEL_SERVICE_NAME
          value: "{service_name}"
"""

deployments = {
    "product-service": "openshift/deployments/product-service-deployment.yaml",
    "order-service": "openshift/deployments/order-service-deployment.yaml",
    "cart-service": "openshift/deployments/cart-service-deployment.yaml",
    "api-gateway": "openshift/deployments/api-gateway-deployment.yaml",
}

for service_name, file_path in deployments.items():
    print(f"Processing {service_name}...")
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Check if already has OTEL
    if "OTEL_EXPORTER_OTLP_ENDPOINT" in content:
        print(f"  ⏭️  {service_name} already has OTEL env vars, skipping")
        continue
    
    # Find the ports section and insert OTEL env vars before it
    ports_match = re.search(r'(\s+)ports:', content)
    if ports_match:
        indent = ports_match.group(1)
        insert_pos = ports_match.start()
        otel_vars = OTEL_ENV_VARS.format(service_name=service_name)
        content = content[:insert_pos] + otel_vars + content[insert_pos:]
        
        with open(file_path, 'w') as f:
            f.write(content)
        
        print(f"  ✅ Updated {file_path}")
    else:
        print(f"  ❌ Could not find ports section in {file_path}")

print("\n🎉 All deployment files updated with OpenTelemetry environment variables!")

# Made with Bob
