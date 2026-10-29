#!/usr/bin/env python3
"""Build a read-only Concert workflow. Governance belongs to native rules and Goals."""
import argparse
import importlib.util
import json
from pathlib import Path
import zipfile

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('runtime_builder', HERE/'build-two-env-patch-workflow.py')
runtime_builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime_builder)


def build(config):
    required = ['repository', 'concert_host', 'application_api', 'github_auth', 'concert_auth',
                'staging_environment_id', 'production_environment_id',
                'staging_deployment_prefix', 'production_deployment_prefix']
    if any(not config.get(k) for k in required):
        raise ValueError('Missing infrastructure configuration')
    cfg = {k: config[k] for k in required}
    original = runtime_builder.build(cfg, evidence_only=True)

    def var(name, value='null', **kwargs):
        return {'name': name, 'isInput': False, 'isOutput': False, 'required': False,
                'level': 'INTERMEDIATE', 'type': {'type': 'any'}, 'value': value, **kwargs}

    blocks = [{'name': '01_Validate_verification_scope', 'function': r'''
if(!/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test($config.repository))throw new Error("Invalid repository");
if(!/^[a-z0-9][a-z0-9-]{0,62}$/.test($service))throw new Error("Invalid service");
if(!/^CVE-\d{4}-\d{4,}$/.test($cve))throw new Error("Invalid CVE");
if(typeof $expected_package!=="string"||!$expected_package.trim()||$expected_package.length>200)throw new Error("Expected package is required");
'''}]
    keep = {'List_staging_deployments', 'List_production_deployments', 'Select_latest_deployments',
            'Read_staging_deployment', 'Read_production_deployment', 'Read_build_artifacts',
            'Select_service_artifact', 'Read_image_instances', 'Resolve_current_runtime_images',
            'Read_staging_packages', 'Read_staging_cve_findings', 'Read_production_packages',
            'Read_production_cve_findings'}
    for block in original['blocks']:
        if block['name'] not in keep:
            continue
        if 'function' in block:
            block['function'] = block['function'].replace('$config.policy.service', '$service')
            if block['name'] == 'Select_latest_deployments':
                block['function'] = block['function'].replace(
                    '$config={...$config,[role+"_deployment_id"]:candidates[0].id};',
                    '$config={...$config,[role+"_deployment_id"]:candidates[0].id};\n'
                    '$deploymentSnapshots={...$deploymentSnapshots,[role]:candidates[0]};')
        blocks.append(block)
    blocks += [{'name': 'Read_release_runs', 'action': 'system/Common/HTTP/HTTP Request', 'inputs': [
        {'name': 'method', 'value': '"GET"'},
        {'name': 'host', 'value': '"https://api.github.com"'},
        {'name': 'path', 'value': '"/repos/"+$config.repository+"/actions/workflows/concert-devsecops.yml/runs"'},
        {'name': 'authKey', 'value': '$config.github_auth'},
        {'name': 'headers', 'value': '{"Accept":"application/json","User-Agent":"Concert-Post-Patch-Verification"}'},
        {'name': 'query', 'value': '{"branch":"main","event":"push","per_page":5}'},
        {'name': 'rejectUnauthorized', 'value': 'true'}, {'name': 'timeout', 'value': '60'}]},
        {'name': '02_Verify_two_current_deployments', 'function': (HERE/'post-patch-verification.js').read_text()}]
    # Safety invariant: this flow cannot mutate any external system.
    for block in blocks:
        if block.get('action'):
            inputs = {p['name']: p['value'] for p in block['inputs']}
            if inputs['method'] != '"GET"':
                raise ValueError('Verification flow must be read-only')
    return {'name': 'Langflow Post-patch Verification', 'platform': 'node',
            'meta': {'version': 5, 'layout': 'flow', 'workerGroup': 'default',
                     'description': 'Read-only post-patch evidence: current staging and production image digests, package inventories, target CVE and deployment pipeline. Assignment and SLA are managed by native Automation rules and Goals.'},
            'variables': [var('service', '"cart-service"', isInput=True, type={'type': 'string'}),
                          var('expected_package', '"python-multipart"', isInput=True, type={'type': 'string'}),
                          var('cve', '"CVE-2024-53981"', isInput=True, type={'type': 'string'}),
                          var('config', json.dumps(cfg)), var('result', '{}', isOutput=True),
                          var('deploymentSnapshots', '{}'), var('targetBuildArtifact'),
                          var('stagingRuntime'), var('productionRuntime')], 'blocks': blocks}


def retirement_notice():
    """Replace the former active governance flow without deleting its execution history."""
    return {'name': 'Langflow CVE Case Management', 'platform': 'node',
            'meta': {'version': 5, 'layout': 'flow', 'workerGroup': 'default',
                     'description': 'Retired. Configure assignment in Automation rules and SLA in Goals. Use Langflow Post-patch Verification for read-only verification.'},
            'variables': [{'name': 'result', 'isInput': False, 'isOutput': True,
                           'required': False, 'level': 'INTERMEDIATE',
                           'type': {'type': 'any'}, 'value': '{}'}],
            'blocks': [{'name': 'Retired_read_only_notice', 'function':
                        '$result={retired:true,writes_enabled:false,replacement:"Langflow Post-patch Verification",message:"Configure ownership in Automation rules and SLA in Goals. This retired flow performs no external actions."};'}]}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--retire-legacy', action='store_true',
                        help='Include a read-only replacement for the former CVE Case Management flow (ZIP only)')
    args = parser.parse_args()
    flow = build(json.loads(Path(args.config).read_text()))
    data = json.dumps(flow, ensure_ascii=False, indent=2)+'\n'
    if args.retire_legacy and Path(args.output).suffix != '.zip':
        parser.error('--retire-legacy requires a ZIP output')
    if Path(args.output).suffix == '.zip':
        with zipfile.ZipFile(args.output, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(flow['name']+'.json', data)
            if args.retire_legacy:
                legacy = retirement_notice()
                archive.writestr(legacy['name']+'.json', json.dumps(legacy, ensure_ascii=False, indent=2)+'\n')
    else:
        Path(args.output).write_text(data)
