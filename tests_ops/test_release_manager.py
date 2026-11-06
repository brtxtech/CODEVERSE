import importlib.util
from pathlib import Path
SRC=Path(__file__).resolve().parents[1]/'tools/codeverse.py'
spec=importlib.util.spec_from_file_location('codeverse_cli',SRC)
cli=importlib.util.module_from_spec(spec);spec.loader.exec_module(cli)
def test_no_secret_values_in_preflight(monkeypatch):
    monkeypatch.setenv('DATABASE_URL','postgresql://username:secret-pass@localhost/db')
    report=cli.prerequisites()
    text=str(report)
    assert 'secret-pass' not in text
    assert report['env_present']['DATABASE_URL'] is True
    assert report['migrations']['found']>=4
def test_release_tasks_not_claimed_completed():
    report=cli.safe_report()
    assert len(report['capabilities'])>=15
    assert not any(x['validated'] for x in report['capabilities'])
def test_migration_requires_confirmation():
    class A:mode='remote';confirm_remote=False
    try:cli.cmd_migrate(A())
    except SystemExit as e:assert 'blocked' in str(e)
    else:raise AssertionError('Remote migration must fail closed')
