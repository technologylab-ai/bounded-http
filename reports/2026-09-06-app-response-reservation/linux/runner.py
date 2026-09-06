import datetime
import hashlib
import json
import os
import pathlib
import platform
import signal
import socket
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent
ENGINE = ROOT / 'engine'
TOKEN = '7cb134a4-311e-49ce-80c6-c2ca7b75957f'
RESULT = {'started_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'complete': False, 'commands': []}
CHILD = None

def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def write_json(name, value):
    (ROOT / name).write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')

def scan():
    result = []
    for proc in pathlib.Path('/proc').iterdir():
        if not proc.name.isdecimal() or int(proc.name) == os.getpid():
            continue
        try:
            cwd = os.readlink(proc / 'cwd')
            exe = os.readlink(proc / 'exe')
            if cwd.startswith(str(ROOT)) or exe.startswith(str(ROOT)):
                stat = (proc / 'stat').read_text().rsplit(') ', 1)[1].split()
                result.append({'pid': int(proc.name), 'ppid': int(stat[1]), 'pgid': int(stat[2]), 'start_ticks': stat[19], 'cwd': cwd, 'exe': exe, 'command': (proc / 'cmdline').read_bytes().replace(b'\0', b' ').decode(errors='replace')})
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            pass
    return result

def cleanup_child(child):
    if child.poll() is None:
        try:
            os.killpg(child.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            child.wait(timeout=5)
    survivors = scan()
    # A suite may start its server in a new session. Reconcile those exact
    # workspace-owned identities as well as the original command group.
    for proc in survivors:
        path = pathlib.Path('/proc') / str(proc['pid'])
        try:
            if path.joinpath('stat').read_text().rsplit(') ', 1)[1].split()[19] == proc['start_ticks']:
                os.kill(proc['pid'], signal.SIGKILL)
        except (FileNotFoundError, ProcessLookupError):
            pass
    deadline = time.monotonic() + 5
    while scan() and time.monotonic() < deadline:
        time.sleep(0.05)
    return {'initial_workspace_survivors': survivors, 'remaining_workspace_processes': scan()}

def capture(command):
    result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=10)
    return {'command': command, 'exit_code': result.returncode, 'output': result.stdout}

def validate_source():
    manifest = json.loads((ROOT / 'source-input.sha256.json').read_text())
    for name, expected in manifest.items():
        actual = hashlib.sha256((ENGINE / name).read_bytes()).hexdigest()
        if actual != expected:
            raise RuntimeError('Source hash mismatch: ' + name)
    return {'entries': len(manifest), 'manifest_sha256': hashlib.sha256((ROOT / 'source-input.sha256.json').read_bytes()).hexdigest()}

def interrupted(signum, frame):
    raise RuntimeError('Native verifier interrupted or overall watchdog expired: ' + str(signum))

def main():
    global CHILD
    owner = json.loads(pathlib.Path('/tmp/zig-http-measurement.lock/owner.json').read_text())
    assert owner['token'] == TOKEN
    assert pathlib.Path('/proc/' + str(owner['owner_pid']) + '/stat').read_text().rsplit(') ', 1)[1].split()[19] == owner['process_start_ticks']
    assert not scan(), 'Workspace has pre-existing child processes'
    for sig in [signal.SIGINT, signal.SIGTERM, signal.SIGALRM]:
        signal.signal(sig, interrupted)
    signal.alarm(2700)
    env = {'recorded_utc': now(), 'host': socket.gethostname(), 'platform': platform.platform(), 'uname': list(platform.uname()), 'python': sys.version, 'zig': capture(['zig', 'version']), 'cpu': capture(['lscpu']), 'os_release': pathlib.Path('/etc/os-release').read_text(), 'io_uring_disabled': pathlib.Path('/proc/sys/kernel/io_uring_disabled').read_text(), 'engine_base_commit': '2b41a0801a655f02223a9ece2e8ebddfffed64f7', 'input': 'Frozen working tree streamed from zig-http-app-seam; src/api.zig and src/server.zig differ from base', 'performance_comparison': False}
    write_json('platform.json', env)
    assert env['zig']['output'].strip() == '0.16.0'
    RESULT['source_before'] = validate_source()
    print('SOURCE ' + json.dumps(RESULT['source_before']), flush=True)
    commands = [
        (600, ['zig', 'build', 'verify', '-Doptimize=Debug', '-j2', '--summary', 'all']),
        (600, ['zig', 'build', 'verify', '-Doptimize=ReleaseSafe', '-j2', '--summary', 'all']),
        (600, ['zig', 'build', '-Doptimize=ReleaseSafe', '-j2', '--summary', 'all']),
        (180, ['python3', '-B', 'tests/test_compare.py', '-v']),
        (180, ['python3', '-B', 'tests/arena_lifecycle_integration.py']),
        (180, ['python3', '-B', 'tests/batch_integration.py']),
        (180, ['python3', '-B', 'tests/gather_integration.py']),
        (180, ['python3', '-B', 'tests/inline_integration.py']),
        (180, ['python3', '-B', 'tests/integration.py']),
        (180, ['python3', '-B', 'tools/smoke.py']),
    ]
    try:
        for index, (watchdog, command) in enumerate(commands, 1):
            record = {'sequence': index, 'command': command, 'watchdog_seconds': watchdog, 'started_utc': now()}
            RESULT['commands'].append(record)
            print('COMMAND ' + json.dumps(record), flush=True)
            CHILD = subprocess.Popen(command, cwd=ENGINE, start_new_session=True, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
            record['leader_pid'] = CHILD.pid
            record['process_group'] = CHILD.pid
            observed = {}
            deadline = time.monotonic() + watchdog
            try:
                while CHILD.poll() is None:
                    for process in scan():
                        observed[(process['pid'], process['start_ticks'])] = process
                    if time.monotonic() >= deadline:
                        raise RuntimeError('Command watchdog expired: ' + repr(command))
                    time.sleep(0.1)
                record['exit_code'] = CHILD.wait(timeout=1)
            finally:
                record['observed_processes'] = list(observed.values())
                record['cleanup'] = cleanup_child(CHILD)
                record['finished_utc'] = now()
                CHILD = None
                write_json('summary.json', RESULT)
            print('COMMAND_FINISHED ' + json.dumps({key: value for key, value in record.items() if key != 'observed_processes'}), flush=True)
            assert not record['cleanup']['initial_workspace_survivors'], 'A command left workspace child processes; cleanup performed'
            assert not record['cleanup']['remaining_workspace_processes'], 'Workspace child processes remain'
            assert record['exit_code'] == 0, 'Native command failed'
        RESULT['source_after'] = validate_source()
        RESULT['complete'] = True
    except BaseException as error:
        RESULT['error'] = repr(error)
        raise
    finally:
        signal.alarm(0)
        if CHILD is not None:
            RESULT['interrupted_child_cleanup'] = cleanup_child(CHILD)
        RESULT['finished_utc'] = now()
        RESULT['final_workspace_processes'] = scan()
        write_json('summary.json', RESULT)
        print('VERIFICATION_FINISHED ' + json.dumps({'complete': RESULT['complete'], 'finished_utc': RESULT['finished_utc'], 'remaining_processes': RESULT['final_workspace_processes'], 'error': RESULT.get('error')}), flush=True)

if __name__ == '__main__':
    main()
