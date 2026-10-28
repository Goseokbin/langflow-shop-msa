"""Observed internal OpenAPI paths, collected through the authenticated Kubernetes API."""
import copy
import datetime
import hashlib
import json
import subprocess

NAMESPACE = 'shopping-mall'
API_PORTS = {'api-gateway': 8000, 'cart-service': 8003, 'langflow': 7860,
             'langflow-ai-service': 8005, 'order-service': 8004,
             'product-service': 8002, 'user-service': 8001}
OTHER_PORTS = {'frontend': 3000, 'postgresql': 5432}
METHODS = {'get', 'put', 'post', 'delete', 'options', 'head', 'patch', 'trace'}


def compact_properties(value):
    """Concert exports can repeat identical property pairs across repeated ingestions."""
    if isinstance(value, dict):
        for key, child in value.items():
            if key == 'properties' and isinstance(child, list):
                seen = set()
                unique = []
                for prop in child:
                    signature = json.dumps(prop, sort_keys=True)
                    if signature not in seen:
                        seen.add(signature)
                        unique.append(prop)
                value[key] = unique
            else:
                compact_properties(child)
    elif isinstance(value, list):
        for child in value:
            compact_properties(child)
    return value


def raw_api(path):
    return subprocess.check_output(['oc', '--request-timeout=30s', 'get', '--raw', path], timeout=40)


def parse_paths(schema):
    """Use only declared operations; path-item metadata is not an API endpoint."""
    if not str(schema.get('openapi', '')).startswith('3.') and schema.get('swagger') != '2.0':
        raise ValueError('Expected an OpenAPI 3.x or Swagger 2.0 document')
    paths = schema.get('paths')
    if not isinstance(paths, dict) or not paths:
        raise ValueError('OpenAPI document has no paths')
    operations = []
    for path, item in paths.items():
        if not isinstance(path, str) or not path.startswith('/') or path.startswith('//') or '?' in path or '#' in path:
            raise ValueError('Expected a local API path')
        if not isinstance(item, dict) or '$ref' in item:
            raise ValueError('Unresolved or invalid OpenAPI path item: ' + path)
        for method in sorted(METHODS.intersection(item)):
            if not isinstance(item[method], dict):
                raise ValueError('Invalid OpenAPI operation: ' + path)
            operations.append({'path': path, 'method': method.upper()})
    if not operations:
        raise ValueError('OpenAPI document has no operations')
    return sorted({x['path'] for x in operations}), operations


def collect(services, evidence_dir, fetch=raw_api):
    evidence_dir.mkdir(parents=True, exist_ok=True)
    observed = {s['metadata']['name']: s for s in services}
    rows = []
    for name, port in sorted({**API_PORTS, **OTHER_PORTS}.items()):
        service = observed.get(name)
        if not service or service['metadata']['namespace'] != NAMESPACE:
            raise ValueError('Missing expected internal Service: ' + name)
        ports = service['spec']['ports']
        if len(ports) != 1 or ports[0]['port'] != port or ports[0].get('protocol', 'TCP') != 'TCP':
            raise ValueError('Review unexpected Service port: ' + name)
        base = f"{'tcp' if name == 'postgresql' else 'http'}://{name}.{NAMESPACE}.svc:{port}"
        row = {'name': name, 'base_url': base, 'port': port, 'operations': []}
        if name in API_PORTS:
            path = f'/api/v1/namespaces/{NAMESPACE}/services/http:{name}:{port}/proxy/openapi.json'
            raw = fetch(path)
            schema = json.loads(raw)
            endpoints, operations = parse_paths(schema)
            (evidence_dir / (name + '.openapi.json')).write_bytes(raw)
            row.update(kind='openapi', endpoints=endpoints, operations=operations,
                       schema_sha256=hashlib.sha256(raw).hexdigest(), schema_path='/openapi.json')
        elif name == 'frontend':
            row.update(kind='web-root', endpoints=['/'])
        else:
            row.update(kind='tcp-socket', endpoints=[base])
        rows.append(row)
    report = {'collected_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'namespace': NAMESPACE, 'services': rows,
              'api_services': len(API_PORTS),
              'api_paths': sum(len(r['endpoints']) for r in rows if r['kind'] == 'openapi'),
              'endpoint_count': sum(len(r['endpoints']) for r in rows)}
    (evidence_dir / 'internal-endpoints.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    return report


def enrich(document, inventory, deployment=False):
    """Replace only known internal endpoint metadata; preserve refs and all other relationships."""
    field = 'network_exposure' if deployment else 'network-exposure'
    for row in inventory['services']:
        matches = [s for s in document.get('services', []) if s['name'] == row['name'] and s.get(field) == 'private']
        if len(matches) != 1:
            raise ValueError('Expected one existing private service: ' + row['name'])
        service = matches[0]
        service['endpoints'] = copy.deepcopy(row['endpoints'])
        if deployment:
            service['base-url'] = row['base_url']
            service['port'] = row['port']
        props = {'endpoint.inventory.kind': row['kind'],
                 'endpoint.inventory.source': 'Live internal OpenAPI via Kubernetes Service proxy' if row['kind'] == 'openapi' else 'Kubernetes Service snapshot; no OpenAPI',
                 'endpoint.inventory.collected_at': inventory['collected_at']}
        if row['kind'] == 'openapi':
            props.update({'endpoint.inventory.schema_sha256': row['schema_sha256'],
                          'endpoint.inventory.schema_path': row['schema_path'],
                          'endpoint.inventory.operation_count': str(len(row['operations']))})
        service['properties'] = [p for p in service.get('properties', []) if not p['name'].startswith('endpoint.inventory.')]
        service['properties'] += [{'name': k, 'value': v} for k, v in props.items()]
    return document


def verify_document(document, inventory, deployment=False):
    field = 'network_exposure' if deployment else 'network-exposure'
    for row in inventory['services']:
        matches = [s for s in document['services'] if s['name'] == row['name'] and s.get(field) == 'private']
        if len(matches) != 1:
            raise ValueError('Expected one Concert private service: ' + row['name'])
        service = matches[0]
        if set(service['endpoints']) != set(row['endpoints']):
            raise ValueError('Concert internal paths differ from live OpenAPI: ' + row['name'])
        if deployment and (service.get('base-url') != row['base_url'] or service.get('port') != row['port']):
            raise ValueError('Concert internal access point changed: ' + row['name'])
