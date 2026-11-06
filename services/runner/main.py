"""Dedicated-worker Docker orchestrator. Never deploy on a host with sensitive workloads."""
import asyncio, hmac, json, os, secrets
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel,Field
app=FastAPI(docs_url=None,redoc_url=None)
slots=asyncio.Semaphore(2)
WRAPPER='''import json,sys,io,contextlib
p=json.load(sys.stdin)
sys.stdin=io.StringIO(json.dumps(p["input"]))
buffer=io.StringIO()
with contextlib.redirect_stdout(buffer):
 exec(compile(p["code"],"skill.py","exec"),{"__name__":"__main__"})
result=buffer.getvalue()
if len(result)>100000:raise ValueError("Output too large")
json.loads(result)
sys.__stdout__.write(result)
'''
class Run(BaseModel):
    code:str=Field(max_length=20000)
    input:list=Field(max_length=40)
@app.post('/run')
async def run(body:Run,authorization:str=Header(default='')):
    expected=os.getenv('CODEVERSE_RUNNER_TOKEN','')
    if not expected or not hmac.compare_digest(authorization,'Bearer '+expected):raise HTTPException(401,'Worker authorization required')
    raw=json.dumps(body.model_dump()).encode()
    if len(raw)>2_000_000:raise HTTPException(413,'Input exceeds 2 MB')
    name='codeverse-'+secrets.token_hex(12)
    async with slots:
        proc=await asyncio.create_subprocess_exec('docker','run','--rm','--pull=never','--name',name,
           '--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges',
           '--pids-limit','32','--memory','128m','--memory-swap','128m','--cpus','0.5',
           '--user','65534:65534','--log-driver','none','--tmpfs','/tmp:rw,noexec,nosuid,size=16m',
           '-i',os.getenv('CODEVERSE_SKILL_IMAGE','codeverse-skill:1'),'python','-I','-c',WRAPPER,
           stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL)
        async def collect():
            proc.stdin.write(raw);await proc.stdin.drain();proc.stdin.close()
            chunks=[];size=0
            while True:
                part=await proc.stdout.read(16384)
                if not part:break
                size+=len(part)
                if size>120000:raise ValueError('Output limit')
                chunks.append(part)
            await proc.wait()
            if proc.returncode:raise ValueError('Skill failed')
            return json.loads(b''.join(chunks))
        try:return await asyncio.wait_for(collect(),timeout=30)
        except (TimeoutError,ValueError,ConnectionError) as exc:raise HTTPException(422,'Skill failed or exceeded execution limits') from exc
        finally:
            cleanup=await asyncio.create_subprocess_exec('docker','rm','-f',name,stdout=asyncio.subprocess.DEVNULL,stderr=asyncio.subprocess.DEVNULL)
            await cleanup.wait()
            if proc.returncode is None:proc.kill();await proc.wait()
