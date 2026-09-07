#!/usr/bin/env python3
"""Finite correctness gates for callback-returning timers and cancellation."""
import argparse
import contextlib
import json
import platform
from pathlib import Path
import re
import socket
import signal
import os
import time

from integration import Server as BaseServer, ResponseReader, require, SERVER_BINARY


def Server(**options):
    return BaseServer(SERVER_BINARY, **options)


def request(path, close=False):
    return (f'GET {path} HTTP/1.1\r\nHost: localhost\r\n' +
            ('Connection: close\r\n' if close else '') + '\r\n').encode()


def fetch(server, path):
    with server.connect() as client:
        client.sendall(request(path, True))
        return ResponseReader(client).response()


def counts(server):
    status, _, body = fetch(server, '/continuation-counts')
    require(status == 200, 'counter route failed')
    return json.loads(body)


def await_count(server, key, minimum):
    deadline = time.monotonic() + 2
    current = {}
    while time.monotonic() < deadline:
        try:
            current = counts(server)
        except (EOFError, ConnectionResetError, ConnectionAbortedError, ConnectionRefusedError):
            require(server.process.poll() is None, 'server exited while awaiting terminal state')
            time.sleep(.01)
            continue
        if current[key] >= minimum:
            return current
        time.sleep(.01)
    raise AssertionError(f'{key} did not reach {minimum}: {current}')


def final_counts(server):
    for line in server.lines:
        match = re.fullmatch(r'CONTINUATIONS started=(\d+) finished=(\d+) cancelled=(\d+) live=(\d+)', line)
        if match:
            result = dict(zip(('started', 'finished', 'cancelled', 'live'), map(int, match.groups())))
            require(result['live'] == 0, 'application state remained after shutdown')
            require(result['started'] == result['finished'] + result['cancelled'], 'terminal callback count mismatch')
            return result
    raise AssertionError('missing final continuation counters')


def shared_options(mode):
    return dict(shards=1, execution=mode, workers=1 if mode == 'workers' else 0,
                connections=64, send_chunk=3, timeout_ms=4000,
                output_bytes=2048, max_response=4096)


def framing_and_reuse(mode):
    with Server(**shared_options(mode), stall_ms=1) as server:
        with server.connect(timeout=8) as client:
            client.sendall(b''.join(request('/timed-chunks') for _ in range(128)))
            reader = ResponseReader(client)
            for _ in range(128):
                status, headers, body = reader.response()
                require(status == 200 and headers.get(b'transfer-encoding') == b'chunked', 'stream framing failed')
                require(body == b'first second third', 'resume lost or replayed body bytes')
        require(fetch(server, '/empty-timer')[2] == b'', 'empty flush/timer changed body')
        current = counts(server)
        require(current == dict(started=129, finished=129, cancelled=0, live=0), 'handler replay or leaked finished state')
        with server.connect() as client:
            client.sendall(request('/abort-after-flush'))
            try:
                ResponseReader(client).response()
            except (EOFError, ConnectionResetError):
                pass
            else:
                raise AssertionError('post-flush failure published a completed response')
        current = await_count(server, 'finished', 130)
        require(current['started'] == 130 and current['live'] == 0, 'error cleanup repeated or leaked')
    final_counts(server)


def many_waits(mode):
    with Server(**shared_options(mode), stall_ms=1200) as server:
        with contextlib.ExitStack() as stack:
            clients = [stack.enter_context(server.connect()) for _ in range(32)]
            for client in clients:
                client.sendall(request('/wait-only'))
            current = await_count(server, 'started', 32)
            require(current['live'] == 32, 'waiting handlers retained the worker or timer expired before admission')
            require(fetch(server, '/plaintext')[2] == b'Hello, World!', 'unrelated request could not progress during waits')
            for client in clients:
                require(ResponseReader(client).response()[2] == b'done', 'timer response mismatch')
        with server.connect() as client:
            client.sendall(request('/plaintext') + request('/wait-only'))
            reader = ResponseReader(client)
            client.settimeout(.7)
            require(reader.response()[2] == b'Hello, World!', 'timer retained an earlier batched response')
            client.settimeout(3)
            require(reader.response()[2] == b'done', 'timer failed after preceding batch drained')
        current = counts(server)
        require(current == dict(started=33, finished=33, cancelled=0, live=0), 'timer finish count mismatch')
    final_counts(server)


