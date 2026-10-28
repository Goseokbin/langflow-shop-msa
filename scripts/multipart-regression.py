"""Exercise form parsing through installed FastAPI/Starlette, without test-only HTTP deps."""
import asyncio,importlib.metadata,json
from fastapi import FastAPI,File,Form,UploadFile

app=FastAPI()
@app.post('/form')
def form(username:str=Form(...)):
    return {'username':username}
@app.post('/upload')
async def upload(username:str=Form(...),document:UploadFile=File(...)):
    return {'username':username,'filename':document.filename,'content':(await document.read()).decode()}

async def request(path,body,content_type):
    messages=[]
    scope={'type':'http','asgi':{'version':'3.0'},'http_version':'1.1','method':'POST','scheme':'http','path':path,'raw_path':path.encode(),'root_path':'','query_string':b'','headers':[(b'content-type',content_type.encode()),(b'content-length',str(len(body)).encode())],'client':('127.0.0.1',1234),'server':('test',80)}
    async def receive():return {'type':'http.request','body':body,'more_body':False}
    async def send(message):messages.append(message)
    await app(scope,receive,send)
    return next(m['status'] for m in messages if m['type']=='http.response.start'),json.loads(b''.join(m.get('body',b'') for m in messages if m['type']=='http.response.body'))

async def main():
    code,data=await request('/form',b'username=demo-user','application/x-www-form-urlencoded')
    assert code==200 and data=={'username':'demo-user'}
    body=b'--demo-boundary\r\nContent-Disposition: form-data; name="username"\r\n\r\ndemo-user\r\n--demo-boundary\r\nContent-Disposition: form-data; name="document"; filename="demo.txt"\r\nContent-Type: text/plain\r\n\r\ndemo content\r\n--demo-boundary--\r\n'
    code,data=await request('/upload',body,'multipart/form-data; boundary=demo-boundary')
    assert code==200 and data=={'username':'demo-user','filename':'demo.txt','content':'demo content'}
    assert (await request('/form',b'','application/x-www-form-urlencoded'))[0]==422
    assert (await request('/upload',b'invalid','multipart/form-data'))[0]==400
asyncio.run(main())
print(json.dumps({'package_version':importlib.metadata.version('python-multipart'),'urlencoded_form':'passed','multipart_upload':'passed','required_field_validation':'passed','missing_boundary_rejected':'passed'}))
