#!/usr/bin/env python3
"""One real Actions job per DevSecOps stage, with safe demo reports."""
import argparse
import concurrent.futures
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'.runtime/github-actions'
STAGES=['prepare','source-scan','sast-scan','sast-ingest','build','image-scan','concert-ingest','deploy','link-verify','smoke']
TITLES=['01 준비 · 소스 고정','02 소스 패키지 · CVE 스캔','03 CodeQL SAST 분석','04 Concert SAST 업로드 · 검증','05 이미지 7개 빌드 · Push','06 이미지 9개 Trivy 스캔','07 Concert CVE 업로드','08 OpenShift 배포','09 저장소 · 이미지 · 배포 연결 검증','10 쇼핑몰 기능 검증']


def output(*args,**kwargs):return subprocess.check_output(args,text=True,**kwargs).strip()
def read(name,default=None):
    p=WORK/'output'/name
    return json.loads(p.read_text()) if p.exists() else default


def freeze():
    if output('git','status','--porcelain','--untracked-files=no',cwd=ROOT):raise RuntimeError('Build requires a clean checkout')
    commit=output('git','rev-parse','HEAD',cwd=ROOT)
    if commit!=os.environ['GITHUB_SHA']:raise RuntimeError('Checkout SHA differs from Actions event')
    WORK.mkdir(parents=True,exist_ok=True)
    archive=WORK/'source.tar.gz'
    with tarfile.open(archive,'w:gz') as tar:
        for name in output('git','ls-files','-z',cwd=ROOT).split('\0'):
            if name:tar.add(ROOT/name,arcname=name,recursive=False)
    (WORK/'source').mkdir(exist_ok=True)
    with tarfile.open(archive) as tar:tar.extractall(WORK/'source',filter='data')
    manifest={'run_id':'github-'+os.environ['GITHUB_RUN_ID'],'repository':'https://github.com/'+os.environ['GITHUB_REPOSITORY'],
              'repo_name':os.environ['GITHUB_REPOSITORY'].split('/')[-1],'branch':os.environ['GITHUB_REF_NAME'],
              'git_base_commit':commit,'dirty':False,'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest()}
    (WORK/'source-manifest.json').write_text(json.dumps(manifest,indent=2))


def context():
    namespace=os.environ.get('SHOP_NAMESPACE','shopping-mall')
    config=json.loads(output('oc','get','configmap','langflow-shop-pipeline-config','-n',namespace,'-o','json'))['data']
    for key in ['CONCERT_HOST','CONCERT_APP_API','CONCERT_ENVIRONMENT_ID','CONCERT_DEPLOYMENT_ID','CONCERT_PREVIOUS_REPO_URL','DOCKER_REGISTRY_HOST']:os.environ[key]=config[key]
    for key in ['APPLICATION_NAME','APPLICATION_VERSION','SHOP_NAMESPACE']:
        if key in config:os.environ[key]=config[key]
    manifest=json.loads((WORK/'source-manifest.json').read_text())
    if manifest['git_base_commit']!=os.environ['GITHUB_SHA'] or manifest['run_id']!='github-'+os.environ['GITHUB_RUN_ID']:
        raise RuntimeError('State belongs to a different commit or workflow run')
    auth=WORK/'authorization';auth.touch(mode=0o600);auth.chmod(0o600);auth.write_text(os.environ.pop('CONCERT_AUTH_HEADER').strip())
    os.environ.update(PIPELINE_WORKSPACE=str(WORK),CONCERT_AUTH_FILE=str(auth),PIPELINE_ENGINE='github-actions',PIPELINE_PUBLIC_LOGS='1')
    source=WORK/'source';sys.path.insert(0,str(source/'scripts'))
    spec=importlib.util.spec_from_file_location('pipeline',source/'scripts/pipeline-stage.py')
    stages=importlib.util.module_from_spec(spec);spec.loader.exec_module(stages)
    # Report paths are reconstructed rather than trusting a previous runner's directory.
    for name in ['source-scan.json','image-scans.json']:
        data=read(name)
        if data:
            for row in data if isinstance(data,list) else [data]:row['file']=str(stages.OUT/Path(row['file']).name)
            stages.save(name,data)
    return manifest,auth,stages


def build_images(manifest,stages):
    source=WORK/'source';commit=manifest['git_base_commit'];OWN=stages.OWN
    registry=os.environ['DOCKER_REGISTRY_HOST']
    run_url=f"https://github.com/{os.environ['GITHUB_REPOSITORY']}/actions/runs/{os.environ['GITHUB_RUN_ID']}"
    subprocess.run(['docker','login',registry,'--username','serviceaccount','--password-stdin'],input=os.environ['OPENSHIFT_TOKEN'],text=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True)
    def build(name):
        namespace=os.environ.get('SHOP_NAMESPACE','shopping-mall')
        tag=f'{registry}/{namespace}/{name}:{commit}'
        labels={'org.opencontainers.image.source':manifest['repository'],'org.opencontainers.image.revision':commit,
                'io.langflow-shop.source-snapshot-sha256':manifest['archive_sha256']}
        args=['docker','build','--pull','--tag',tag]
        for key,value in labels.items():args.extend(['--label',key+'='+value])
        logfile=stages.OUT/(name+'.build.log')
        with logfile.open('w') as log:
            try:
                subprocess.run([*args,str(source/'services'/name)],stdout=log,stderr=subprocess.STDOUT,check=True)
                subprocess.run(['docker','push',tag],stdout=log,stderr=subprocess.STDOUT,check=True)
            except subprocess.CalledProcessError:
                # Build output may contain internal registry names; retain locally.
                print('Docker build/push failed: '+name,flush=True)
                raise
        image=json.loads(output('docker','image','inspect',tag))[0]
        if any(image['Config']['Labels'].get(k)!=v for k,v in labels.items()):
            raise RuntimeError('Image source label mismatch: '+name)
        digests=[x.split('@',1)[1] for x in image['RepoDigests'] if x.startswith(registry+'/'+namespace+'/'+name+'@')]
        if len(set(digests))!=1:raise RuntimeError('Cannot establish pushed digest: '+name)
        result={'name':name,'build':f"github-actions/{os.environ['GITHUB_RUN_ID']}/{name}",'run_url':run_url,
                'image':'image-registry.openshift-image-registry.svc:5000/'+namespace+'/'+name+'@'+digests[0],
                'git_commit':commit,'source.snapshot-sha256':manifest['archive_sha256'],'verified_oci_labels':labels}
        stages.save(name+'.build.json',result)
        print('Built and verified image: '+name,flush=True)
        return result
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        builds=list(pool.map(build,OWN))
    stages.save('builds.json',builds);stages.event('build','succeeded',built_images=len(builds))

def smoke(stages,manifest):
    source=WORK/'source';(source/'docs').mkdir(exist_ok=True)
    with (stages.OUT/'smoke.log').open('w') as log:
        subprocess.run(['python3',str(source/'scripts/smoke-test.py')],cwd=source,stdout=log,stderr=subprocess.STDOUT,check=True)
    result=json.loads((stages.OUT/'smoke.log').read_text())
    stages.save('smoke.json',{'checks':result['results'],'passed':len(result['results'])})
    verification=read('verification.json')
    public={'run_url':run_url(),'git_commit':manifest['git_base_commit'],'source_snapshot_sha256':manifest['archive_sha256'],
            'repository':verification['repository'],'images':[{k:v for k,v in row.items() if k in ['name','packages','cves','os_unsupported']} for row in verification['images']],
            'topology_counts':verification['topology_counts'],'internal_endpoints':verification['internal_endpoints'],
            'sast':read('sast-verification.json'),'commerce_smoke':'passed','oci_revision_verified_images':len(read('builds.json',[]))}
    stages.save('public-verification.json',public)
    import promotion_bundle
    promotion_bundle.create_release(stages,manifest,stages.api.Concert(authorization=stages.AUTH))
    stages.event('smoke','succeeded',checks=len(result['results']))


def run_url():return f"https://github.com/{os.environ['GITHUB_REPOSITORY']}/actions/runs/{os.environ['GITHUB_RUN_ID']}"


def table(headers,rows):
    escape=lambda v:str(v).replace('|','\\|').replace('\n',' ')
    return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+['| '+' | '.join(escape(v) for v in row)+' |' for row in rows])


