"""Reviewed dependency policies shared by Concert and CI. No credentials here."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_policies():
    policies = json.loads((ROOT/'scripts/remediation-policies.json').read_text())
    branches = set()
    for name, p in policies.items():
        if not re.fullmatch(r'[a-z0-9-]+', name):
            raise ValueError('Invalid policy ID')
        if p['file'] != 'services/'+p['service']+'/requirements.txt':
            raise ValueError('Only a selected service requirements.txt is supported')
        if not re.fullmatch(r'[a-z0-9-]+', p['service']):
            raise ValueError('Invalid service name')
        if not re.fullmatch(r'[a-z0-9][a-z0-9.-]*', p['package']):
            raise ValueError('Expected normalized Python distribution name')
        if not re.fullmatch(re.escape(p['package'])+r'(\[[a-zA-Z0-9,._-]+\])?', p.get('requirement',p['package'])):
            raise ValueError('Invalid pinned requirement')
        if not all(re.fullmatch(r'\d+(?:\.\d+)+(?:[a-zA-Z0-9.-]*)', v) for v in [p['from_version'],p['to_version'],*p['fixed_versions']]):
            raise ValueError('Expected explicit reviewed versions')
        if not p['cves'] or not all(re.fullmatch(r'CVE-\d{4}-\d{4,}', c) for c in p['cves']):
            raise ValueError('Expected explicit CVE scope')
        if not p['branch'].startswith('concert-patch/') or p['branch'] in branches:
            raise ValueError('Expected unique patch branch')
        branches.add(p['branch'])
        if p['regression'] not in ['scripts/requests-regression.py','scripts/multipart-regression.py','scripts/jose-regression.py']:
            raise ValueError('Unknown compatibility check')
        if not isinstance(p['port'],int) or not 1 <= p['port'] <= 65535:
            raise ValueError('Invalid service port')
    return policies


def resolve_branch(branch):
    matches = [(name,p) for name,p in load_policies().items() if p['branch']==branch]
    if len(matches)!=1:
        raise ValueError('Branch has no unique reviewed patch policy')
    return matches[0]


if __name__ == '__main__':
    import argparse
    ap=argparse.ArgumentParser();ap.add_argument('--branch',required=True);ap.add_argument('--github-output');args=ap.parse_args()
    name,p=resolve_branch(args.branch)
    values={'policy':name,'service':p['service'],'package':p['package'],'version':p['to_version'],'port':p['port'],'regression':p['regression']}
    if args.github_output:
        with open(args.github_output,'a') as f:
            for k,v in values.items():f.write(f'{k}={v}\n')
    print(json.dumps(values))
