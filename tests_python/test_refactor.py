"""Regression tests for real issues reported from the previous CV prototype."""
from io import BytesIO
from fastapi.testclient import TestClient
from docx import Document
from services.api.main import app,normalize_spaced_pdf_text
from services.api.core import extract_skills_with_sources
from services.api.role_recommender import recommend_roles,skill_evidence_from_claims_and_repos

client=TestClient(app)

def test_telecom_detection_with_sources():
    skills=extract_skills_with_sources([{'page':2,'document':'cv.pdf','text':'Built a 5G Core monitor using Python; studying 6G research.'}])
    by={s['id']:s for s in skills}
    assert {'5g-core','6g','python'} <= by.keys()
    assert by['6g']['evidence'][0]['page']==2
    assert '6G' in by['6g']['evidence'][0]['excerpt']
    assert by['6g']['confidence'] is None

def test_6g_is_not_inferred_from_5g():
    ids={s['id'] for s in extract_skills_with_sources([{'page':1,'text':'Worked with 5G, free5GC and Open5GS'}])}
    assert '5g' in ids and '6g' not in ids

def test_angularjs_does_not_implicate_modern_angular():
    ids={s['id'] for s in extract_skills_with_sources([{'text':'AngularJS is used here, JavaScript too.'}])}
    assert 'angularjs' in ids and 'angular' not in ids and 'java' not in ids

def test_page_by_page_docx_with_tables():
    doc=Document();doc.add_paragraph('Developer portfolio')
    table=doc.add_table(rows=1,cols=2);table.cell(0,0).text='Cloud';table.cell(0,1).text='Kubernetes and Docker'
    b=BytesIO();doc.save(b)
    r=client.post('/api/cv/extract',files={'file':('skills.docx',b.getvalue(),'application/vnd.openxmlformats-officedocument.wordprocessingml.document')})
    assert r.status_code==200
    ids={x['id'] for x in r.json()['skills']}
    assert {'docker','kubernetes'} <= ids

def test_pdf_character_spacing_normalization():
    text,changed=normalize_spaced_pdf_text('I  u s e  P y t h o n  a n d  5 G  n e t w o r k s')
    assert changed and 'Python' in text and '5G' in text

def test_no_unsupported_proof_promotion():
    result=skill_evidence_from_claims_and_repos([{'id':'angular','name':'Angular','evidence':[{'excerpt':'Angular'}]}],[])
    assert result[0]['verification_status']=='cv_claim_only'
    assert 'not completed' in result[0]['confidence_reason'].lower()

def test_role_recommendations_without_manual_job_description():
    roles=recommend_roles(['5g','5g-core','python','pytorch','llm','docker'])
    assert roles and any('Telecom' in x['title'] or 'AI' in x['title'] for x in roles)
    assert all('requirements' in x and 'why_recommended' in x for x in roles)

def test_new_routes_and_navigation():
    assert client.post('/api/jobs/profiles/recommended',json={'skills':['5g','python']}).status_code==200
    html=client.get('/studio').text
    for name in ('GitHub Repositories','Career Explorer','Pipeline Studio','Skills & Evidence','data-skill'):
        assert name in html