def timeout_and_shutdown(mode):
    options = shared_options(mode)
    options['timeout_ms'] = 150
    options['deadline_sweep_ms'] = 5
    with Server(**options, stall_ms=10000) as server:
        with server.connect() as client:
            client.sendall(request('/wait-only'))
            require(client.recv(1) == b'', 'sticky request deadline did not cancel timer')
        current = await_count(server, 'cancelled', 1)
        require(current['live'] == 0 and current['started'] == 1, 'timeout cleanup did not run exactly once')
        with contextlib.ExitStack() as stack:
            clients = [stack.enter_context(server.connect()) for _ in range(12)]
            for client in clients:
                client.sendall(request('/wait-only'))
            await_count(server, 'started', 13)
            server.request_stop()
    current = final_counts(server)
    require(current['cancelled'] == 13 and current['finished'] == 0, 'shutdown failed to drain cancellation callbacks')


def disconnect_after_flush(mode):
    options = shared_options(mode)
    options['connections'] = 1
    with Server(**options, stall_ms=300) as server:
        with server.connect() as client:
            client.sendall(request('/timed-chunks'))
            reader = ResponseReader(client)
            require(reader._line().startswith(b'HTTP/1.1 200 '), 'initial flush was not visible')
            while reader._line():
                pass
            size = int(reader._line(), 16)
            require(reader._take(size) == b'first ', 'first chunk changed')
            require(reader._take(2) == b'\r\n', 'first chunk terminator changed')
            import struct
            client.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER,
                              struct.pack('hh' if __import__('os').name == 'nt' else 'ii', 1, 0))
        current = await_count(server, 'cancelled', 1)
        require(current['live'] == 0, 'disconnect retained application state')
        require(fetch(server, '/empty-timer')[0] == 200, 'slot reuse after cancellation failed')
    final_counts(server)


def notification_ordering_and_reuse(mode):
    with Server(**shared_options(mode), stall_ms=10) as server:
        with server.connect() as client:
            reader = ResponseReader(client)
            for index in range(8):
                client.sendall(request(f'/notify-before/{index}'))
                require(reader.response()[2] == b'notified', 'pending notification lost to immediate timer')
                require(fetch(server, f'/signal/{index}')[2] == b'stale', 'finished request handle remained active')
            client.sendall(request('/notify-timeout/8'))
            require(reader.response()[2] == b'timer', 'notification timeout did not resume')
        require(fetch(server, '/signal/8')[2] == b'stale', 'timer finish retained producer handle')
        require(fetch(server, '/notify/0')[0] == 503, 'fixed fixture registry reused a published entry')
        require(counts(server) == dict(started=9, finished=9, cancelled=0, live=0), 'notification finish accounting failed')
    final_counts(server)


def notification_many_waits(mode, shards=1):
    options = shared_options(mode)
    options['shards'] = shards
    with Server(**options, stall_ms=10) as server:
        with contextlib.ExitStack() as stack:
            clients = [stack.enter_context(server.connect()) for _ in range(32)]
            for index, client in enumerate(clients):
                client.sendall(request(f'/notify/{index}'))
            current = await_count(server, 'started', 32)
            require(current['live'] == 32, 'notifications retained callback workers')
            require(fetch(server, '/plaintext')[2] == b'Hello, World!', 'unrelated request stalled behind notification waits')
            for index, client in enumerate(clients):
                require(fetch(server, f'/signal/{index}')[2] == b'notified', 'producer signal failed')
                require(ResponseReader(client).response()[2] == b'notified', 'producer failed to resume request')
                require(fetch(server, f'/signal/{index}')[2] == b'stale', 'terminal signal was not rejected')
        require(counts(server) == dict(started=32, finished=32, cancelled=0, live=0), 'notification finish accounting failed')
    final_counts(server)


def notification_pipeline_and_flush(mode):
    with Server(**shared_options(mode), stall_ms=10) as server:
        with server.connect() as client:
            client.sendall(request('/plaintext') + request('/notify/0') + request('/plaintext'))
            reader = ResponseReader(client)
            require(reader.response()[2] == b'Hello, World!', 'notification wait retained previous pipeline response')
            await_count(server, 'started', 1)
            require(fetch(server, '/signal/0')[2] == b'notified', 'pipeline producer signal failed')
            require(reader.response()[2] == b'notified', 'pipeline notification response missing')
            require(reader.response()[2] == b'Hello, World!', 'pipeline suffix lost after notification')
            client.sendall(request('/notify-flush/1'))
            require(reader._line().startswith(b'HTTP/1.1 200 '), 'notification stream head missing')
            while reader._line():
                pass
            size = int(reader._line(), 16)
            require(reader._take(size) == b'start ', 'notification initial chunk changed')
            require(reader._take(2) == b'\r\n', 'notification chunk terminator changed')
            require(fetch(server, '/signal/1')[2] == b'notified', 'signal during flush failed')
            size = int(reader._line(), 16)
            require(reader._take(size) == b'notified', 'notification final chunk changed')
            require(reader._take(2) == b'\r\n', 'notification final chunk terminator changed')
            require(reader._line() == b'0' and reader._line() == b'', 'notification stream did not terminate')
        require(counts(server) == dict(started=2, finished=2, cancelled=0, live=0), 'notification pipeline accounting failed')
    final_counts(server)


