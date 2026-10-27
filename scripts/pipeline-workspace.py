#!/usr/bin/env python3
"""Authenticate and encrypt inter-job state; never upload credentials or cache."""
import argparse
import hashlib
import hmac
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile

MAGIC=b'LFSHOPSTATE1\n'
ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'.runtime/github-actions'


def mac_key(secret):
    return hmac.new(secret.encode(),b'langflow-shop-state-authentication-v1',hashlib.sha256).digest()


def seal(work,destination,secret):
    destination.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory() as directory:
        archive=Path(directory)/'state.tar.gz';cipher=Path(directory)/'state.aes'
        with tarfile.open(archive,'w:gz') as tar:
            for path in sorted(work.rglob('*')):
                rel=path.relative_to(work)
                if rel.parts[0] in {'cache','source','authorization'} or path.is_symlink():continue
                if path.is_file():tar.add(path,arcname=str(rel),recursive=False)
        subprocess.run(['openssl','enc','-aes-256-cbc','-pbkdf2','-iter','200000','-salt','-in',str(archive),'-out',str(cipher),'-pass','env:PIPELINE_STATE_KEY'],env={**os.environ,'PIPELINE_STATE_KEY':secret},check=True)
        ciphertext=cipher.read_bytes()
        destination.write_bytes(MAGIC+hmac.digest(mac_key(secret),ciphertext,'sha256')+ciphertext)


def restore(source,work,secret):
    data=source.read_bytes()
    if not data.startswith(MAGIC):raise ValueError('Invalid pipeline state format')
    signature=data[len(MAGIC):len(MAGIC)+32];ciphertext=data[len(MAGIC)+32:]
    if not hmac.compare_digest(signature,hmac.digest(mac_key(secret),ciphertext,'sha256')):
        raise ValueError('Pipeline state authentication failed')
    with tempfile.TemporaryDirectory() as directory:
        cipher=Path(directory)/'state.aes';archive=Path(directory)/'state.tar.gz';cipher.write_bytes(ciphertext)
        subprocess.run(['openssl','enc','-d','-aes-256-cbc','-pbkdf2','-iter','200000','-in',str(cipher),'-out',str(archive),'-pass','env:PIPELINE_STATE_KEY'],env={**os.environ,'PIPELINE_STATE_KEY':secret},check=True)
        work.mkdir(parents=True,exist_ok=True)
        with tarfile.open(archive) as tar:tar.extractall(work,filter='data')
    snapshot=work/'source.tar.gz';manifest=__import__('json').loads((work/'source-manifest.json').read_text())
    if hashlib.sha256(snapshot.read_bytes()).hexdigest()!=manifest['archive_sha256']:raise ValueError('Source checksum mismatch')
    (work/'source').mkdir(exist_ok=True)
    with tarfile.open(snapshot) as tar:tar.extractall(work/'source',filter='data')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['seal','restore']);p.add_argument('file',type=Path);args=p.parse_args()
    secret=os.environ['PIPELINE_STATE_KEY']
    if len(secret)<32:raise ValueError('PIPELINE_STATE_KEY must contain at least 32 characters')
    if args.command=='seal':seal(WORK,args.file,secret)
    else:restore(args.file,WORK,secret)
    print('Pipeline state '+args.command+' completed (authenticated encryption, no credentials).')
