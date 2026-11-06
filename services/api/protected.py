"""Opt-in authenticated endpoints. Never available in unauthenticated demo mode."""
import os
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from .identity import authenticated_user
from .ledger import Ledger
from .main import Req, PublicScan
from .github_client import collect_public_repository, GithubCollectionError

router=APIRouter(prefix='/api/v1',tags=['Protected evidence ledger'])
def ledger():
    path=os.environ.get('CODEVERSE_LEDGER_DB')
    if not path:
        raise HTTPException(503,'Persistent ledger disabled; configure CODEVERSE_LEDGER_DB')
    return Ledger(Path(path))
class TargetCreate(BaseModel):
    job_title:str=Field(min_length=3,max_length=160)
    requirements:list[Req]=Field(min_length=1,max_length=60)
class EvidenceCreate(BaseModel):
    skill:str=Field(min_length=1,max_length=100)
    level:float=Field(ge=0,le=4)
    confidence:float=Field(ge=0,le=1)
    freshness:float=Field(default=1,ge=0,le=1)
    source:str=Field(pattern='^cv_claim$')
    repo:str|None=Field(default=None,max_length=200)
    commit_sha:str|None=Field(default=None,max_length=64)
class MilestoneCreate(BaseModel):
    skill:str=Field(min_length=1,max_length=100)
    criteria:list[str]=Field(min_length=1,max_length=20)
class Submit(BaseModel):
    reference:str=Field(min_length=4,max_length=500)

@router.post('/targets')
def create_target(body:TargetCreate,user:str=Depends(authenticated_user)):
    return {'id':ledger().create_target(user,body.job_title,[r.model_dump() for r in body.requirements])}
@router.post('/evidence')
def add_evidence(body:EvidenceCreate,user:str=Depends(authenticated_user)):
    try:
        return {'id':ledger().add_evidence(user,**body.model_dump())}
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc
@router.post('/targets/{target_id}/evaluate')
def evaluate_target(target_id:str,user:str=Depends(authenticated_user)):
    try:return ledger().evaluate(user,target_id)
    except KeyError:raise HTTPException(404,'Not found')
@router.get('/targets/{target_id}/history')
def history(target_id:str,user:str=Depends(authenticated_user)):
    try:return {'snapshots':ledger().history(user,target_id)}
    except KeyError:raise HTTPException(404,'Not found')
@router.post('/targets/{target_id}/milestones')
def create_milestone(target_id:str,body:MilestoneCreate,user:str=Depends(authenticated_user)):
    try:return {'id':ledger().create_milestone(user,target_id,body.skill,body.criteria)}
    except KeyError:raise HTTPException(404,'Not found')
@router.post('/milestones/{milestone_id}/submit')
def submit(milestone_id:str,body:Submit,user:str=Depends(authenticated_user)):
    try:return ledger().submit_milestone(user,milestone_id,body.reference)
    except KeyError:raise HTTPException(404,'Not found')
@router.delete('/account')
def delete_account_ledger(user:str=Depends(authenticated_user)):
    return ledger().delete_owner(user)

@router.post('/github/scan-and-store')
async def scan_and_store(body:PublicScan,user:str=Depends(authenticated_user)):
    """Server-sourced public manifests only, never user-attested proof of authorship."""
    owner,repo=body.repository.split('/')
    try:
        response=await collect_public_repository(owner,repo)
    except GithubCollectionError as exc:
        raise HTTPException(400,str(exc)) from exc
    stored=[]
    for e in response['evidence']:
        try:
            stored.append(ledger().add_evidence(user,e['skill'],e['level'],e['confidence'],'github_static',
                        repo=response['repository'],commit_sha=e.get('commit_sha') or None))
        except Exception as exc:
            # Duplicate evidence is not a new proof; do not claim new facts.
            if 'UNIQUE constraint failed' not in str(exc):
                raise
    return {'repository':response['repository'],'evidence_inserted':len(stored),
            'manifest_files_checked':response['files_checked'],
            'authorship_verified':False,'note':'Only public static metadata and manifest evidence was ingested.'}