def notification_cancellation(mode):
    options = shared_options(mode)
    options['timeout_ms'] = 200
    options['deadline_sweep_ms'] = 5
    with Server(**options, stall_ms=10000) as server:
        with server.connect() as client:
            client.sendall(request('/notify/0'))
            require(client.recv(1) == b'', 'request deadline did not cancel unbounded notification wait')
        current = await_count(server, 'cancelled', 1)
        require(current['live'] == 0, 'notification timeout did not release state')
        require(fetch(server, '/signal/0')[2] == b'stale', 'cancelled handle remained active')
        with server.connect() as client:
            client.sendall(request('/notify-flush/1'))
            reader = ResponseReader(client)
            require(reader._line().startswith(b'HTTP/1.1 200 '), 'notification disconnect head missing')
            while reader._line():
                pass
            size = int(reader._line(), 16)
            require(reader._take(size) == b'start ', 'notification disconnect first chunk changed')
            require(reader._take(2) == b'\r\n', 'notification disconnect chunk terminator changed')
            import struct
            client.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER,
                              struct.pack('hh' if os.name == 'nt' else 'ii', 1, 0))
        current = await_count(server, 'cancelled', 2)
        require(current['live'] == 0, 'notification disconnect retained application state')
        require(fetch(server, '/signal/1')[2] == b'stale', 'disconnected handle remained active')
        with contextlib.ExitStack() as stack:
            clients = [stack.enter_context(server.connect()) for _ in range(8)]
            for index, client in enumerate(clients, 2):
                client.sendall(request(f'/notify/{index}'))
            await_count(server, 'started', 10)
            server.request_stop()
    current = final_counts(server)
    require(current == dict(started=10, finished=0, cancelled=10, live=0), 'notification shutdown did not clean every request once')


def sharded_timers():
    options = shared_options('inline')
    options['shards'] = 3
    with Server(**options, stall_ms=100) as server:
        with contextlib.ExitStack() as stack:
            clients = [stack.enter_context(server.connect()) for _ in range(24)]
            for client in clients:
                client.sendall(request('/timed-chunks'))
            for client in clients:
                require(ResponseReader(client).response()[2] == b'first second third', 'sharded timer body mismatch')
        require(counts(server) == dict(started=24, finished=24, cancelled=0, live=0), 'sharded state accounting mismatch')
    final_counts(server)
    require(server.stats['shards'] == 3, 'configured shard count changed')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--server', type=Path)
    parser.add_argument('--json', type=Path)
    args = parser.parse_args()
    if args.server:
        global SERVER_BINARY
        SERVER_BINARY = args.server.resolve()
    results = []
    for mode in ('inline', 'workers'):
        for test in (framing_and_reuse, many_waits, timeout_and_shutdown, disconnect_after_flush,
                     notification_ordering_and_reuse, notification_many_waits,
                     notification_pipeline_and_flush, notification_cancellation):
            started = time.monotonic()
            test(mode)
            result = dict(name=f'{test.__name__}/{mode}', passed=True, seconds=round(time.monotonic() - started, 3))
            results.append(result)
            print(f"PASS {result['name']}", flush=True)
    started = time.monotonic()
    if platform.system() == 'Darwin':
        results.append(dict(name='sharded_timers/inline', skipped='macOS engine supports one owner'))
        print('SKIP sharded_timers/inline: macOS engine supports one owner', flush=True)
    else:
        sharded_timers()
        results.append(dict(name='sharded_timers/inline', passed=True, seconds=round(time.monotonic() - started, 3)))
        print('PASS sharded_timers/inline', flush=True)
    started = time.monotonic()
    if platform.system() == 'Darwin':
        results.append(dict(name='sharded_notifications/inline', skipped='macOS engine supports one owner'))
        print('SKIP sharded_notifications/inline: macOS engine supports one owner', flush=True)
    else:
        notification_many_waits('inline', shards=3)
        results.append(dict(name='sharded_notifications/inline', passed=True, seconds=round(time.monotonic() - started, 3)))
        print('PASS sharded_notifications/inline', flush=True)
    packet = dict(ok=True, groups=len(results), results=results)
    if args.json:
        args.json.write_text(json.dumps(packet, indent=2) + '\n')
    print(json.dumps(packet))


if __name__ == '__main__':
    # Windows runs under the existing process-tree supervisor in verify_windows.py.
    if os.name == 'posix':
        def watchdog(signum, frame):
            raise TimeoutError('continuation suite exceeded its 120-second watchdog')
        signal.signal(signal.SIGALRM, watchdog)
        signal.alarm(120)
    try:
        main()
    finally:
        if os.name == 'posix':
            signal.alarm(0)
