#!/usr/bin/env python3
"""Verify a constrained dependency patch or real Trivy inventory; never equate no output with safe."""
import argparse
import json
import pathlib
import os
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
def load_policy(name='requests'):
    paths={'requests':'scripts/patch-policy.json','multipart':'scripts/patch-policies/multipart.json'}
    if name not in paths:raise ValueError('Unknown patch policy')
    return json.loads((ROOT/paths[name]).read_text())

POLICY = load_policy(os.environ.get('PATCH_POLICY','requests'))


def validate_change(before, after, changed):
    p = POLICY
    old, new = f"{p['package']}=={p['from_version']}", f"{p['package']}=={p['to_version']}"
    if changed != [p['file']] or before.splitlines().count(old) != 1:
        raise ValueError('Patch scope or base version differs from the approved policy')
    if after != before.replace(old, new):
        raise ValueError('Patch must contain exactly the approved one-line version change')


def validate_scan(doc, policy=None):
    p = policy or POLICY
    packages = [x for r in doc.get('Results', []) for x in r.get('Packages', []) if x['Name'] == p['package']]
    if not packages or any(x['Version'] != p['to_version'] for x in packages):
        raise ValueError('Target package/version missing or unexpected in actual scan inventory')
    findings = [v['VulnerabilityID'] for r in doc.get('Results', []) for v in r.get('Vulnerabilities', [])
                if v['PkgName'] == p['package'] and v['VulnerabilityID'] in p['cves']]
    if findings:
        raise ValueError('Target CVEs still present: ' + ', '.join(sorted(set(findings))))
    return {'package': p['package'], 'version': p['to_version'], 'inventory_occurrences': len(packages),
            'target_cves_absent': p['cves'], 'scope': 'allowlisted package only; other findings remain for triage'}


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=['diff', 'scan'])
    ap.add_argument('value')
    args = ap.parse_args()
    if args.mode == 'diff':
        before = subprocess.check_output(['git', 'show', args.value + ':' + POLICY['file']], text=True)
        changed = subprocess.check_output(['git', 'diff', '--name-only', args.value, 'HEAD'], text=True).splitlines()
        validate_change(before, (ROOT / POLICY['file']).read_text(), changed)
        print('Approved one-line patch scope verified')
    else:
        print(json.dumps(validate_scan(json.loads(pathlib.Path(args.value).read_text())), indent=2))
