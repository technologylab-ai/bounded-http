import subprocess
import sys

for script in ('tests/test_compare.py', 'tests/arena_lifecycle_integration.py',
               'tests/batch_integration.py', 'tests/gather_integration.py',
               'tests/inline_integration.py', 'tests/integration.py', 'tools/smoke.py'):
    print('RUN CORE', script, flush=True)
    subprocess.run([sys.executable, script], check=True, timeout=120)
