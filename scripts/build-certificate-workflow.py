#!/usr/bin/env python3
"""Generate a native Concert TLS inventory workflow. Only public certificate data is collected."""
import argparse
import json
import pathlib


def build(config):
    if not config.get('targets') or any(not t.get('host') or t.get('port') != 443 for t in config['targets']):
        raise ValueError('Explicit HTTPS host allowlist with port 443 required')
    def var(name,value='null',**kw):
        return {'name':name,'isInput':False,'isOutput':False,'required':False,'level':'INTERMEDIATE','type':{'type':'any'},'value':value,**kw}
    def block(name,action,**inputs):
        return {'name':name,'action':action,'inputs':[{'name':k,'value':v} for k,v in inputs.items()]}
    flow={'name':'Langflow Certificate Inventory','platform':'node',
      'meta':{'version':5,'layout':'flow','workerGroup':'default','description':'Read public TLS certificates from explicit HTTPS routes, deduplicate shared certificates, ingest into Concert and verify inventory. No keys or certificate rotation.'},
      'variables':[var('config',json.dumps(config)),var('result','{}',isOutput=True),var('certificates','{}'),var('observations','[]'),var('certificatePem','""'),var('signatureAlgorithm','""'),var('attempts','0'),var('ingestionComplete','false')],
      'blocks':[{'action':'foreach','name':'ForEachTarget','list':'$config.targets','blocks':[
        block('ReadTLS','system/Common/OpenSSL/Get SSL Certificate',url='$ForEachTarget.item.host',port='443',protocol='"https:"'),
        {'name':'EncodePublicCertificate','function':pathlib.Path(__file__).with_name('certificate-signature.js').read_text()+r'''
let raw=$ReadTLS.result.raw;
if (!raw) throw new Error("TLS response lacks public DER certificate");
for(let n=0;n<4 && raw.data;n++) raw=raw.data;
const bytes=Array.isArray(raw)?raw:Object.keys(raw).filter(k=>/^\d+$/.test(k)).sort((a,b)=>Number(a)-Number(b)).map(k=>raw[k]);
if(bytes.length<100 || bytes[0]!==48) throw new Error("Unsupported DER representation: "+Object.keys(raw).slice(0,5).join(","));
$signatureAlgorithm=certificateSignature(bytes);
const b64=Buffer.from(bytes).toString("base64");
$certificatePem="-----BEGIN CERTIFICATE-----\n"+b64.match(/.{1,64}/g).join("\n")+"\n-----END CERTIFICATE-----\n";
'''} ,
        block('DecodeCertificate','system/Common/OpenSSL/Decode X509',data='$certificatePem'),
        {'name':'ValidateAndGroup','function':r'''
const raw=$ReadTLS.result, decoded=$DecodeCertificate.result, target=$ForEachTarget.item;
if (!raw || !raw.serialNumber || !Number.isFinite(Date.parse(raw.valid_to))) throw new Error("Incomplete TLS certificate: "+target.host);
const serial=String(raw.serialNumber).replace(/:/g,"").toUpperCase();
const fingerprint=raw.fingerprint256;
if (!fingerprint) throw new Error("Missing SHA256 certificate fingerprint");
const properties={subject:decoded.subject.replace(/\n/g,", "),issuer:decoded.issuer.replace(/\n/g,", "),
 validity_start_date:new Date(raw.valid_from).toISOString().replace("T"," ").replace(/\.\d{3}Z$/," +0000 UTC"),
 validity_end_date:new Date(raw.valid_to).toISOString().replace("T"," ").replace(/\.\d{3}Z$/," +0000 UTC"),
 certificate_type:"SSL/TLS",namespace:$config.namespace,dns_names:raw.subjectaltname||"",fingerprint256:fingerprint,
 metadata:JSON.stringify({source:"Live HTTPS handshake through Concert Workflows",cluster_name:$config.cluster,namespace:$config.namespace,certificate_host:target.host,demo:!!target.demo,key_algorithm:raw.modulus?"RSA":"unknown",key_size:String(raw.bits),key_length:String(raw.bits),bit_length:String(raw.bits),hash_algorithm:$signatureAlgorithm,signature_algorithm:$signatureAlgorithm})};
if (raw.bits) {properties.key_length=String(raw.bits);properties.key_size=String(raw.bits);}
properties.hash_algorithm=$signatureAlgorithm;
properties.signature_algorithm=$signatureAlgorithm;
if (raw.modulus) properties.key_algorithm="RSA";
if (!$certificates[fingerprint]) $certificates[fingerprint]={type:"certificate",ref:"certificate:"+serial,serial_number:serial,
 properties:Object.entries(properties).map(([name,value])=>({name,value})),access_points:[]};
const cert=$certificates[fingerprint];
if (!cert.access_points.some(p=>p.url==="https://"+target.host)) cert.access_points.push({name:target.host,is_public:"true",url:"https://"+target.host,port:443});
$observations.push({host:target.host,serial_number:serial,fingerprint256:fingerprint,subject:raw.subject.CN,issuer:raw.issuer.CN,
 not_after:raw.valid_to,days_remaining:Math.floor((Date.parse(raw.valid_to)-Date.now())/86400000),demo:!!target.demo,
 key_bits:raw.bits,signature_algorithm:$signatureAlgorithm});
'''}]},
        {'name':'BuildCertificateDocument','function':r'''
const components=Object.values($certificates);
$document={components,dependencies:[{ref:"environment:"+$config.environment,depends_on:components.map(c=>c.ref)}]};
$result={stage:"collected",target_count:$config.targets.length,unique_certificates:components.length,observations:$observations};
'''}]}
    def request(name,path,method='GET',body=None,query=None):
        inputs={'method':json.dumps(method),'host':'"https://"+$config.concert_host','path':json.dumps(path),
            'headers':'{"Accept":"application/json","Content-Type":"application/json","InstanceID":"0000-0000-0000-0000"}',
            'authKey':'$config.read_auth','rejectUnauthorized':'true','timeout':'60'}
        if body: inputs['body']=body
        if query: inputs['query']=query
        return block(name,'system/Common/HTTP/HTTP Request',**inputs)
    flow['blocks'].extend([
        block('UploadCertificates','system/IBM/Concert/Import Data/Upload Files to Concert',authKey='$config.upload_auth',
            file='{"data_type":"certificate","filename":JSON.stringify($document)}',fileType='"json"',saveAs='"langflow-shop-certificates.json"'),
        {'name':'RequireIngestionReceipt','function':'if (!$UploadCertificates.result || !$UploadCertificates.result.event_ids || $UploadCertificates.result.event_ids.length!==1) throw new Error("No single certificate ingestion event receipt");'},
        {'action':'while','name':'WaitForIngestion','condition':'!$ingestionComplete && $attempts<60','blocks':[
            request('ReadIngestionStatus','/concert/ingestion/api/v1/table_of_contents/lz/advanced_search',method='POST',
                body='{"filters":{"logic":"and","conditions":[{"field":"event_id","value":$UploadCertificates.result.event_ids[0],"operator":"="}]},"pagination":{"page":1,"page_size":10}}'),
            {'name':'CheckIngestionStatus','function':r'''
if ($ReadIngestionStatus.statusCode!==200) throw new Error("Unable to verify ingestion");
const data=typeof $ReadIngestionStatus.result==="string"?JSON.parse($ReadIngestionStatus.result):$ReadIngestionStatus.result;
const record=(data.toc_records||[])[0];
if(record && String(record.status).startsWith("error")) throw new Error("Certificate ingestion failed: "+record.status);
$ingestionComplete=!!record && record.status==="processing_completed";
$attempts++;
'''},
            {'action':'if','name':'PauseBeforeRetry','condition':'!$ingestionComplete','then':[block('WaitThreeSeconds','system/Common/Sleep',seconds='3')],'else':[]}]},
        {'name':'RequireCompletedIngestion','function':'if (!$ingestionComplete) throw new Error("Certificate ingestion did not finish within the verification window");'},
        request('ReadCertificateInventory','/concert/core/api/v1/certificates',query='{"page_size":2000,"filter":"environment_id:"+$config.environment_id}'),
        {'name':'VerifyCurrentCertificates','function':r'''
if($ReadCertificateInventory.statusCode!==200) throw new Error("Certificate inventory query failed");
const inventory=typeof $ReadCertificateInventory.result==="string"?JSON.parse($ReadCertificateInventory.result):$ReadCertificateInventory.result;
if (inventory.pagination && inventory.pagination.total_count>2000) throw new Error("Certificate pagination needs extension");
const records=inventory.certificates||[];
const expected=Object.values($certificates);
const verified=expected.map(c=>{
 const record=records.find(x=>String(x.serial_number).replace(/:/g,"").toUpperCase()===c.serial_number);
 if(!record) throw new Error("Expected certificate not in environment: "+c.serial_number);
 if((record.access_points||[]).length<c.access_points.length) throw new Error("Certificate access points were not fully linked");
 return {id:record.id,serial_number:record.serial_number,subject:record.subject,issuer:record.issuer,
 status:record.status,validity_end_date:record.validity_end_date,access_points:(record.access_points||[]).length};
});
$result={stage:"verified",target_count:$config.targets.length,unique_certificates:expected.length,
 observation_time:new Date().toISOString(),observations:$observations,certificates:verified,ingestion_event:$UploadCertificates.result.event_ids[0]};
'''}])
    flow['variables'].append(var('document','{}'))
    return flow


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    pathlib.Path(a.output).write_text(json.dumps(build(json.loads(pathlib.Path(a.config).read_text())),indent=2,ensure_ascii=False)+'\n')
