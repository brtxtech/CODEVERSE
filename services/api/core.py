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
 'cpp':['C++','cpp','cplusplus'], 'csharp':['C#','csharp','c-sharp'],
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
    special={'c':'c','c++':'cpp','cplusplus':'cpp','cpp':'cpp','c#':'csharp','csharp':'csharp','c-sharp':'csharp'}
    if name.strip().casefold() in special:return special[name.strip().casefold()]
    key=re.sub(r'[^a-z0-9]+','-',name.casefold()).strip('-')
    for ident, aliases in ALIASES.items():
        if key == ident or any(re.sub(r'[^a-z0-9]+','-',a.casefold()).strip('-')==key for a in aliases):return ident
    return key

# Typed aliases intentionally distinguish 5G from free5GC, AngularJS from Angular,
# and Java from JavaScript. The matched source is always returned.
EXTRA_ALIASES = {
 '5g': ['5G networks', '5G network', '5G technology', '5G', '5 G'],
 '5g-core': ['5G Core', '5 G Core', '5GC', '5G core architecture'],
 '5g-nr': ['5G NR', '5G New Radio', '5 G NR'], '6g':['6G', '6 G', '6G networks'],
 'telecom-monitoring': ['network monitoring', 'telecom monitoring'],
 'network-anomaly-detection':['network anomaly detection', 'anomaly detection'],
 'angularjs':['AngularJS','Angular.js'], 'angular':['Angular','@angular/core'],
 'ci-cd':['CI/CD'], 'llm':['LLM','LLMs','large language models'],
 'rag':['RAG','retrieval augmented generation'],
}

def _skill_patterns(skill):
    tid=skill['id']; names=[skill['name']]+ALIASES.get(tid,[])+EXTRA_ALIASES.get(tid,[])
    for name in dict.fromkeys(names):
        if name=='C':
            yield name,re.compile(r'(?<![\w+#])C(?![\w+#])')
            continue
        if len(name)<2: continue
        # Explicit, conservative boundaries; prevent framework names matching suffixes.
        yield name,re.compile(r'(?<![\w])'+re.escape(name)+r'(?![\w])', re.I)

def extract_skills_with_sources(pages:list[dict])->list[dict]:
    '''Find CV claims and exact excerpts, preserving page provenance.'''
    found={}
    for pg in pages:
        text=str(pg.get('text') or '')[:150_000]
        # Collect matches longest first to prevent subordinate overlap
        candidates=[]
        for t in TECH:
            for alias,regex in _skill_patterns(t):
                for m in regex.finditer(text): candidates.append((m.start(),m.end(),t,alias))
        candidates.sort(key=lambda x:(-(x[1]-x[0]),x[0]))
        claimed=[]
        for st,en,t,alias in candidates:
            if any(not (en<=a or st>=b) for a,b in claimed):continue
            claimed.append((st,en))
            tid=t['id']
            row=found.setdefault(tid,{'id':tid,'name':t['name'],'category':t['category'],
                 'source':'cv_claim','status':'cv_claim_only','verification_status':'cv_claim_only',
                 'confidence':None,'confidence_reason':'CV statement only; GitHub verification not completed.',
                 'evidence':[],'github_evidence':[]})
            snippet=text[max(0,st-65):min(len(text),en+80)].replace('\n',' ').strip()
            source={'type':'cv','page':pg.get('page'),'section':pg.get('section'),
                'excerpt':snippet,'start_offset':st,'end_offset':en,
                'method':'taxonomy_exact_match','document':pg.get('document')}
            if not any(e['excerpt']==snippet and e['page']==source['page'] for e in row['evidence']):row['evidence'].append(source)
    return sorted(found.values(),key=lambda x:x['name'].casefold())

def extract_skills(text:str)->list[dict]:
    '''Backward compatible extraction API with CV references.'''
    return extract_skills_with_sources([{'text':text,'page':None,'document':None}])

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
