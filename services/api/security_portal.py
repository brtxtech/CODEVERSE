"""CODEVERSE authenticated portal, Supabase-backed immutable roles and sequential journey.

Production deployment REQUIRES Supabase asymmetric signing keys, configured RLS migrations,
trusted HTTPS frontend/origin and server-only Supabase service_role credential.
"""
from __future__ import annotations
import hmac
import json
import os
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, Header
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field, ConfigDict
from .identity import authenticated_user, authenticated_claims
from .github_client import collect_public_repositories, collect_public_repository, GithubCollectionError

try:
    from prometheus_client import Counter as PromCounter, generate_latest, CONTENT_TYPE_LATEST
    ACCESS_EVENTS = PromCounter('codeverse_access_events_total', 'CODEVERSE audited requests', ['role', 'action', 'outcome'])
    JOURNEY_EVENTS = PromCounter('codeverse_journey_events_total', 'CODEVERSE completed journey steps', ['step'])
except ImportError:  # metrics fail closed without deployment dependency
    ACCESS_EVENTS = JOURNEY_EVENTS = None
    generate_latest = None
    CONTENT_TYPE_LATEST = None

router = APIRouter(tags=['CODEVERSE Secure Portal'])
ROOT = Path(__file__).resolve().parents[2]
STAGES = ('cv', 'github', 'evidence', 'career', 'gaps', 'proof', 'readiness')
ALLOWED_ROLES = ('visitor', 'developer', 'recruiter', 'security_admin')
CAREERS = {
    'backend': 'Backend Software Engineer',
    'fullstack': 'Full-stack Engineer',
    'telecom': 'Telecom Software Engineer',
    'ml': 'AI / ML Engineer',
    'devops': 'Cloud / DevOps Engineer',
}
CAREER_LINKS = [
    {'company': 'Nokia', 'url': 'https://www.nokia.com/about-us/careers/', 'suggested_positions': ['Telecom Software Engineer', 'Backend Engineer']},
    {'company': 'Ericsson', 'url': 'https://www.ericsson.com/en/careers', 'suggested_positions': ['5G Core Developer', 'Cloud Engineer']},
    {'company': 'Orange', 'url': 'https://orange.jobs/', 'suggested_positions': ['Software Engineer', 'Network Engineer']},
    {'company': 'OVHcloud', 'url': 'https://careers.ovhcloud.com/', 'suggested_positions': ['Cloud Engineer', 'DevOps Engineer']},
]
GITHUB_RE = re.compile(r'^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$')


def configured() -> tuple[str, str]:
    if os.environ.get('CODEVERSE_DEV_BYPASS_AUTH') == '1':
        url = os.environ.get('SUPABASE_URL', 'https://example.supabase.co').rstrip('/')
        key = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', 'dev-bypass-service-role')
        if not os.environ.get('CODEVERSE_JWT_ISSUER'):
            os.environ.setdefault('CODEVERSE_JWT_ISSUER', 'https://example.supabase.co/auth/v1')
        return url, key
    url = os.environ.get('SUPABASE_URL', '').rstrip('/')
    key = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '')
    if not url.startswith('https://') or not key or not os.environ.get('CODEVERSE_JWT_ISSUER'):
        raise HTTPException(503, 'Supabase security is not configured; refusing insecure fallback')
    return url, key


