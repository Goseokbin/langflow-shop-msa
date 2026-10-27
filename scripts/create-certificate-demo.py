#!/usr/bin/env python3
"""Create one isolated short-lived TLS demo route; existing routes are never modified."""
import argparse
import base64
import json
import pathlib
import subprocess
import tempfile


def oc(*args, data=None):
    return subprocess.check_output(['oc', *args], input=json.dumps(data) if data is not None else None, text=True).strip()


if __name__ == '__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--namespace',default='shopping-mall')
    ap.add_argument('--days',type=int,default=5)
    args=ap.parse_args()
    if not 1 <= args.days <= 30:
        raise SystemExit('Initial demonstration validity must be 1–30 days')
    ns=args.namespace
    frontend=json.loads(oc('get','route','frontend','-n',ns,'-o','json'))
    domain=frontend['spec']['host'].split('.',1)[1]
    host='certificate-demo-'+ns+'.'+domain
    # Re-running does not rotate a certificate or overwrite an existing resource.
    exists=subprocess.run(['oc','get','route','certificate-demo','-n',ns],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0
    if exists:
        route=json.loads(oc('get','route','certificate-demo','-n',ns,'-o','json'))
        if route['metadata'].get('labels',{}).get('langflow-shop.dev/certificate-demo')!='true':
            raise SystemExit('Existing route is not owned by this demo')
        print(json.dumps({'status':'already_exists','host':route['spec']['host']}))
        raise SystemExit(0)
    with tempfile.TemporaryDirectory(prefix='concert-certificate-') as td:
        cert=pathlib.Path(td)/'tls.crt';key=pathlib.Path(td)/'tls.key'
        subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-noenc','-days',str(args.days),
            '-keyout',str(key),'-out',str(cert),'-subj','/CN=langflow-shop-certificate-demo/O=Langflow Shop Certificate Demo',
            '-addext','subjectAltName=DNS:'+host,'-addext','basicConstraints=critical,CA:FALSE'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        key.chmod(0o600)
        labels={'langflow-shop.dev/certificate-demo':'true','app.kubernetes.io/part-of':'langflow-shop'}
        secret={'apiVersion':'v1','kind':'Secret','metadata':{'name':'concert-certificate-demo-tls','namespace':ns,'labels':labels},'type':'kubernetes.io/tls',
            'data':{'tls.crt':base64.b64encode(cert.read_bytes()).decode(),'tls.key':base64.b64encode(key.read_bytes()).decode()}}
        route={'apiVersion':'route.openshift.io/v1','kind':'Route','metadata':{'name':'certificate-demo','namespace':ns,'labels':labels,
            'annotations':{'langflow-shop.dev/purpose':'Short-lived self-signed certificate for Concert expiry demonstration only'}},
            'spec':{'host':host,'to':{'kind':'Service','name':'frontend','weight':100},'port':frontend['spec']['port'],
                'tls':{'termination':'edge','certificate':cert.read_text(),'key':key.read_text(),'insecureEdgeTerminationPolicy':'Redirect'},'wildcardPolicy':'None'}}
        oc('apply','-f','-',data=secret)
        oc('apply','-f','-',data=route)
    print(json.dumps({'status':'created','host':host,'namespace':ns,'validity_days':args.days,'self_signed':True,'existing_routes_changed':False}))
