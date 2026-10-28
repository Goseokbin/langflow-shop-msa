#!/usr/bin/env python3
"""Refresh only internal service paths; no source, image or workload changes."""
import argparse
import datetime
import importlib.util
import json
import os
from pathlib import Path
import subprocess

from concert_internal_endpoints import collect, compact_properties, enrich, verify_document


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--authorization-file', required=True)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--output-dir', type=Path, default=Path(__file__).resolve().parents[1]/'.runtime/internal-endpoints')
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location('concert_api', Path(__file__).with_name('concert-audit-api.py'))
    api = importlib.util.module_from_spec(spec); spec.loader.exec_module(api)
    client = api.Concert(authorization=args.authorization_file)
    deploy_api = f"/concert/core/api/v2/environments/{os.environ['CONCERT_ENVIRONMENT_ID']}/deployments/{os.environ['CONCERT_DEPLOYMENT_ID']}"
    services = json.loads(subprocess.check_output(['oc','get','services','-n','shopping-mall','-o','json']))['items']
    inventory = collect(services, args.output_dir)
    documents = []
    for name, path, deployment in [('application',api.APP,False),('deployment',deploy_api,True)]:
        document = client.request(path+'/sbom')
        (args.output_dir/(name+'.before.json')).write_text(json.dumps(document, indent=2)+'\n')
        compact_properties(document)
        enrich(document, inventory, deployment=deployment)
        document['metadata']['timestamp'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        file = args.output_dir/(name+'.cdef.json')
        file.write_text(json.dumps(document,indent=2)+'\n')
        documents.append((file,path,deployment))
    receipts = []
    if args.apply:
        for file,path,deployment in documents:
            response = client.upload(file,'application_sbom',{})
            (args.output_dir/(file.stem+'.ingestion.json')).write_text(json.dumps(response,indent=2)+'\n')
            client.wait_for_upload(response)
            receipts.append(response)
        for file,path,deployment in documents:
            verify_document(client.request(path+'/sbom'),inventory,deployment=deployment)
    result = {'stage':'verified' if args.apply else 'prepared', 'api_services':inventory['api_services'],
              'api_paths':inventory['api_paths'],'internal_endpoints':inventory['endpoint_count'],'ingestion':receipts}
    (args.output_dir/'verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))


if __name__=='__main__':
    main()
