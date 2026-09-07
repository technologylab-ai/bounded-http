#!/usr/bin/env python3
"""Run native Windows HTTP gates with finite process-tree watchdogs.

The workflow supplies the exact compiler and records the hosted Windows image.
This gate exercises the HTTP application, not the sibling wiki's Windows proofs.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import struct
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[1]


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def capture(arguments):
    return subprocess.check_output(arguments, cwd=ROOT, text=True, timeout=20).strip()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--packet', type=Path, required=True)
    args = parser.parse_args()
    require(os.name == 'nt' and platform.machine().lower() in ('amd64', 'x86_64'),
            'This initial runtime gate requires native x64 Windows')
    packet = args.packet.resolve()
    require(not packet.is_relative_to(ROOT), 'Keep the evidence packet outside the checkout')
    packet.mkdir(parents=True, exist_ok=True)
    receipt = dict(schema_version=1, tool='bounded-http-windows-runtime', ok=False,
                   started_utc=datetime.now(timezone.utc).isoformat(),
                   execution='native x64 Windows compiler and HTTP executable',
                   timed_comparison=False, phases=[],
                   exclusions=['Four batch maximum-cell fixtures need POSIX SIGSTOP/SIGCONT',
                               'POSIX-only transport fixtures remain explicit skips',
                               'CTRL_BREAK shutdown only; console-close, logoff and service control remain unqualified',
                               'No ARM64, WOW64, device, production-load or latency qualification'])
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1',
                       BOUNDED_HTTP_WINDOWS_WATCHDOG='process-tree supervisor')

    def save():
        (packet / 'runtime-gate.json').write_text(json.dumps(receipt, indent=2) + '\n')

    def run(name, arguments, timeout):
        phase = dict(name=name, arguments=arguments, timeout_seconds=timeout,
                     started_utc=datetime.now(timezone.utc).isoformat(), log=name + '.log')
        receipt['phases'].append(phase)
        save()
        print('START ' + name, flush=True)
        started = time.monotonic()
        with (packet / phase['log']).open('w', encoding='utf-8') as output:
            process = subprocess.Popen(arguments, cwd=ROOT, env=environment,
                                       stdin=subprocess.DEVNULL, stdout=output,
                                       stderr=subprocess.STDOUT,
                                       creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
            try:
                phase['exit_code'] = process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                phase['watchdog_expired'] = True
                # The PID still identifies this live child. Kill its descendants
                # before collecting the process; never target unrelated runners.
                cleanup = subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                                         capture_output=True, text=True, timeout=20)
                phase['timeout_cleanup'] = dict(exit_code=cleanup.returncode,
                                                 stdout=cleanup.stdout, stderr=cleanup.stderr)
                process.wait(timeout=10)
                raise TimeoutError(name + ' exceeded its process-tree watchdog')
            finally:
                phase['seconds'] = round(time.monotonic() - started, 6)
                save()
        require(phase['exit_code'] == 0, name + ' failed; inspect ' + phase['log'])
        print('PASS ' + name, flush=True)

    try:
        expected = (ROOT / '.zig-version').read_text().strip()
        require(expected == '0.16.0' and capture(['zig', 'version']) == expected,
                'Use exactly the repository Zig 0.16.0 release')
        receipt['zig_version'] = expected
        receipt['repository_commit'] = capture(['git', 'rev-parse', 'HEAD'])
        receipt['input_status'] = capture(['git', 'status', '--porcelain=v1', '--untracked-files=all'])
        require(not receipt['input_status'], 'Publication runtime gates require a clean checkout')
        if os.environ.get('GITHUB_SHA'):
            require(receipt['repository_commit'] == os.environ['GITHUB_SHA'], 'Workflow commit mismatch')
        paths = capture(['git', 'ls-files']).splitlines()
        receipt['source_hashes'] = {path: digest(ROOT / path) for path in paths
                                    if path.startswith(('src/', 'tests/', 'examples/')) or
                                    path in ('.zig-version', 'build.zig', 'build.zig.zon',
                                             'tools/verify_windows.py', 'tools/check_embedding.py',
                                             'tools/smoke.py', 'tools/benchmark.py', 'tools/compare.py')}
        run('verify-debug', ['zig', 'build', 'verify', '--summary', 'all'], 300)
        run('verify-release-safe', ['zig', 'build', 'verify', '-Doptimize=ReleaseSafe', '--summary', 'all'], 300)
        run('build-release-safe', ['zig', 'build', '-Doptimize=ReleaseSafe'], 300)
        binary = ROOT / 'zig-out/bin/bounded-http.exe'
        data = binary.read_bytes()
        require(data[:2] == b'MZ' and len(data) >= 64, 'HTTP output is not a PE executable')
        offset = struct.unpack_from('<I', data, 0x3c)[0]
        require(data[offset:offset + 4] == b'PE\0\0' and
                struct.unpack_from('<H', data, offset + 4)[0] == 0x8664,
                'HTTP executable is not native x64 PE')
        receipt['binary'] = dict(path=str(binary), sha256=digest(binary), pe_machine='8664',
                               optimize='ReleaseSafe', target='x86_64-windows')
        run('comparator-receipts', [sys.executable, 'tests/test_compare.py', '-v'], 30)
        for suite in ('arena_lifecycle', 'batch', 'gather', 'inline', ''):
            name = (suite + '_' if suite else '') + 'integration'
            run(name, [sys.executable, 'tests/' + name + '.py', '--server', str(binary),
                       '--timeout', '120', '--json', str(packet / (name + '.json'))], 150)
            wire = json.loads((packet / (name + '.json')).read_text())
            require(wire.get('ok') is True, name + ' did not produce a passing receipt')
        run('continuation-integration',
            [sys.executable, 'tests/continuation_integration.py', '--server', str(binary),
             '--json', str(packet / 'continuation-integration.json')], 150)
        continuation = json.loads((packet / 'continuation-integration.json').read_text())
        require(continuation.get('ok') is True and continuation.get('groups') == 18,
                'Continuation timer/cancellation receipt mismatch')
        run('windows-shards-integration',
            [sys.executable, 'tests/windows_shards_integration.py', '--server', str(binary),
             '--timeout', '120', '--json', str(packet / 'windows-shards-integration.json')], 150)
        shards = json.loads((packet / 'windows-shards-integration.json').read_text())
        require(shards.get('ok') is True and shards.get('passed') == 9,
                'Native Windows multi-owner receipt mismatch')
        require(all(session['backend'] == 'iocp' and session['stats']['shards'] >= 2
                    for session in shards['sessions']), 'Multi-owner suite did not run native IOCP shards')
        run('smoke', [sys.executable, 'tools/smoke.py', '--server', str(binary), '--timeout', '150',
                      '--json', str(packet / 'smoke.json')], 180)
        smoke = json.loads((packet / 'smoke.json').read_text())
        require(smoke['ok'] and smoke['server']['backend'] == 'iocp' and
                smoke['server']['stats']['completed'] == 30000 and
                smoke['build']['optimize'] == 'ReleaseSafe', 'Native IOCP smoke receipt mismatch')
        require(smoke['build']['binary_sha256'] == receipt['binary']['sha256'], 'Binary identity changed')
        receipt['output_status'] = capture(['git', 'status', '--porcelain=v1', '--untracked-files=all'])
        require(not receipt['output_status'], 'Verification modified the checkout')
        receipt['ok'] = True
    except Exception as error:
        receipt['error'] = type(error).__name__ + ': ' + str(error)
        print(receipt['error'], file=sys.stderr, flush=True)
    finally:
        receipt['finished_utc'] = datetime.now(timezone.utc).isoformat()
        save()
    return 0 if receipt['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