def report(stage,outcome):
    manifest=json.loads((WORK/'source-manifest.json').read_text()) if (WORK/'source-manifest.json').exists() else {}
    data={'stage':stage,'outcome':outcome,'commit':os.environ['GITHUB_SHA'],'run_url':run_url()}
    text=[f'## {TITLES[STAGES.index(stage)]}',f'결과: **{outcome}** · Commit: `{os.environ["GITHUB_SHA"]}`',f'[전체 단계 그래프로 돌아가기]({run_url()})']
    if stage=='prepare':
        data.update({'source_snapshot_sha256':manifest.get('archive_sha256'),'clean_checkout':manifest.get('dirty') is False})
        text += ['이후 모든 job은 같은 소스 아카이브와 커밋을 검증합니다.',f'소스 SHA-256: `{manifest.get("archive_sha256","미생성")}`']
    elif stage=='source-scan' and read('source-scan.json'):
        scan=read('source-scan.json');doc=json.loads((WORK/'output/repository.cdx.json').read_text())
        purls=sorted({c['purl'] for c in doc.get('components',[]) if c.get('purl') and c.get('type')!='operating-system'})
        data.update({'packages':scan['packages'],'trivy_advisories':scan['vulnerabilities'],'python_packages':sum(x.startswith('pkg:pypi/') for x in purls),'npm_packages':sum(x.startswith('pkg:npm/') for x in purls),'package_purls':purls})
        text += [table(['검사 대상','수집 수'],[['Python 패키지',data['python_packages']],['npm 패키지',data['npm_packages']],['전체 고유 패키지',scan['packages']],['Trivy advisory 항목',scan['vulnerabilities']]]),'소스 의존성 검사 결과입니다. OS·Python 전이 의존성은 04 이미지 스캔에서 보완합니다.']
    elif stage=='sast-scan' and read('sast-scan.json'):
        d=read('sast-scan.json');data['sast']=d
        text += [table(['분석 언어','CodeQL 발견 항목','규칙 수'],[[a['language'],a['finding_count'],len(a['rules'])] for a in d['analyses']]),'검사 범위: services/ · security-extended. 실제 CodeQL SARIF 결과이며 CVE 검사와 별개입니다.']
        findings=[f for a in d['analyses'] for f in a['findings']]
        if findings:text += [table(['CodeQL 규칙','파일','줄','심각도'],[[f['rule_id'],f['locations'][0]['file'],f['locations'][0]['line'],f['severity']] for f in findings])]
        else:text += ['이 규칙 집합에서 발견 항목 0개입니다. 분석 미실행이나 전체 코드 안전 판정을 뜻하지 않습니다.']
    elif stage=='sast-ingest' and read('sast-verification.json'):
        data['sast']=read('sast-verification.json')
        text += [table(['Concert SAST 확인 항목','결과'],data['sast'].items()),'확인 위치: Concert → langflow-shop 1.0.0 → 노출, 또는 저장소 → SAST 노출. static_code_scan 업로드 처리 완료 후 실제 규칙 ID를 대조합니다.']
    elif stage=='build' and read('builds.json'):
        data['images']=[{'service':b['name'],'digest':b['image'].rsplit('@',1)[1],'commit':b['git_commit'],'oci_labels_verified':True} for b in read('builds.json')]
        text += [table(['서비스','빌드 이미지 digest','소스 label'],[[b['service'],'`'+b['digest']+'`','검증 통과'] for b in data['images']]),'Push한 digest가 스캔·배포까지 유지됩니다.']
    elif stage=='image-scan' and read('image-scans.json'):
        data['images']=[{k:v for k,v in b.items() if k in ['name','packages','vulnerabilities','os_unsupported']} for b in read('image-scans.json')]
        text += [table(['이미지','패키지','Trivy advisory','분석 범위'],[[b['name'],b['packages'],b['vulnerabilities'],'OS CVE 매칭 미지원 · inventory만 수집' if b['os_unsupported'] else '패키지 + CVE'] for b in data['images']]),'CVE 수는 고유 취약점 총계로 이미지 간 합산하지 않습니다.']
    elif stage=='concert-ingest':
        events=[]
        for p in sorted((WORK/'output').glob('*.ingestion.json')):
            d=json.loads(p.read_text());events.append({'report':p.name,'event_ids':d.get('event_ids',[]),'processing_completed':outcome=='success'})
        data['ingestion_events']=events
        text += [table(['업로드 파일 / 타입','이벤트','완료 판정'],[[e['report'],', '.join(e['event_ids']),'processing_completed 확인' if e['processing_completed'] else '로그 확인'] for e in events]),'단순 업로드 접수가 아니라 Concert 처리 완료를 기다립니다. 현재는 CVE 발견 수로 배포를 차단하지 않는 감사 모드입니다.']
    elif stage=='deploy' and read('deployment-verification.json'):
        data['deployments']=read('deployment-verification.json')
        text += [table(['Deployment','배포 digest','Ready'],[[b['name'],'`'+b['digest']+'`',b['ready']] for b in data['deployments']]),'확인 위치: OpenShift → shopping-mall → Deployments. 07에서 Concert의 관계를 대조합니다.']
    elif stage=='link-verify' and read('verification.json'):
        d=read('verification.json');data.update({'repository':d['repository'],'topology_counts':d['topology_counts'],'internal_endpoints':d['internal_endpoints']})
        text += ['### 내부 OpenAPI 엔드포인트 수집 · Concert 대조',
                 table(['서비스','수집 유형','경로 수','HTTP operation 수'],[[r['name'],r['kind'],r['paths'],r['operations']] for r in d['internal_endpoints']['services']]),
                 '내부 주소는 액세스 지점으로 유지하고 실제 OpenAPI 경로를 엔드포인트로 수집합니다. 동일 경로의 GET/POST는 경로 1개, operation 2개입니다. 웹 화면은 루트, PostgreSQL은 TCP 접속점으로 구분합니다.']
        text += [table(['Concert 확인 항목','조회 결과'],[['저장소 패키지',d['repository']['packages']],['CVE 발견 행',d['repository']['cves']],['고유 CVE·패키지·버전 조합',d['repository'].get('unique_cve_package_version_combinations','미조회')],*d['topology_counts'].items()]),'확인 위치: Concert → langflow-shop 1.0.0 → 저장소 → 사용된 패키지 / CVE 찾은 결과 / 결과 빌드 아티팩트.', '저장소 SCA는 branch 범위입니다. 반복 발견 행과 고유 조합을 구분합니다. 정확한 커밋은 이미지 OCI label 및 Deployment 주석으로 검증합니다.']
    elif stage=='smoke' and read('smoke.json'):
        data['commerce_checks']=read('smoke.json');data['verification']=read('public-verification.json')
        text += [table(['쇼핑몰 기능 확인','결과'],[[check,'PASS'] for check in data['commerce_checks']['checks']]),'테스트 사용자와 취소된 주문이 남습니다. 실제 AI 생성은 모델 크레딧 부족으로 이번 통과 항목에 포함하지 않습니다.']
        if read('promotion-release.json'):
            release=read('promotion-release.json');data['promotion_release']=release
            text += ['### 운영 승인에 사용할 검증된 릴리스',
                table(['서비스','운영에 승격할 동일 digest'],[[r['name'],r['digest']] for r in release['images']]),
                '승인 대상 암호화 artifact SHA-256: `'+release['sha256']+'`',
                '다음 production job은 사용자 승인 후 이 artifact만 복호화하여 배포합니다. 운영에서 이미지를 다시 빌드하지 않습니다.']
    if outcome!='success':text += ['이 단계가 실패해 후속 단계가 실행되지 않았습니다. 해당 job의 **Run stage** 로그에서 실패 원인을 확인하세요.']
    path=ROOT/'.runtime/demo-reports';path.mkdir(parents=True,exist_ok=True)
    (path/(stage+'.json')).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    markdown='\n\n'.join(text)+'\n';(path/(stage+'.md')).write_text(markdown)
    with open(os.environ.get('GITHUB_STEP_SUMMARY',str(path/'summary.md')),'a') as file:file.write(markdown)
    print(json.dumps({'stage':stage,'outcome':outcome,'demo_report':stage+'.json'},ensure_ascii=False))


