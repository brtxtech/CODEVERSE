"""Explicitly authenticated career graph endpoints. No CV text is persisted here."""
from __future__ import annotations
from fastapi import APIRouter,Depends,HTTPException,UploadFile,File
from pydantic import BaseModel,Field
from .identity import authenticated_user
from .career_pipeline import build_pipeline,fetch_jobs,ProviderUnavailable,to_csv
from .main import extract_cv

router=APIRouter(prefix='/api/v1/workflow',tags=['Authenticated career pipeline'])
class Offer(BaseModel):
    id:str='';title:str='';company:str='';location:str='';remote:bool=False;url:str='';description:str='';source:str='user_supplied';posted_at:str|None=None;collected_at:str|None=None
class RunRequest(BaseModel):
    skills:list[str]=Field(default_factory=list,max_length=150)
    target_job:str=Field(min_length=15,max_length=20000)
    location:str=Field(default='',max_length=150)
    offers:list[Offer]=Field(default_factory=list,max_length=200)
    use_live_offers:bool=False

@router.post('/cv/extract')
async def protected_extract(file:UploadFile=File(...),_user:str=Depends(authenticated_user)):
    return await extract_cv(file)

@router.post('/run')
async def run(req:RunRequest,_user:str=Depends(authenticated_user)):
    items=[o.model_dump() for o in req.offers]
    provider_status='user_supplied'
    if req.use_live_offers:
        try:
            items=await fetch_jobs(limit=80,pages=2)
            provider_status='Arbeitnow_live_response'
        except ProviderUnavailable:
            provider_status='unavailable_no_fabricated_offers'
            if not items: items=[]
    outcome=build_pipeline(req.skills,req.target_job,items,req.location)
    outcome['provider_status']=provider_status
    return outcome

@router.get('/jobs')
async def jobs(limit:int=30,_user:str=Depends(authenticated_user)):
    try:return {'offers':await fetch_jobs(limit=min(max(limit,1),80)),'source':'Arbeitnow'}
    except ProviderUnavailable as e:raise HTTPException(503,str(e)) from e
