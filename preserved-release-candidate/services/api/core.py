"""CODEVERSE deterministic evidence and readiness engine. No LLM is permitted to set scores."""
from __future__ import annotations
import json, re, math, hashlib
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
TAXONOMY = json.loads((ROOT/'data/technology-taxonomy.json').read_text())
TECH = TAXONOMY['technologies']
TECH_BY_ID = {t['id']:t for t in TECH}
ALIASES = {
 'react':['react','react.js','reactjs'], 'angular':['angular','@angular/core'],
 'flask':['flask'], 'fastapi':['fastapi'], 'django':['django'],
 'pytorch':['pytorch','torch'], 'tensorflow':['tensorflow'],
 'transformers':['transformers','hugging face transformers'],
 'docker':['docker','dockerfile'], 'kubernetes':['kubernetes','k8s'],
 'postgresql':['postgresql','postgres','psycopg'], 'mongodb':['mongodb','mongoose'],
 'typescript':['typescript'], 'python':['python'], 'rust':['rust'],
 'github-actions':['github actions'], 'redis':['redis'], 'nextjs':['next.js','nextjs'],
 'nodejs':['node.js','nodejs'], 'scikit-learn':['scikit-learn','sklearn'],
 'rag':['retrieval augmented generation','rag'], 'llm':['large language model','llm']
}

def normalize_skill(name:str)->str:
    key=re.sub(r'[^a-z0-9]+','-',name.casefold()).strip('-')
    for ident, aliases in ALIASES.items():
        if key == ident or any(re.sub(r'[^a-z0-9]+','-',a.casefold()).strip('-')==key for a in aliases):return ident
    return key

def extract_skills(text:str)->list[dict]:
    """Conservative matching. This is a *claim*, not code-verified competence."""
    found={}
    for t in TECH:
        name=t['name']; tid=t['id']
        names=[name]+ALIASES.get(tid,[])
        for term in names:
            if len(term)<2: continue
            pattern=r'(?<![\w])'+re.escape(term)+r'(?![\w])'
            if re.search(pattern,text,re.I):
                found[tid]={'id':tid,'name':name,'category':t['category'],'source':'cv_claim','confidence':0.35}
                break
    return sorted(found.values(),key=lambda x:x['name'])

def job_requirements(text:str,skills:list[str]|None=None)->list[dict]:
    ids=skills or [t['id'] for t in extract_skills(text)]
    return [{'skill':normalize_skill(s),'weight':1.0,'required_level':2.0,'required':True} for s in dict.fromkeys(ids)]

def readiness(requirements:list[dict], evidence:list[dict], milestones:list[dict]|None=None, experience:float=0, version:str='1.0.0')->dict:
    """Measures evidence alignment, never probability of hiring."""
    ev={}
    for e in evidence:
        key=normalize_skill(e['skill'])
        if key not in ev or (e.get('level',0)*e.get('confidence',0)) > (ev[key].get('level',0)*ev[key].get('confidence',0)):
            ev[key]=e
    total=0.0; match=0.0; breakdown=[]
    for r in requirements:
        key=normalize_skill(r['skill']); weight=max(0.,float(r.get('weight',1))); required=max(0.01,float(r.get('required_level',2)))
        row=ev.get(key,{})
        level=max(0,min(4,float(row.get('level',0))))
        confidence=max(0,min(1,float(row.get('confidence',0))))
        freshness=max(0,min(1,float(row.get('freshness',1))))
        contribution=min(1,level/required)*confidence*freshness
        total+=weight; match+=weight*contribution
        breakdown.append({'skill':key,'weight':weight,'required_level':required,'evidenced_level':level,'confidence':confidence,'match':round(contribution,4),'gap':round(1-contribution,4),'evidence_id':row.get('id')})
    skill_score=100*match/total if total else 0
    ms=milestones or []
    project_score=100*(sum(max(0,float(m.get('weight',1))) for m in ms if m.get('verified'))/sum(max(0,float(m.get('weight',1))) for m in ms)) if ms else 0
    exp_score=100*max(0,min(1,float(experience)))
    score=0.7*skill_score+0.2*project_score+0.1*exp_score
    return {'score':round(score,2),'skill_score':round(skill_score,2),'project_score':round(project_score,2),'experience_score':round(exp_score,2),'algorithm_version':version,'breakdown':breakdown,'disclaimer':'Evidence alignment only, not a hiring probability.'}

def evidence_from_github(repo:dict, files:dict[str,str])->list[dict]:
    """Static evidence from selected small text manifests. No remote code execution."""
    patterns={'python':['requirements.txt','pyproject.toml'],'typescript':['tsconfig.json'],'docker':['dockerfile','compose.yaml','docker-compose.yml'],
      'kubernetes':['deployment.yaml','kustomization.yaml'],'github-actions':['.github/workflows/ci.yml']}
    result={}
    for path,content in files.items():
        p=path.lower(); content=content[:150_000]; low=content.lower()
        for t in TECH:
            tid=t['id']; names=[t['name'].lower()]+[a.lower() for a in ALIASES.get(tid,[])]
            match=any(re.search(r'(?<![a-z0-9])'+re.escape(term)+r'(?![a-z0-9])',low) for term in names if len(term)>2)
            match = match or (tid in patterns and any(p.endswith(s) for s in patterns[tid]))
            if match:
                eid=hashlib.sha256(f"{repo.get('full_name','')}:{repo.get('sha','')}:{p}:{tid}".encode()).hexdigest()[:16]
                result[tid]={'id':eid,'skill':tid,'level':1.5,'confidence':0.65,'freshness':1,'source':'github_static','repo':repo.get('full_name'),'path':path,'commit_sha':repo.get('sha'),'reason':'Dependency/configuration evidence; authorship and proficiency not established'}
    return list(result.values())

CHALLENGES={
  'docker':{'title':'Containerize a production-style API','criteria':['Dockerfile','health-check','ci-workflow']},
  'kubernetes':{'title':'Deploy a resilient service to Kubernetes','criteria':['deployment','service','readiness-probe','ci-workflow']},
  'postgresql':{'title':'Design a migrated relational data service','criteria':['migration','indexed-query','integration-test']},
  'pytest':{'title':'Build an automated Python test suite','criteria':['tests','ci-workflow']},
  'react':{'title':'Build an accessible React dashboard','criteria':['components','test','accessibility-check']},
  'fastapi':{'title':'Build a typed API with tests','criteria':['schema','endpoint','test','ci-workflow']},
}

def recommend_projects(result:dict, limit=3):
    gaps=sorted(result['breakdown'],key=lambda r:-r['weight']*r['gap'])
    return [{'skill':g['skill'],'priority':round(g['weight']*g['gap'],3),'title':CHALLENGES.get(g['skill'],{'title':f'Build a verifiable {g["skill"]} project'})['title'],
             'criteria':CHALLENGES.get(g['skill'],{'criteria':['implementation','tests','documentation']})['criteria']} for g in gaps if g['gap']>.2][:limit]

def verify_challenge(criteria:list[str], proofs:list[str])->dict:
    """MVP manual-review evidence checklist. Never treat filenames as conclusive proof of ownership."""
    satisfied=sorted(set(criteria)&set(proofs)); missing=sorted(set(criteria)-set(proofs))
    return {'ready_for_review':not missing,'satisfied':satisfied,'missing':missing,'verified':False,'reason':'Human or trusted CI review required before verified=true'}