class SupabaseStore:
    """Server-only PostgREST adapter. Never return service credential to frontend."""
    async def request(self, method: str, table: str, *, params: dict | None = None,
                      payload: dict | None = None, prefer: str | None = None) -> Any:
        url, key = configured()
        headers = {'apikey': key, 'Authorization': f'Bearer {key}'}
        if prefer:
            headers['Prefer'] = prefer
        async with httpx.AsyncClient(timeout=12) as client:
            try:
                r = await client.request(method, f'{url}/rest/v1/{table}', params=params,
                                         json=payload, headers=headers)
                r.raise_for_status()
            except (httpx.HTTPError, ValueError) as exc:
                raise HTTPException(503, 'Supabase unavailable or schema not migrated') from exc
        return r.json() if r.content else None

    async def profile(self, user: str) -> dict:
        rows = await self.request('GET', 'codeverse_profiles', params={
            'id': f'eq.{user}', 'select': 'id,role,display_name,email,university,github_username,created_at', 'limit': '1'})
        if not rows:
            raise HTTPException(403, 'No CODEVERSE profile; complete registration')
        profile = rows[0]
        if profile['role'] not in ALLOWED_ROLES:
            raise HTTPException(403, 'Unrecognized role')
        return profile

    async def steps(self, user: str) -> list[dict]:
        return await self.request('GET', 'codeverse_journey_steps', params={
            'user_id': f'eq.{user}', 'select': 'step,status,result,completed_at', 'order': 'step.asc'}) or []

    async def finalized(self, user: str) -> bool:
        rows = await self.request('GET', 'codeverse_journeys', params={
            'user_id': f'eq.{user}', 'select': 'submitted_at', 'limit': '1'})
        return bool(rows and rows[0]['submitted_at'])

    async def save_step(self, user: str, step: int, result: dict) -> None:
        await self.request('POST', 'codeverse_journey_steps', payload={
            'user_id': user, 'step': step, 'status': 'completed', 'result': result},
            prefer='resolution=merge-duplicates,return=minimal')

    async def submit(self, user: str) -> None:
        await self.request('POST', 'codeverse_journeys', payload={'user_id': user, 'submitted_at': datetime.now(timezone.utc).isoformat()},
                           prefer='resolution=merge-duplicates,return=minimal')

    async def audit(self, actor: str | None, role: str, action: str, outcome: str, detail: dict | None = None) -> None:
        if ACCESS_EVENTS is not None:
            ACCESS_EVENTS.labels(role=role, action=action, outcome=outcome).inc()
        # Never put raw tokens, CV contents, email, full IP or user agent in this log.
        try:
            await self.request('POST', 'codeverse_security_events', payload={
                'actor_id': actor, 'role': role, 'action': action, 'outcome': outcome,
                'detail': detail or {}}, prefer='return=minimal')
        except HTTPException:
            pass  # metric still records event; never break auth because of audit availability


store = SupabaseStore()


async def context(request: Request, user: str = Depends(authenticated_user)) -> dict:
    profile = await store.profile(user)
    if profile['role'] == 'security_admin' and os.environ.get('CODEVERSE_REQUIRE_ADMIN_MFA','1') == '1':
        claims = authenticated_claims(request.headers.get('authorization'))
        if claims.get('aal') != 'aal2':
            raise HTTPException(403, 'MFA_AAL2_REQUIRED: security administrators must verify a second factor')
    return {'user': user, 'profile': profile, 'role': profile['role']}


def allowed(*roles: str):
    async def dependency(ctx: dict = Depends(context)) -> dict:
        if ctx['role'] not in roles:
            await store.audit(ctx['user'], ctx['role'], 'role_access', 'denied', {'requested_roles': list(roles)})
            raise HTTPException(403, 'Access denied by server-side role policy')
        return ctx
    return dependency


def is_valid_github(value: str) -> str:
    value = value.strip().rstrip('/')
    if value.startswith('https://github.com/'):
        parsed = urlparse(value)
        if parsed.hostname != 'github.com' or parsed.query or parsed.fragment:
            raise HTTPException(422, 'Enter a GitHub profile URL without queries')
        username = parsed.path.strip('/')
    else:
        username = value
    if '/' in username or not GITHUB_RE.fullmatch(username):
        raise HTTPException(422, 'Enter a valid GitHub username')
    return username


def build_dossier(user: str, records: list[dict]) -> dict:
    """One file per user, rebuilt from stored journey steps so it never depends on local disk."""
    by = {int(r['step']): (r.get('result') or {}) for r in records}
    repos = by.get(2, {}).get('repositories', [])
    langs = {str(r.get('language')).lower() for r in repos if r.get('language')}
    techs = [{**t, 'seen_in_public_repositories': t['name'].lower() in langs} for t in by.get(1, {}).get('technologies', [])]
    backed = sum(1 for t in techs if t['seen_in_public_repositories'])
    career = by.get(4, {}).get('career')
    return {
        'schema': 'codeverse.user-file/1',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'user_id': user,
        'github_username': by.get(2, {}).get('username'),
        'career_target': {'id': career, 'title': CAREERS.get(career)} if career else None,
        'cv_technologies': {'count': len(techs), 'items': techs},
        'github': {'public_repositories': len(repos), 'repositories': repos},
        'evidence': {'technologies_seen_in_code': backed, 'cv_claims_only': len(techs) - backed,
                     'coverage_percent': round(100 * backed / len(techs)) if techs else 0,
                     'proof_repository': by.get(6, {}).get('repository'),
                     'proof_signals': by.get(6, {}).get('signals_found'),
                     'authorship_verified': False},
        'notes': ['CV technologies are claims until code evidence exists.',
                  'Coverage is not a hiring probability.',
                  'Repository presence is not proof of authorship.'],
    }


