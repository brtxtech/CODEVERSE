"""Deterministic career pipeline. No invented offers; explicit source and freshness.

Skill evidence is a claim until an authorized server-side source verifies it.
"""
from __future__ import annotations
import csv, io, re
from collections import defaultdict
from datetime import datetime, timezone
from urllib.parse import urlparse
import httpx
from .core import normalize_skill, extract_skills, job_requirements, readiness, recommend_projects

JOB_ENDPOINT = 'https://www.arbeitnow.com/api/job-board-api'

class ProviderUnavailable(Exception): pass

async def fetch_jobs(limit=50, pages=1):
    """Public documented Arbeitnow job board endpoint; no scraping or claims of coverage."""
    pages=max(1,min(2,pages)); limit=max(1,min(100,limit))
    collected=[]
    try:
        async with httpx.AsyncClient(timeout=12,follow_redirects=False,headers={'User-Agent':'CODEVERSE-MVP/0.2'}) as client:
            for page in range(1,pages+1):
                response=await client.get(JOB_ENDPOINT,params={'page':page})
                response.raise_for_status()
                payload=response.json()
                for item in payload.get('data',[]):
                    url=item.get('url','')
                    if not isinstance(url,str) or urlparse(url).scheme not in ('https','http'):continue
                    collected.append({'id':str(item.get('slug',''))[:180], 'title':str(item.get('title',''))[:180],
                       'company':str(item.get('company_name',''))[:160], 'location':str(item.get('location',''))[:160],
                       'remote':bool(item.get('remote',False)), 'url':url,
                       'description':re.sub(r'<[^>]+>',' ',str(item.get('description','')))[:15000],
                       'source':'Arbeitnow', 'collected_at':datetime.now(timezone.utc).isoformat(),
                       'posted_at':item.get('created_at')})
                    if len(collected)>=limit:return collected
    except (httpx.HTTPError, ValueError, TypeError) as ex:
        raise ProviderUnavailable('Job provider unavailable; no live offers returned') from ex
    return collected[:limit]

def match_offers(skills:list[str], offers:list[dict], location:str='', limit:int=12):
    """Deterministic match; exact location filter, no unsupported geolocation assertions."""
    owned=set(map(normalize_skill,skills)); ranked=[]
    term=location.strip().casefold()
    for job in offers:
        where=str(job.get('location','')).casefold()
        if term and term not in where and not (term=='remote' and job.get('remote')):continue
        requirements=job_requirements(str(job.get('title',''))+' '+str(job.get('description','')))
        required={r['skill'] for r in requirements}
        overlap=required&owned
        fraction=len(overlap)/len(required) if required else 0
        ranked.append({**{k:job.get(k) for k in ('id','title','company','location','remote','url','source','posted_at','collected_at')},
           'match_percent':round(fraction*100,1),'matched_skills':sorted(overlap),'missing_skills':sorted(required-owned),
           'requirement_count':len(required),'method':'taxonomy_overlap_not_hiring_probability'})
    return sorted(ranked,key=lambda x:(-x['match_percent'],-len(x['matched_skills']),x['title'] or ''))[:max(1,min(limit,50))]

def build_pipeline(cv_skills:list[str], target_job:str, offers:list[dict], location:str='', evidence:list[dict]|None=None):
    """One reproducible graph execution with explicit tabular input and output per node."""
    skills=sorted(set(map(normalize_skill,cv_skills)))
    evidence=evidence if evidence is not None else [{'skill':s,'level':2,'confidence':0.35,'source':'cv_claim'} for s in skills]
    requirements=job_requirements(target_job)
    readiness_result=readiness(requirements,evidence)
    matches=match_offers(skills,offers,location)
    gaps=sorted(set(x['skill'] for x in readiness_result['breakdown'] if x['gap']>0.2)
                | {s for offer in matches[:5] for s in offer['missing_skills']})
    recommendations=recommend_projects(readiness_result,10)
    for skill in gaps:
        if not any(x['skill']==skill for x in recommendations):
            recommendations.append({'skill':skill,'priority':0,'title':f'Build and test a {skill} integration',
                                    'criteria':['implementation','tests','documentation']})
    nodes=[
     {'id':'cv','label':'CV evidence','input':[{'uploaded_document':'parsed in memory'}],
      'output':[{'skill':s,'evidence_type':'cv_claim','confidence':0.35} for s in skills]},
     {'id':'profiles','label':'Target job profile','input':[{'job_description':target_job[:400]}],
      'output':requirements},
     {'id':'offers','label':'Employer offers','input':[{'skill':s} for s in skills],
      'output':matches},
     {'id':'gaps','label':'Skills to develop','input':readiness_result['breakdown'],
      'output':[{'skill':s,'priority':'requires evidence'} for s in gaps]},
     {'id':'repos','label':'GitHub learning projects','input':[{'skill':s} for s in gaps],
      'output':recommendations},
     {'id':'readiness','label':'Career readiness','input':readiness_result['breakdown'],
      'output':[{'score':readiness_result['score'],'skill_score':readiness_result['skill_score'],
                 'project_score':readiness_result['project_score'],'algorithm_version':readiness_result['algorithm_version']}]}
    ]
    return {'nodes':nodes,'edges':[{'from':'cv','to':'offers'},{'from':'profiles','to':'offers'},
       {'from':'offers','to':'gaps'},{'from':'cv','to':'gaps'},{'from':'gaps','to':'repos'},
       {'from':'profiles','to':'readiness'},{'from':'cv','to':'readiness'}],
       'summary':{'readiness':readiness_result,'offers_count':len(matches),'skills_count':len(skills),
                  'gaps_count':len(gaps),'source_mode':'provided_offers_or_live_provider','needs_human_review':True}}

def to_csv(rows):
    """Excel-safe CSV output with stable union columns."""
    cols=list(dict.fromkeys(k for row in rows for k in row.keys()))
    if not cols:return ''
    f=io.StringIO(); writer=csv.DictWriter(f,fieldnames=cols,extrasaction='ignore');writer.writeheader()
    for row in rows:
        normalized={k:(', '.join(map(str,v)) if isinstance(v,list) else str(v) if isinstance(v,(dict,tuple)) else v) for k,v in row.items()}
        for k,v in normalized.items():
            if isinstance(v,str) and v.lstrip().startswith(('=','+','-','@','\t','\r')):normalized[k]="'"+v
        writer.writerow(normalized)
    return f.getvalue()