def execute(stage):
    if stage=='prepare':freeze()
    manifest,auth,stages=context()
    try:
        stages.prepare()  # Source and run identity is checked in every job.
        if stage=='sast-scan':
            import concert_sast
            result=concert_sast.collect(WORK);stages.event(stage,'succeeded',findings=result['finding_count'])
        elif stage=='sast-ingest':
            import concert_sast
            result=concert_sast.ingest(WORK,manifest,stages,auth);stages.event(stage,'succeeded',findings=result['source_findings'])
        elif stage=='build':build_images(manifest,stages)
        elif stage=='smoke':smoke(stages,manifest)
        elif stage!='prepare':
            {'source-scan':stages.source_scan,'image-scan':stages.image_scan,'concert-ingest':stages.ingest,'deploy':stages.deploy,'link-verify':stages.link_verify}[stage]()
        if stage=='deploy':
            actual={d['metadata']['name']:d for d in stages.items('deployments')};rows=[]
            for built in read('builds.json'):
                d=actual[built['name']];image=d['spec']['template']['spec']['containers'][0]['image']
                if image!=built['image'] or d['status'].get('readyReplicas',0)!=d['spec'].get('replicas',1):raise RuntimeError('Deployment digest/readiness mismatch')
                rows.append({'name':built['name'],'digest':image.rsplit('@',1)[1],'ready':d['status']['readyReplicas']})
            stages.save('deployment-verification.json',rows)
        if stage=='link-verify':
            import concert_sast
            concert_sast.verify(stages.api.Concert(authorization=auth),stages.api,WORK)
            client=stages.api.Concert(authorization=auth);d=read('verification.json');repoid=d['repository']['id']
            findings=client.request(stages.api.APP+'/source_repos/'+repoid+'/cve_findings?page_size=2000')['cve_findings']
            d['repository']['unique_cve_package_version_combinations']=len({(r['cve'],r['package_name'],r['package_version']) for r in findings})
            stages.save('verification.json',d)
    except Exception:
        # Expose useful diagnostics without credentials, paths or registry hosts.
        for log in sorted((WORK/'output').glob('*.log')):
            lines=log.read_text(errors='replace').splitlines()[-12:]
            message='\n'.join(lines)
            for key in ['OPENSHIFT_TOKEN','CONCERT_HOST','DOCKER_REGISTRY_HOST']:
                if os.environ.get(key):message=message.replace(os.environ[key],'[redacted]')
            print(f'::group::Diagnostic: {log.name}\n{message}\n::endgroup::',flush=True)
        raise
    finally:
        auth.unlink(missing_ok=True)
        if stage=='build':subprocess.run(['docker','logout',os.environ['DOCKER_REGISTRY_HOST']],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['run','report']);parser.add_argument('stage',choices=STAGES);parser.add_argument('--outcome',default='success');args=parser.parse_args()
    if args.command=='report':report(args.stage,args.outcome)
    else:execute(args.stage)
