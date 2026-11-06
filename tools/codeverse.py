#!/usr/bin/env python3
"""CODEVERSE local operations CLI. Safe-by-default; NEVER uploads credentials."""
from __future__ import annotations
import argparse, datetime as dt, hashlib, json, os, re, shutil, subprocess, sys, tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MIGRATIONS=ROOT/'supabase'/'migrations'
REQ=ROOT/'services'/'api'/'requirements.txt'
KEY_NAMES=('SUPABASE_SERVICE_ROLE_KEY','SUPABASE_SECRET_KEY','GITHUB_APP_PRIVATE_KEY','GITHUB_CLIENT_SECRET','DATABASE_URL','SUPABASE_DB_PASSWORD')
TRACK=[
 ('supabase','Supabase production migrations and real DB RLS validation','external'),
 ('github','GitHub App OAuth and installation-scoped sync','external'),
 ('webhooks','Signed GitHub webhooks with automatic sync','external'),
 ('postgres','FastAPI production PostgreSQL persistence','external'),
 ('evidence','Authorship-attributed code-based Skill Evidence Graph','partial'),
 ('verification','Automated trusted project verification and rescoring','external'),
 ('cv','CV parser benchmark against labeled real samples','partial'),
 ('jobs','Real job provider quality / freshness benchmark','partial'),
 ('matching','Embedding and pgvector semantic matching','external'),
 ('scoring','Calibration against independently labeled job requirements','partial'),
 ('pipeline','Full CV to verified project journey','partial'),
 ('city','Authenticated live evidence connected to 3D buildings','external'),
 ('node_ui','Fully connected pipeline graph and CSV outputs','partial'),
 ('ux','Single responsive authenticated application','partial'),
 ('privacy','GDPR operational and legal review','external'),
 ('production','Browser E2E, hardening, monitoring and deployment','external'),
 ('pilot','20 real-user validated journeys','external')]

def run(cmd, *, cwd=ROOT, timeout=150, env=None):
    try:
        p=subprocess.run(cmd,cwd=cwd,text=True,capture_output=True,timeout=timeout,env=env)
        return {'ok':p.returncode==0,'exit_code':p.returncode,'output':(p.stdout+'\n'+p.stderr)[-4500:].strip()}
    except (OSError, subprocess.TimeoutExpired) as e:
        return {'ok':False,'exit_code':None,'output':str(e)}

def binaries():
    out={}
    for name in ('python3','node','npm','supabase','psql'):
        path=shutil.which(name)
        if not path:out[name]={'installed':False}
        else:
            version=run([path,'--version'],timeout=10)
            out[name]={'installed':True,'version':version['output'].split('\n')[0][:120]}
    return out

def env_report():
    """Only booleans; never return secret contents or URLs."""
    return {key:bool(os.environ.get(key)) for key in (
        'SUPABASE_URL','SUPABASE_PUBLISHABLE_KEY','SUPABASE_PROJECT_REF',
        'SUPABASE_ACCESS_TOKEN','GITHUB_APP_ID','GITHUB_APP_PRIVATE_KEY_FILE',
        'GITHUB_WEBHOOK_SECRET','GITHUB_OAUTH_CLIENT_ID','GITHUB_OAUTH_CLIENT_SECRET',
        'GITHUB_CALLBACK_URL','DATABASE_URL','CODEVERSE_LEDGER_DB')}

