"""Explicit demo releases retain SHA/digest provenance and require a real remediation gate."""
import importlib.util
import json
from pathlib import Path
import re
import subprocess


def load_release(path):
    doc=json.loads(Path(path).read_text())
    if set(doc)!={'version','remediation_policy'} or doc['version'] not in {'1.0.0','1.0.1'}:
        raise ValueError('Recording demo release must be 1.0.0 or 1.0.1')
    expected=None if doc['version']=='1.0.0' else 'multipart-cart'
    if doc['remediation_policy']!=expected:raise ValueError('Release remediation scope does not match the recording scenario')
    return doc


def bind_release(version,commit,namespace):
    if not re.fullmatch(r'\d+\.\d+\.\d+',version) or not re.fullmatch(r'[a-f0-9]{40}',commit):
        raise ValueError('Invalid semantic release provenance')
    name='langflow-shop-release-'+version.replace('.','-')
    value=subprocess.check_output(['oc','get','cm',name,'-n',namespace,'--ignore-not-found','-o','json'],text=True).strip()
    if value:
        if json.loads(value)['data'].get('commit')!=commit:
            raise ValueError('This semantic release is bound to another commit. Bump release.json or explicitly reset the rehearsal baseline.')
        return
    doc={'apiVersion':'v1','kind':'ConfigMap','metadata':{'name':name,'namespace':namespace,'labels':{'app.kubernetes.io/part-of':'langflow-shop'}},'immutable':True,'data':{'commit':commit,'version':version}}
    subprocess.run(['oc','create','-f','-'],input=json.dumps(doc),text=True,check=True,stdout=subprocess.DEVNULL)


def verify_remediation(release_file,output):
    release=load_release(release_file)
    if release['remediation_policy'] is None:return {'version':release['version'],'policy':None,'baseline':True,'passed':False}
    from patch_catalog import load_policies
    policy=load_policies()[release['remediation_policy']]
    spec=importlib.util.spec_from_file_location('recording_scan_guard',Path(__file__).with_name('verify-patch.py'))
    guard=importlib.util.module_from_spec(spec);spec.loader.exec_module(guard)
    out=Path(output)
    rows=json.loads((out/'image-scans.json').read_text())
    images=[x for x in rows if x['name']==policy['service']]
    if len(images)!=1:raise ValueError('Expected one actual target image scan')
    source=json.loads((out/'source-scan.json').read_text())
    def scan(row):return json.loads((out/Path(row['file']).name).read_text())
    source_gate=guard.validate_scan(scan(source),policy,source=True)
    image_gate=guard.validate_scan(scan(images[0]),policy)
    return {'version':release['version'],'policy':release['remediation_policy'],'service':policy['service'],'passed':True,'source':source_gate,'image':image_gate}
