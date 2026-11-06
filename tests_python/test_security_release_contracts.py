"""Static release contracts to prevent accidental loss of access controls."""
import json
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]

def test_grafana_dashboard_has_prometheus_metrics():
    d=json.loads((ROOT/'ops/grafana/dashboards/codeverse-security.json').read_text())
    assert d['uid']=='codeverse-security'
    assert len(d['panels'])>=7
    assert all(p['datasource']['uid']=='codeverse-prometheus' for p in d['panels'])


def test_role_signup_and_rls_contract():
    s=(ROOT/'supabase/migrations/20261101000000_codeverse_security.sql').read_text()
    assert "requested = 'recruiter'" in s
    assert "'security_admin'" in s
    assert 'revoke all on public.codeverse_security_events from anon, authenticated;' in s
    assert 'for select to authenticated' in s
    assert 'for update to authenticated' not in s
    assert 'codeverse_journey_steps' in s


def test_metric_endpoint_is_bearer_authenticated():
    s=(ROOT/'services/api/security_portal.py').read_text()
    assert 'compare_digest' in s
    assert "CODEVERSE_METRICS_TOKEN_FILE" in s
    assert "CODEVERSE_REQUIRE_ADMIN_MFA" in s


def test_secure_frontend_no_role_switching():
    s=(ROOT/'apps/secure-portal/index.html').read_text()
    assert 'signupRole' in s
    assert 'security_admin' not in s[s.index('id="signupRole"'):s.index('</select>',s.index('id="signupRole"'))]
    assert 'Submit completed journey' in s
    assert 'Role locked' in s
    assert 'send-only' not in s.lower() or 'Gmail' in s