def dossier_csv(d: dict) -> str:
    import csv, io
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(['technology', 'category', 'seen_in_public_repositories'])
    for t in d['cv_technologies']['items']:
        w.writerow([t['name'], t['category'], 'yes' if t['seen_in_public_repositories'] else 'no'])
    return out.getvalue()


def write_user_file(user: str, dossier: dict) -> None:
    """Optional server copy: set CODEVERSE_EXPORT_DIR to a persistent volume."""
    base = os.environ.get('CODEVERSE_EXPORT_DIR')
    if not base or not re.fullmatch(r'[0-9a-fA-F-]{36}', user):
        return
    folder = Path(base) / user
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'codeverse-user-file.json').write_text(json.dumps(dossier, indent=2, ensure_ascii=False), encoding='utf-8')


@router.get('/start', include_in_schema=False)
async def start_page():
    return FileResponse(ROOT / 'apps/start/index.html', media_type='text/html')


def summarize_admin(events: list[dict], steps: list[dict], profiles: list[dict], journeys: list[dict]) -> dict:
    """Real aggregates for the admin console. No sample data: empty tables give zeros."""
    now = datetime.now(timezone.utc)
    buckets = {}
    for i in range(24):
        h = (now - timedelta(hours=23 - i)).replace(minute=0, second=0, microsecond=0)
        buckets[h] = {'hour': h.strftime('%H:00'), 'allowed': 0, 'denied': 0}
    denied_actions = Counter()
    for e in events:
        try:
            t = datetime.fromisoformat(str(e['created_at']).replace('Z', '+00:00')).replace(minute=0, second=0, microsecond=0)
        except (KeyError, ValueError):
            continue
        if t in buckets:
            buckets[t]['denied' if e.get('outcome') == 'denied' else 'allowed'] += 1
        if e.get('outcome') == 'denied':
            denied_actions[e.get('action', 'unknown')] += 1
    funnel = []
    for n in range(1, 8):
        funnel.append({'step': n, 'users': len({r['user_id'] for r in steps if r.get('step') == n and r.get('status') == 'completed'})})
    roles = Counter(r.get('role') for r in profiles)
    submitted = sum(1 for j in journeys if j.get('submitted_at'))
    devs = roles.get('developer', 0)
    return {'hourly': list(buckets.values()), 'top_denied': [{'action': a, 'count': c} for a, c in denied_actions.most_common(6)],
            'funnel': funnel, 'accounts': {'developers': devs, 'recruiters': roles.get('recruiter', 0), 'admins': roles.get('security_admin', 0)},
            'journeys_submitted': submitted, 'completion_percent': round(100 * submitted / devs) if devs else 0,
            'open_reviews': sum(1 for e in events if e.get('review_status') == 'open'), 'events_in_window': len(events),
            'denied_in_window': sum(1 for e in events if e.get('outcome') == 'denied')}


@router.get('/api/secure/admin/analytics')
async def admin_analytics(ctx: dict = Depends(allowed('security_admin'))):
    since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    events = await store.request('GET', 'codeverse_security_events', params={
        'select': 'created_at,action,outcome,role,review_status', 'created_at': f'gte.{since}', 'order': 'created_at.desc', 'limit': '5000'}) or []
    steps = await store.request('GET', 'codeverse_journey_steps', params={'select': 'user_id,step,status', 'limit': '20000'}) or []
    profiles = await store.request('GET', 'codeverse_profiles', params={'select': 'role', 'limit': '20000'}) or []
    journeys = await store.request('GET', 'codeverse_journeys', params={'select': 'submitted_at', 'limit': '20000'}) or []
    await store.audit(ctx['user'], ctx['role'], 'admin_analytics_view', 'allowed')
    data = summarize_admin(events, steps, profiles, journeys)
    data['generated_at'] = datetime.now(timezone.utc).isoformat()
    data['observability'] = {'grafana': os.environ.get('CODEVERSE_GRAFANA_URL') or None, 'prometheus': os.environ.get('CODEVERSE_PROMETHEUS_URL') or None}
    return data


@router.get('/admin', include_in_schema=False)
async def admin_page():
    return FileResponse(ROOT / 'apps/admin/index.html', media_type='text/html')


def current_index(steps: list[dict]) -> int:
    completed = {int(s['step']) for s in steps if s['status'] == 'completed'}
    return next((i for i in range(1, 8) if i not in completed), 8)


