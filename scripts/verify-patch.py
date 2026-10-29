#!/usr/bin/env python3
"""Verify a constrained dependency patch or real Trivy inventory; never equate no output with safe."""
import argparse
import json
import pathlib
import os
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
def load_policy(name='requests'):
    from patch_catalog import load_policies
    policies=load_policies()
    if name not in policies:raise ValueError('Unknown patch policy')
    return policies[name]

POLICY = load_policy(os.environ.get('PATCH_POLICY','requests'))


def validate_change(before, after, changed):
    p = POLICY
    old, new = f"{p.get('requirement',p['package'])}=={p['from_version']}", f"{p.get('requirement',p['package'])}=={p['to_version']}"
    if changed != [p['file']] or before.splitlines().count(old) != 1:
        raise ValueError('Patch scope or base version differs from the approved policy')
    if after != before.replace(old, new):
        raise ValueError('Patch must contain exactly the approved one-line version change')


def validate_scan(doc, policy=None, source=False):
    p = policy or POLICY
    results = doc.get('Results', [])
    if source:
        suffix = str(pathlib.PurePosixPath(p['file']).relative_to('services'))
        results = [r for r in results if r.get('Target', '').replace('\\', '/').endswith('/'+suffix) or r.get('Target') == suffix]
        if len(results) != 1:
            raise ValueError('Expected exactly one selected service dependency manifest in source scan')
    packages = [x for r in results for x in r.get('Packages', []) if x['Name'] == p['package']]
    if not packages or any(x['Version'] != p['to_version'] for x in packages):
        raise ValueError('Target package/version missing or unexpected in actual scan inventory')
    findings = [v['VulnerabilityID'] for r in results for v in r.get('Vulnerabilities', [])
                if v['PkgName'] == p['package'] and v['VulnerabilityID'] in p['cves']]
    if findings:
        raise ValueError('Target CVEs still present: ' + ', '.join(sorted(set(findings))))
    return {'package': p['package'], 'version': p['to_version'], 'inventory_occurrences': len(packages),
            'target_cves_absent': p['cves'], 'scope': p['file'] if source else 'selected image; other findings remain for triage'}


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=['diff', 'scan'])
    ap.add_argument('value')
    ap.add_argument('--source', action='store_true')
    args = ap.parse_args()
    if args.mode == 'diff':
        before = subprocess.check_output(['git', 'show', args.value + ':' + POLICY['file']], text=True)
        changed = subprocess.check_output(['git', 'diff', '--name-only', args.value, 'HEAD'], text=True).splitlines()
        if 'release.json' in changed:
            previous=json.loads(subprocess.check_output(['git','show',args.value+':release.json'],text=True))
            current=json.loads((ROOT/'release.json').read_text())
            if previous!={'version':'1.0.0','remediation_policy':None} or current!={'version':'1.0.1','remediation_policy':'multipart-cart'} or os.environ.get('PATCH_POLICY')!='multipart-cart':
                raise ValueError('Only the recording demo 1.0.0 to 1.0.1 release transition is permitted')
            changed.remove('release.json')
        validate_change(before, (ROOT / POLICY['file']).read_text(), changed)
        print('Approved one-line patch scope verified')
    else:
        print(json.dumps(validate_scan(json.loads(pathlib.Path(args.value).read_text()), source=args.source), indent=2))