def migration_checks():
    paths=sorted(MIGRATIONS.glob('*.sql'))
    problems=[]; hashes=[]
    for path in paths:
        raw=path.read_bytes()
        hashes.append({'name':path.name,'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)})
        if b'alter table' not in raw.lower() and b'create table' not in raw.lower() and b'create policy' not in raw.lower():
            problems.append(path.name+': no DDL statements found; inspect manually')
    evidence=(MIGRATIONS/'20261031000000_evidence_graph.sql')
    if evidence.exists():
        sql=evidence.read_text().lower()
        for token in ['enable row level security','auth.uid()','revoke insert,update,delete on public.skill_evidence']:
            if token not in sql:problems.append('Evidence migration missing expected guard: '+token)
    else:problems.append('Evidence graph migration missing')
    return {'found':len(paths),'files':hashes,'static_findings':problems,'live_rls_verified':False}

def prerequisites():
    report={'timestamp_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'mode':'local_only',
       'tools':binaries(),'env_present':env_report(),'migrations':migration_checks()}
    return report

def safe_report():
    pre=prerequisites()
    outputs={'preflight':pre,'capabilities':[],'tests':{}}
    for key,description,status in TRACK:
        outputs['capabilities'].append({'id':key,'task':description,'baseline':status,'validated':False})
    return outputs

def write_report(report,path):
    dest=Path(path).expanduser().resolve()
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    print(f'Report saved to {dest}')

def cmd_doctor(args):
    r=prerequisites()
    print('CODEVERSE local preflight (no credentials displayed)')
    for k,v in r['tools'].items():print(f'  {k:12} {v.get("version","MISSING") if v["installed"] else "MISSING"}')
    print('  SQL migrations:',r['migrations']['found'],'static findings:',len(r['migrations']['static_findings']))
    print('  Supabase project configured:',r['env_present']['SUPABASE_PROJECT_REF'])
    print('  PostgreSQL URL configured:',r['env_present']['DATABASE_URL'])
    print('  GitHub app configured:',r['env_present']['GITHUB_APP_ID'])
    if args.output:write_report(r,args.output)

def cmd_test(args):
    tests={}
    if shutil.which('python3'):
        py=sys.executable
        tests['python']=run([py,'-m','pytest','-q','tests_python','tests_ops'],timeout=180)
    if shutil.which('npm'):tests['javascript']=run(['npm','test'],timeout=90)
    if args.browser:
        if (ROOT/'node_modules'/'vite').exists() and shutil.which('npm'):
            tests['vite_build']=run(['npm','run','build'],timeout=120)
        else:tests['vite_build']={'ok':False,'output':'Dependencies not installed. Run npm install first.'}
    for name,result in tests.items():
        print(f'{name}: {"PASS" if result["ok"] else "NOT PASSED"}')
        print(result['output'][-1200:])
    if args.output:write_report(tests,args.output)
    if any(not v['ok'] for v in tests.values()):raise SystemExit(1)

def cmd_migrate(args):
    """Explicit opt-in migration: no DB writes unless confirmed by operator."""
    if args.mode=='local':
        if not shutil.which('supabase'):raise SystemExit('Supabase CLI missing: install it, then run again.')
        cmd=['supabase','db','reset','--local'] if args.reset else ['supabase','migration','list','--local']
        if args.reset and not args.confirm_data_loss:raise SystemExit('Local database reset destroys data: pass --confirm-data-loss')
        res=run(cmd,timeout=240);print(res['output'])
        if not res['ok']:raise SystemExit(1)
    else:
        if not args.confirm_remote:raise SystemExit('Remote changes blocked. Pass --confirm-remote after reviewing migrations and backup.')
        if not os.getenv('SUPABASE_PROJECT_REF'):raise SystemExit('SUPABASE_PROJECT_REF environment variable missing')
        if not shutil.which('supabase'):raise SystemExit('Supabase CLI missing')
        print('This will run `supabase db push` on linked Supabase project; no keys are printed.')
        if not args.yes:
            reply=input('Type DEPLOY to proceed: ')
            if reply!='DEPLOY':raise SystemExit('Cancelled')
        res=run(['supabase','db','push','--linked'],timeout=240)
        print(res['output']);
        if not res['ok']:raise SystemExit(1)
        print('Migrations pushed; live RLS is NOT validated until two-user ownership tests are executed.')

def cmd_rls(args):
    """Runs a read-only database inspection; not a substitute for two-user RLS tests."""
    if not shutil.which('psql'):raise SystemExit('psql missing')
    if not os.getenv('DATABASE_URL'):raise SystemExit('DATABASE_URL missing (set locally, never commit)')
    sql="""SELECT n.nspname||'.'||c.relname AS table_name, c.relrowsecurity AS rls_enabled,
      c.relforcerowsecurity AS rls_forced, count(p.polname) AS policy_count
      FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
      LEFT JOIN pg_policy p ON p.polrelid=c.oid
      WHERE n.nspname='public' AND c.relkind='r'
      GROUP BY n.nspname,c.relname,c.relrowsecurity,c.relforcerowsecurity
      ORDER BY 1;"""
    # PGPASSWORD/DATABASE_URL inherited through env only; never printed.
    res=run(['psql','-X','-v','ON_ERROR_STOP=1','-c',sql],timeout=30)
    print(res['output'])
    if not res['ok']:raise SystemExit(1)
    print('Warning: metadata-only inspection; real tenant isolation must be tested with separate authenticated identities.')

def cmd_pilot(args):
    cmd=[sys.executable,'-m','pilot.metrics',args.input,'--output',args.output]
    res=run(cmd);print(res['output'])
    if not res['ok']:raise SystemExit(1)

def cmd_status(args):
    report=safe_report()
    if args.with_tests:
        report['tests']['python']=run([sys.executable,'-m','pytest','-q','tests_python','tests_ops'],timeout=120)
        if shutil.which('npm'):report['tests']['javascript']=run(['npm','test'],timeout=90)
    write_report(report,args.output)
    print('No task was marked complete without connected production validation.')

def main(argv=None):
    parser=argparse.ArgumentParser(description='CODEVERSE local deployment & readiness manager')
    sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('doctor');p.add_argument('--output');p.set_defaults(func=cmd_doctor)
    p=sub.add_parser('test');p.add_argument('--browser',action='store_true');p.add_argument('--output');p.set_defaults(func=cmd_test)
    p=sub.add_parser('migrate');p.add_argument('--mode',choices=['local','remote'],required=True);p.add_argument('--reset',action='store_true');p.add_argument('--confirm-data-loss',action='store_true');p.add_argument('--confirm-remote',action='store_true');p.add_argument('--yes',action='store_true');p.set_defaults(func=cmd_migrate)
    p=sub.add_parser('rls-inspect');p.set_defaults(func=cmd_rls)
    p=sub.add_parser('pilot-report');p.add_argument('--input',default='pilot/journeys.csv');p.add_argument('--output',default='pilot/report.json');p.set_defaults(func=cmd_pilot)
    p=sub.add_parser('status');p.add_argument('--output',default='reports/readiness.json');p.add_argument('--with-tests',action='store_true');p.set_defaults(func=cmd_status)
    args=parser.parse_args(argv);args.func(args)

if __name__=='__main__':main()
