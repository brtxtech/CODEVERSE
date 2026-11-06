import io
from pathlib import Path
from fastapi.testclient import TestClient
from services.api.core import extract_skills, readiness, evidence_from_github, verify_challenge
from services.api.main import app
client=TestClient(app)

def test_taxonomy_detection():
    r=extract_skills('I built a Flask backend using Python, Docker and PostgreSQL')
    ids={x['id'] for x in r}
    assert 'flask' in ids and 'python' in ids and 'docker' in ids

def test_score_is_deterministic():
    req=[{'skill':'docker','weight':2,'required_level':2},{'skill':'kubernetes','weight':1,'required_level':2}]
    ev=[{'skill':'docker','level':2,'confidence':.8,'freshness':1}]
    a=readiness(req,ev);b=readiness(req,ev)
    assert a==b and a['score']>0 and a['score']<70

def test_project_verification_requires_review():
    result=verify_challenge(['tests','ci-workflow'],['tests','ci-workflow'])
    assert result['ready_for_review'] and not result['verified']

def test_verified_milestone_raises_score():
    req=[{'skill':'python','weight':1,'required_level':2}]
    ev=[{'skill':'python','level':2,'confidence':.8}]
    baseline=readiness(req,ev,[{'verified':False}])
    upgraded=readiness(req,ev,[{'verified':True}])
    assert round(upgraded['score']-baseline['score'])==20

def test_static_evidence_no_execution():
    result=evidence_from_github({'full_name':'demo/project','sha':'abcdef'}, {'requirements.txt':'fastapi==0.115\n','Dockerfile':'FROM python:3.12'})
    assert {'fastapi','docker'} <= {e['skill'] for e in result}
    assert all(e['confidence'] < 1 for e in result)

def test_api_end_to_end():
    extracted=client.post('/api/cv/extract',files={'file':('cv.txt',b'Python and FastAPI and Docker','text/plain')})
    assert extracted.status_code==200
    assert extracted.json()['stored'] is False
    parsed=client.post('/api/jobs/parse',json={'text':'Backend Engineer: Python, FastAPI, Docker, Kubernetes and PostgreSQL required.'})
    assert parsed.status_code==200
    payload={'requirements':parsed.json()['requirements'],'evidence':[{'skill':x['id'],'level':2,'confidence':.35} for x in extracted.json()['skills']]}
    scored=client.post('/api/readiness/evaluate',json=payload)
    assert scored.status_code==200 and scored.json()['recommendations']

def test_invalid_cv_rejected():
    assert client.post('/api/cv/extract',files={'file':('cv.exe',b'bad','application/octet-stream')}).status_code==415
    assert client.post('/api/cv/extract',files={'file':('bad.pdf',b'not a pdf','application/pdf')}).status_code==422

def test_health_discloses_local_demo():
    r=client.get('/api/health').json();assert r['production_ready'] is False

def test_studio_available():
    r=client.get('/studio');assert r.status_code==200 and 'Career readiness' in r.text

def test_schema_rejects_unbounded_evidence():
    data={'requirements':[{'skill':'python'}],'evidence':[{'skill':'python','level':8,'confidence':1}]}
    assert client.post('/api/readiness/evaluate',json=data).status_code==422

def test_github_repository_validation():
    assert client.post('/api/github/public-scan',json={'repository':'https://attacker.test/foo'}).status_code==422

def test_taxonomy_endpoint():
    result=client.get('/api/taxonomy?search=Flask').json()
    assert result['count']>=250 and any(t['name']=='Flask' for t in result['results'])
