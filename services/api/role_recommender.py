"""Curated career archetypes. These are NOT live vacancies or hiring predictions."""
from .core import normalize_skill
PROFILES=[
 ('backend','Backend Software Engineer',['python','fastapi','django','flask','postgresql','docker','rest-api']),
 ('fullstack','Full-Stack Engineer',['typescript','javascript','react','angular','nodejs','expressjs','postgresql']),
 ('ai-ml','AI / ML Engineer',['python','pytorch','tensorflow','scikit-learn','docker','transformers']),
 ('llm','LLM Application Engineer',['python','llm','rag','transformers','fastapi','docker']),
 ('telecom','Telecom Software Engineer',['5g','5g-core','python','c','cpp','docker','prometheus']),
 ('network','Network Automation Engineer',['5g','python','bgp','ospf','sdn','docker']),
 ('devops','DevOps Engineer',['docker','kubernetes','helm','jenkins','github-actions','prometheus']),
 ('data','Data Engineer',['python','pandas','sql','postgresql','apache-spark','airflow']),
 ('security','Security Engineer',['python','tls','oauth2','jwt','docker','kubernetes']),
 ('research','AI Research Engineer',['python','pytorch','transformers','llm','rag','jupyter']),
]

def recommend_roles(skills,github_evidence=None,limit=8):
    owned={normalize_skill(s) for s in skills};source={normalize_skill(x.get('skill','')) for x in github_evidence or []}
    ranked=[]
    for slug,title,required in PROFILES:
        required=list(dict.fromkeys(required))
        matched=[s for s in required if s in owned or s in source]
        missing=[s for s in required if s not in owned and s not in source]
        supported=[s for s in matched if s in source]
        # ranking aids discovery, NOT assessment/hiring score
        coverage=round(100*len(matched)/len(required),1)
        ranked.append({'id':slug,'title':title,'requirements':[{'skill':s,'weight':1,'required_level':2} for s in required],
            'matched_skills':matched,'missing_skills':missing,'github_supported_skills':supported,
            'match_percent':coverage,'why_recommended':f'{len(matched)} of {len(required)} curated role technologies appear in the CV or scanned GitHub manifests.',
            'source':'CODEVERSE curated example profile; not a live employer vacancy'})
    return sorted(ranked,key=lambda x:(-x['match_percent'],-len(x['github_supported_skills']),x['title']))[:limit]

def skill_evidence_from_claims_and_repos(claims,repositories):
    mapped={}
    for skill in claims:
        ident=normalize_skill(skill.get('id',skill.get('skill','')))
        if not ident:continue
        mapped[ident]={**skill,'id':ident,'github_evidence':[],
            'verification_status':'cv_claim_only','confidence_reason':'CV claim. GitHub analysis not completed or no matching evidence observed.'}
    for repo in repositories:
        for evidence in repo.get('evidence',[]):
            ident=normalize_skill(evidence.get('skill',''))
            if not ident:continue
            if ident not in mapped:
                mapped[ident]={'id':ident,'name':ident,'category':'Repository detected','evidence':[],
                    'source':'github','github_evidence':[]}
            mapped[ident]['github_evidence'].append({**evidence,'repo':repo.get('repository',evidence.get('repo'))})
            mapped[ident]['verification_status']='repository_detected'
            mapped[ident]['confidence_reason']='Static repository manifest/configuration detected. Authorship has not been verified.'
    return sorted(mapped.values(),key=lambda x:x.get('name',x['id']).casefold())
