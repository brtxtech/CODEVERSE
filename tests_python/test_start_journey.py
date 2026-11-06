from fastapi.testclient import TestClient
from services.api.main import app
from services.api.security_portal import build_dossier, dossier_csv, GitHubInput, is_valid_github


def steps(n_tech=45):
    techs = [{'name': f'Tech{i}', 'category': 'Backend' if i % 2 else 'Frontend'} for i in range(n_tech)]
    techs[0] = {'name': 'Python', 'category': 'Languages'}
    return [
        {'step': 1, 'result': {'technologies': techs}},
        {'step': 2, 'result': {'username': 'octocat', 'repositories': [{'name': 'a', 'language': 'Python'}]}},
        {'step': 4, 'result': {'career': 'backend'}},
    ]


def test_dossier_keeps_every_technology_and_marks_evidence():
    d = build_dossier('u', steps(45))
    assert d['cv_technologies']['count'] == 45  # no 30-item cap
    assert d['evidence']['technologies_seen_in_code'] == 1
    assert d['github_username'] == 'octocat'
    assert d['career_target']['title'] == 'Backend Software Engineer'
    assert d['evidence']['authorship_verified'] is False


def test_csv_lists_all_rows():
    csv_text = dossier_csv(build_dossier('u', steps(45)))
    assert len(csv_text.strip().splitlines()) == 46


def test_github_accepts_bare_username_only():
    assert is_valid_github('octocat') == 'octocat'
    assert GitHubInput(github_username='octocat').github_username == 'octocat'


def test_start_page_served_and_demo_removed():
    c = TestClient(app)
    r = c.get('/start')
    assert r.status_code == 200 and 'CODEVERSE' in r.text and 'three@0.160.0' in r.text
    assert c.get('/career-journey').status_code == 404


def test_admin_summary_is_real_and_empty_safe():
    from datetime import datetime, timezone
    from services.api.security_portal import summarize_admin
    empty = summarize_admin([], [], [], [])
    assert empty['events_in_window'] == 0 and empty['completion_percent'] == 0 and len(empty['hourly']) == 24
    now = datetime.now(timezone.utc).isoformat()
    ev = [{'created_at': now, 'action': 'role_access', 'outcome': 'denied', 'review_status': 'open'},
          {'created_at': now, 'action': 'cv_processed', 'outcome': 'allowed'}]
    st = [{'user_id': 'a', 'step': 1, 'status': 'completed'}, {'user_id': 'b', 'step': 1, 'status': 'completed'}, {'user_id': 'a', 'step': 2, 'status': 'completed'}]
    d = summarize_admin(ev, st, [{'role': 'developer'}, {'role': 'developer'}, {'role': 'security_admin'}], [{'submitted_at': now}, {'submitted_at': None}])
    assert d['denied_in_window'] == 1 and d['open_reviews'] == 1
    assert d['funnel'][0]['users'] == 2 and d['funnel'][1]['users'] == 1
    assert d['completion_percent'] == 50 and d['top_denied'][0]['action'] == 'role_access'


def test_admin_page_served_and_has_no_demo_labels():
    r = TestClient(app).get('/admin')
    assert r.status_code == 200 and 'Security console' in r.text
    assert 'DEMO' not in r.text.upper().replace('DEMONSTR', '')