async def require_step(ctx: dict, step: int) -> list[dict]:
    if ctx['role'] != 'developer':
        raise HTTPException(403, 'Journey is only available to developer accounts')
    records = await store.steps(ctx['user'])
    next_step = current_index(records)
    if step != next_step:
        await store.audit(ctx['user'], ctx['role'], 'journey_out_of_order', 'denied',
                          {'requested_step': step, 'next_step': next_step})
        raise HTTPException(409, f'Complete step {next_step} before step {step}')
    return records


@router.get('/api/secure/config')
async def public_config():
    url, _ = configured()
    anon = os.environ.get('SUPABASE_ANON_KEY', '')
    if not anon:
        raise HTTPException(503, 'Missing Supabase public anon key')
    # This is a public browser key, NOT service_role.
    return {'supabase_url': url, 'supabase_anon_key': anon, 'oauth_redirect': os.environ.get('CODEVERSE_PUBLIC_URL', '').rstrip('/') + '/'}


@router.get('/secure', include_in_schema=False)
async def portal():
    return FileResponse(ROOT / 'apps/secure-portal/index.html', media_type='text/html')


@router.get('/api/secure/me')
async def me(ctx: dict = Depends(context)):
    steps = await store.steps(ctx['user']) if ctx['role'] == 'developer' else []
    submitted = await store.finalized(ctx['user']) if ctx['role'] == 'developer' else False
    return {'profile': ctx['profile'], 'steps': steps, 'next_step': current_index(steps),
            'submitted': submitted, 'can_view_jobs': bool(ctx['role'] == 'developer' and submitted),
            'available_roles': [ctx['role']]}


class ProfilePatch(BaseModel):
    model_config = ConfigDict(extra='forbid')
    display_name: str | None = Field(default=None, max_length=120)
    university: str | None = Field(default=None, max_length=160)
    github_username: str | None = Field(default=None, max_length=39)


@router.patch('/api/secure/profile')
async def profile_patch(body: ProfilePatch, ctx: dict = Depends(context)):
    changes = body.model_dump(exclude_unset=True)
    if 'github_username' in changes:
        raise HTTPException(403, 'GitHub username is managed by verified provider identity')
    if changes:
        await store.request('PATCH', 'codeverse_profiles', params={'id': f'eq.{ctx["user"]}'},
                            payload=changes, prefer='return=minimal')
    await store.audit(ctx['user'], ctx['role'], 'profile_update', 'allowed', {'fields': list(changes)})
    return {'ok': True, 'role_unchanged': ctx['role']}


@router.post('/api/secure/journey/cv')
async def journey_cv(file: UploadFile = File(...), ctx: dict = Depends(allowed('developer'))):
    await require_step(ctx, 1)
    # Reuse existing parser and never echo full document to audit stream.
    from .main import extract_cv
    result = await extract_cv(file)
    if not result.get('skills'):
        raise HTTPException(422, 'No technology evidence was detected; upload or review a different CV')
    await store.request('POST', 'cvs', payload={
        'user_id': ctx['user'], 'parsed': {'filename': (file.filename or '')[:160]},
        'result': result}, prefer='return=minimal')
    technologies = [{'name': str(x.get('name', ''))[:80], 'category': str(x.get('category') or x.get('group') or 'Other')[:60]}
                    for x in result['skills'] if x.get('name')]
    await store.save_step(ctx['user'], 1, {'skills_detected': len(technologies), 'technologies': technologies, 'source': 'cv_claims'})
    await store.audit(ctx['user'], ctx['role'], 'cv_processed', 'allowed')
    if JOURNEY_EVENTS is not None:
        JOURNEY_EVENTS.labels(step='1').inc()
    return {'status': 'completed', 'step': 1, 'skills_detected': len(technologies), 'technologies': technologies, 'next_step': 2}


class GitHubInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    github_username: str | None = Field(default=None, min_length=1, max_length=39)
    github_url: str | None = Field(default=None, min_length=3, max_length=160)  # legacy, prefer github_username


