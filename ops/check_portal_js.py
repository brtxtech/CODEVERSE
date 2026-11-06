"""Check that embedded ESM in the secure portal parses on Node 22+ (not an OAuth e2e)."""
from pathlib import Path
from tempfile import TemporaryDirectory
import subprocess

root = Path(__file__).resolve().parents[1]
html = (root / 'apps/secure-portal/index.html').read_text()
start = html.index('<script type="module">') + len('<script type="module">')
end = html.index('</script>', start)
with TemporaryDirectory() as workdir:
    f = Path(workdir) / 'codeverse-secure-portal.mjs'
    f.write_text(html[start:end])
    subprocess.run(['node', '--check', str(f)], check=True)
print('Secure portal JavaScript syntax: OK')