@router.post('/api/secure/journey/github')
async def journey_github(body: GitHubInput, ctx: dict = Depends(allowed('developer'))):
    await require_step(ctx, 2)
    raw = body.github_username or body.github_url
    if not raw:
        raise HTTPException(422, 'Enter your GitHub username')
    username = is_valid_github(raw)
    try:
        repos = await collect_public_repositories(username)
    except GithubCollectionError as exc:
        raise HTTPException(422, f'GitHub scan failed: {exc}') from exc
    # Collect function returns dict with repo collection in its data field.
    items = repos.get('repositories', []) if isinstance(repos, dict) else repos
    if not items:
        raise HTTPException(422, 'No public repositories found; connect or create a public repository first')
    repo_rows = [{'name': r.get('name'), 'full_name': r.get('full_name'), 'language': r.get('language'),
                  'size': r.get('size', 0), 'stars': r.get('stars', r.get('stargazers_count', 0)),
                  'pushed_at': r.get('pushed_at')} for r in items[:100]]
    await store.save_step(ctx['user'], 2, {'username': username, 'public_repos_found': len(items), 'repositories': repo_rows})
    await store.request('PATCH', 'codeverse_profiles', params={'id': f'eq.{ctx["user"]}'},
                        payload={'github_username': username}, prefer='return=minimal')
    await store.audit(ctx['user'], ctx['role'], 'github_public_scan', 'allowed', {'repo_count': len(items)})
    if JOURNEY_EVENTS is not None:
        JOURNEY_EVENTS.labels(step='2').inc()
    return {'status': 'completed', 'step': 2, 'username': username, 'public_repositories': len(items),
            'repositories': repo_rows, 'next_step': 3}


class JourneyAction(BaseModel):
    model_config = ConfigDict(extra='forbid')
    acknowledge: bool = False
    career: str | None = Field(default=None, max_length=35)
    repository: str | None = Field(default=None, max_length=190)


@router.post('/api/secure/journey/steps/{step}')
async def journey_action(step: int, body: JourneyAction, ctx: dict = Depends(allowed('developer'))):
    if step not in (3, 4, 5, 6, 7):
        raise HTTPException(404, 'Use CV or GitHub upload endpoint for steps 1 and 2')
    previous = await require_step(ctx, step)
    result: dict[str, Any]
    if step == 3:
        if not body.acknowledge:
            raise HTTPException(422, 'Review evidence and explicitly acknowledge its limitations')
        result = {'reviewed': True, 'verification_note': 'Repository presence is not proof of authorship'}
    elif step == 4:
        if body.career not in CAREERS:
            raise HTTPException(422, 'Choose an existing career profile')
        result = {'career': body.career, 'title': CAREERS[body.career]}
    elif step == 5:
        if not body.acknowledge:
            raise HTTPException(422, 'Review your requirement gaps before continuing')
        result = {'gaps_reviewed': True}
    elif step == 6:
        repo = (body.repository or '').strip()
        if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo):
            raise HTTPException(422, 'Provide an owner/repository GitHub reference')
        try:
            scanned = await collect_public_repository(*repo.split('/'))
        except GithubCollectionError as exc:
            raise HTTPException(422, f'Repository proof could not be scanned: {exc}') from exc
        evidence = scanned.get('evidence') or []
        if not evidence:
            raise HTTPException(422, 'No supported technology manifest evidence was found')
        result = {'repository': repo, 'signals_found': len(evidence),
                  'proof_status': 'repository_signals_only', 'authorship_verified': False}
    else:
        if not body.acknowledge:
            raise HTTPException(422, 'Review the readiness interpretation before continuing')
        result = {'readiness_reviewed': True, 'score_is_hiring_probability': False}
    await store.save_step(ctx['user'], step, result)
    await store.audit(ctx['user'], ctx['role'], 'journey_step', 'allowed', {'step': step})
    if JOURNEY_EVENTS is not None:
        JOURNEY_EVENTS.labels(step=str(step)).inc()
    return {'status': 'completed', 'step': step, 'next_step': step + 1, 'result': result}


@router.post('/api/secure/journey/submit')
async def submit_journey(ctx: dict = Depends(allowed('developer'))):
    records = await store.steps(ctx['user'])
    if current_index(records) != 8:
        raise HTTPException(409, 'All seven stages must be completed before submission')
    await store.submit(ctx['user'])
    await store.audit(ctx['user'], ctx['role'], 'journey_submitted', 'allowed')
    dossier = build_dossier(ctx['user'], records)
    write_user_file(ctx['user'], dossier)
    return {'submitted': True, 'jobs_unlocked': True, 'file': '/api/secure/journey/file'}


@router.get('/api/secure/journey/options')
async def journey_options(ctx: dict = Depends(allowed('developer'))):
    return {'careers': [{'id': k, 'title': v} for k, v in CAREERS.items()]}


@router.get('/api/secure/journey/file')
async def journey_file(format: str = Query('json', pattern='^(json|csv)$'), ctx: dict = Depends(allowed('developer'))):
    if not await store.finalized(ctx['user']):
        raise HTTPException(409, 'Submit the journey to generate your file')
    dossier = build_dossier(ctx['user'], await store.steps(ctx['user']))
    name = f"codeverse-{dossier['github_username'] or 'profile'}"
    await store.audit(ctx['user'], ctx['role'], 'user_file_download', 'allowed', {'format': format})
    if format == 'csv':
        return Response(dossier_csv(dossier), media_type='text/csv; charset=utf-8',
                        headers={'Content-Disposition': f'attachment; filename="{name}.csv"'})
    return Response(json.dumps(dossier, indent=2, ensure_ascii=False), media_type='application/json',
                    headers={'Content-Disposition': f'attachment; filename="{name}.json"'})


@router.get('/api/secure/jobs')
async def jobs(ctx: dict = Depends(allowed('developer'))):
    if not await store.finalized(ctx['user']):
        await store.audit(ctx['user'], ctx['role'], 'jobs_view', 'denied', {'reason': 'journey_incomplete'})
        raise HTTPException(403, 'Submit all seven journey stages to unlock Job Opportunities')
    await store.audit(ctx['user'], ctx['role'], 'jobs_view', 'allowed')
    return {'employment_listings_verified': False,
            'note': 'Company career portals and role suggestions only; not verified live vacancies.',
            'companies': CAREER_LINKS}


@router.get('/api/secure/recruiter')
async def recruiter(ctx: dict = Depends(allowed('recruiter'))):
    return {'consented_candidates': [], 'note': 'No candidates shared. Recruiter data requires explicit consent.'}


@router.get('/api/secure/admin/events')
async def admin_events(limit: int = Query(50, ge=1, le=100), ctx: dict = Depends(allowed('security_admin'))):
    rows = await store.request('GET', 'codeverse_security_events', params={
        'select': 'id,created_at,actor_id,role,action,outcome,detail,review_status',
        'order': 'created_at.desc', 'limit': str(limit)})
    await store.audit(ctx['user'], ctx['role'], 'admin_events_view', 'allowed')
    return {'events': rows or [], 'scope': 'API authorization and journey events; not full Supabase Auth login logs'}


@router.get('/api/secure/admin/overview')
async def admin_overview(ctx: dict = Depends(allowed('security_admin'))):
    rows = await store.request('GET', 'codeverse_security_events', params={
        'select': 'action,outcome,role,review_status', 'order': 'created_at.desc', 'limit': '500'})
    counts = Counter(r['outcome'] for r in (rows or []))
    return {'events_sampled': len(rows or []), 'by_outcome': dict(counts),
            'pending_review': sum(r.get('review_status') == 'open' for r in rows or []),
            'source': 'codeverse_security_events; latest 500 records'}


class EventResolution(BaseModel):
    model_config = ConfigDict(extra='forbid')
    status: str = Field(pattern='^(investigating|closed)$')
    reason: str = Field(min_length=5, max_length=500)


@router.post('/api/secure/admin/events/{event_id}/review')
async def review_event(event_id: str, body: EventResolution,
                       ctx: dict = Depends(allowed('security_admin'))):
    if not re.fullmatch(r'[0-9a-fA-F-]{36}', event_id):
        raise HTTPException(422, 'Invalid event ID')
    await store.request('PATCH', 'codeverse_security_events', params={'id': f'eq.{event_id}'},
                        payload={'review_status': body.status, 'reviewed_by': ctx['user'],
                                 'review_note': body.reason[:500]}, prefer='return=minimal')
    await store.audit(ctx['user'], ctx['role'], 'security_event_review', 'allowed',
                      {'event_id': event_id, 'new_status': body.status})
    return {'ok': True, 'status': body.status}


@router.get('/internal/metrics')
async def metrics(authorization: str | None = Header(default=None)):
    secret = os.environ.get('CODEVERSE_METRICS_TOKEN', '')
    secret_file = os.environ.get('CODEVERSE_METRICS_TOKEN_FILE', '')
    if secret_file:
        try:
            secret = Path(secret_file).read_text().strip()
        except OSError:
            secret = ''
    if not secret or not authorization or not hmac.compare_digest(authorization, 'Bearer ' + secret):
        raise HTTPException(404, 'Not found')
    if generate_latest is None:
        raise HTTPException(503, 'Prometheus client unavailable')
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
