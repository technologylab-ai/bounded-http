#!/usr/bin/env python3
"""Finite native Windows witnesses for accepted-socket handoff between IOCP owners.

Response acknowledgments establish live admission before capacity checks.
Per-owner final counters establish distribution, including destination owners.
These wire tests do not force mailbox interleavings or infer deadline retention.
Deterministic Zig fixtures cover those internal ownership and shutdown races.
The Windows supervisor supplies the whole-process-tree watchdog.
"""

import argparse
import contextlib
import json
import os
from pathlib import Path
import queue
import re
import socket
import subprocess
import sys
import threading
import time
import traceback

import integration as wire


def get(target=b"/plaintext", close=False, method=b"GET"):
    return (method + b" " + target + b" HTTP/1.1\r\nHost: localhost\r\n" +
            (b"Connection: close\r\n" if close else b"") + b"\r\n")


def post(body, target=b"/borrowed-body", close=False):
    return (b"POST " + target + b" HTTP/1.1\r\nHost: localhost\r\nContent-Length: " +
            str(len(body)).encode("ascii") + b"\r\n" +
            (b"Connection: close\r\n" if close else b"") + b"\r\n" + body)


def payload(client, generation):
    # Exceed the optional small-borrow copy threshold and include binary bytes.
    return ("client=%02d;generation=%02d;" % (client, generation)).encode("ascii") + bytes(range(256)) * 2


def response(reader, expected, head=False):
    status, headers, body = reader.response(head=head)
    wire.require(status == 200 and body == expected, "cross-owner response body or framing changed")
    wire.require(headers.get(b"server") == b"bounded-http", "Server product token changed")
    return headers


class ShardedServer(wire.Server):
    def __init__(self, binary, **options):
        options.setdefault("shards", 3)
        options.setdefault("send_chunk", 65536)
        options.setdefault("borrow_copy_threshold", 0)
        options.setdefault("timeout_ms", 6000)
        super().__init__(binary, execution="inline", workers=0, **options)
        self.shard_stats = []

    def __enter__(self):
        super().__enter__()
        try:
            wire.require(self.backend == "iocp", "native Windows IOCP is required")
            ready = next(line for line in self.lines if line.startswith("READY "))
            wire.require(re.search(r"\bshards=%d\b" % self.options["shards"], ready) is not None,
                         "READY did not report the requested owner count")
        except BaseException:
            self.__exit__(*sys.exc_info())
            raise
        return self

    def __exit__(self, kind, value, tb):
        result = super().__exit__(kind, value, tb)
        if kind is None:
            lines = [line for line in self.lines if line.startswith("SHARDS ")]
            wire.require(len(lines) == 1, "one final per-owner receipt is required")
            self.shard_stats = [dict(accepted=int(accepted), completed=int(completed))
                                for accepted, completed in
                                re.findall(r"accepted=(\d+)/completed=(\d+)", lines[0])]
            wire.require(len(self.shard_stats) == self.options["shards"], "per-owner receipt count differs")
            for field in ("accepted", "completed"):
                wire.require(sum(shard[field] for shard in self.shard_stats) == self.stats[field],
                             "per-owner and aggregate %s differ" % field)
            for field in ("handoffs_sent", "handoffs_received", "handoffs_closed", "max_handoff_delay_ns"):
                wire.require(type(self.stats.get(field)) is int and self.stats[field] >= 0,
                             "missing handoff counter: " + field)
            wire.require(self.stats["handoffs_sent"] == self.stats["handoffs_received"],
                         "a published socket remained in a mailbox at shutdown")
            wire.require(self.stats["shards"] == self.options["shards"] and
                         self.stats["execution"] == "inline_event_loop" and
                         self.stats["worker_dispatches"] == 0, "owner configuration changed")
        return result

    def record(self, phase):
        return dict(phase=phase, backend=self.backend, options=self.options,
                    stats=self.stats, owners=self.shard_stats)


def require_distribution(server):
    wire.require(all(owner["accepted"] > 0 and owner["completed"] > 0 for owner in server.shard_stats),
                 "every configured IOCP owner must complete a response")
    wire.require(server.stats["handoffs_sent"] > 0, "destination handoff path was not exercised")


def parallel_clients(sockets, function, timeout=30):
    """Start bounded client threads together and join every thread before return."""
    barrier = threading.Barrier(len(sockets))
    results = queue.Queue(maxsize=len(sockets))

    def client(index, sock):
        failure = None
        try:
            barrier.wait(timeout=5)
            function(index, sock)
        except BaseException as error:
            failure = error
            barrier.abort()
        finally:
            results.put((index, failure))

    threads = [threading.Thread(target=client, args=(index, sock), daemon=True)
               for index, sock in enumerate(sockets)]
    deadline = time.monotonic() + timeout
    for thread in threads:
        thread.start()
    try:
        for thread in threads:
            thread.join(timeout=max(0, deadline - time.monotonic()))
        wire.require(not any(thread.is_alive() for thread in threads), "concurrent client watchdog expired")
        failures = [results.get_nowait() for _ in threads]
        for index, failure in failures:
            if failure is not None:
                raise AssertionError("client %d failed: %s" % (index, failure)) from failure
    finally:
        barrier.abort()
        for sock in sockets:
            with contextlib.suppress(OSError):
                sock.shutdown(socket.SHUT_RDWR)
            sock.close()
        for thread in threads:
            thread.join(timeout=1)
        wire.require(not any(thread.is_alive() for thread in threads), "client threads survived socket cleanup")


def run(binary, emit, sessions):
    for shards in (2, 3, 4):
        with ShardedServer(binary, shards=shards, connections=8, send_chunk=97) as server:
            for stream in range(shards * 3):
                first, second = payload(stream, 0), payload(stream, 1)
                target = ("/buffered?owner-witness=%d" % stream).encode("ascii")
                with server.connect() as sock:
                    sock.sendall(post(first) + post(second, b"/borrowed-body-chunked") + get(target, close=True))
                    reader = wire.ResponseReader(sock)
                    response(reader, first)
                    wire.require(response(reader, second).get(b"transfer-encoding") == b"chunked",
                                 "borrowed chunk framing changed")
                    response(reader, target)
                    wire.require(not reader.buffer, "pipeline gained an extra response")
                    wire.expect_closed(sock)
        require_distribution(server)
        wire.require(server.stats["completed"] == shards * 9 and server.stats["accepted"] == shards * 3,
                     "distribution witness lost or duplicated a request")
        wire.require(server.stats["timeouts"] == server.stats["rejected"] == server.stats["handoffs_closed"] == 0,
                     "valid handoffs were rejected or expired")
        wire.require(server.stats["max_send_bytes"] <= 97, "partial-send cap was exceeded")
        phase = "distinct_borrowed_pipeline_on_%d_iocp_owners" % shards
        sessions.append(server.record(phase))
        emit(phase)

    with ShardedServer(binary, shards=4, connections=16, send_chunk=251) as server:
        with contextlib.ExitStack() as stack:
            sockets = [stack.enter_context(server.connect(timeout=5)) for _ in range(12)]

            def client(index, sock):
                reader = wire.ResponseReader(sock)
                for generation in range(8):
                    body = payload(index, generation)
                    route = b"/borrowed-body-chunked" if generation % 2 else b"/echo"
                    sock.sendall(post(body, route) + get(close=generation == 7))
                    response(reader, body)
                    response(reader, wire.PLAINTEXT)
                wire.expect_closed(sock)

            parallel_clients(sockets, client)
    require_distribution(server)
    wire.require(server.stats["accepted"] == 12 and server.stats["completed"] == 192,
                 "concurrent clients lost or duplicated a request")
    wire.require(server.stats["timeouts"] == server.stats["rejected"] == 0,
                 "within-capacity concurrent clients failed")
    sessions.append(server.record("concurrent_distinct_payloads_and_flushes"))
    emit("concurrent_distinct_payloads_and_flushes")

    # Each first response acknowledges adoption. The unfinished second request
    # then keeps its admission charge until the client supplies the final bytes.
    with ShardedServer(binary, shards=3, connections=6) as server:
        with contextlib.ExitStack() as stack:
            held = [stack.enter_context(server.connect()) for _ in range(6)]
            readers = [wire.ResponseReader(sock) for sock in held]
            for sock, reader in zip(held, readers):
                sock.sendall(get() + post(b"123456789")[:-8])
                response(reader, wire.PLAINTEXT)
            for _ in range(4):
                try:
                    with server.connect(timeout=0.25) as extra:
                        extra.sendall(get())
                        status, _, _ = wire.ResponseReader(extra).response()
                        wire.require(status == 503, "request above the shared connection ceiling was served")
                except (TimeoutError, socket.timeout, EOFError, ConnectionError):
                    pass
            for sock, reader in zip(held, readers):
                sock.sendall(b"23456789" + get(close=True))
                response(reader, b"123456789")
                response(reader, wire.PLAINTEXT)
                wire.expect_closed(sock)
        with server.connect() as recovered:
            recovered.sendall(get(close=True))
            response(wire.ResponseReader(recovered), wire.PLAINTEXT)
            wire.expect_closed(recovered)
    require_distribution(server)
    wire.require(server.stats["peak_connections"] == 6 and server.stats["rejected"] > 0,
                 "global admission boundary was not reached")
    wire.require(server.stats["accepted"] == 7 and server.stats["completed"] == 19 and
                 server.stats["timeouts"] == 0, "held connections or admission recovery changed")
    sessions.append(server.record("acknowledged_global_ceiling_and_recovery"))
    emit("acknowledged_global_ceiling_and_recovery")

    with ShardedServer(binary, shards=4, connections=4, send_chunk=97, prearm_receive=1) as server:
        for generation in range(24):
            body = payload(generation, generation)
            target = ("/buffered?generation=%d" % generation).encode("ascii")
            with server.connect() as sock:
                sock.sendall(post(body) + get(b"/chunks") + get(b"/index.html", method=b"HEAD") + get(target))
                sock.shutdown(socket.SHUT_WR)
                reader = wire.ResponseReader(sock)
                response(reader, body)
                response(reader, b"first second third")
                response(reader, b"", head=True)
                response(reader, target)
                wire.require(not reader.buffer, "EOF generation gained an extra response")
                wire.expect_closed(sock)
    require_distribution(server)
    wire.require(server.stats["accepted"] == 24 and server.stats["completed"] == 96 and
                 server.stats["flushes"] == server.stats["resumed"] == 72 and
                 server.stats["timeouts"] == server.stats["rejected"] == 0,
                 "fresh stream EOF, borrow or flush continuation changed")
    sessions.append(server.record("fresh_stream_generations_and_half_close"))
    emit("fresh_stream_generations_and_half_close")

    # Read only response headers from three large borrows. Small receive windows
    # keep output pending while three acknowledged requests retain receive slots.
    body = b"s" * (1024 * 1024)
    with ShardedServer(binary, shards=3, connections=6, max_body=len(body),
                       socket_send_buffer=4096, timeout_ms=15000) as server:
        with contextlib.ExitStack() as stack:
            for _ in range(3):
                slow = stack.enter_context(server.connect(timeout=5))
                slow.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024)
                slow.sendall(post(body))
                reader = wire.ResponseReader(slow)
                wire.require(reader._line().startswith(b"HTTP/1.1 200 "), "borrowed send did not start")
                for _ in range(32):
                    if not reader._line():
                        break
                else:
                    raise AssertionError("borrowed response header limit exceeded")
            for _ in range(3):
                held = stack.enter_context(server.connect())
                held.sendall(get() + b"GET /plaintext HTTP/1.1\r\nHost:")
                response(wire.ResponseReader(held), wire.PLAINTEXT)
            server.request_stop()
            server.process.wait(timeout=5)
    require_distribution(server)
    wire.require(server.stats["peak_connections"] == 6 and server.stats["completed"] == 3,
                 "shutdown did not retain three receives and three borrowed sends")
    wire.require(server.stats["bytes_received"] >= len(body) * 3 and
                 server.stats["bytes_sent"] < len(body) * 3,
                 "shutdown did not interrupt the observed partial responses")
    sessions.append(server.record("ctrl_break_with_live_receives_and_partial_borrows"))
    emit("ctrl_break_with_live_receives_and_partial_borrows")

    for iteration in range(3):
        with ShardedServer(binary, shards=3, connections=3, duration_ms=100) as server:
            server.process.wait(timeout=5)
        wire.require(server.stats["accepted"] == server.stats["completed"] == 0,
                     "idle shutdown unexpectedly accepted a connection")
        sessions.append(server.record("idle_duration_shutdown_%d" % iteration))
    emit("repeated_three_owner_idle_duration_shutdown")

    # An occupied loopback port produces a real native listener failure.
    # Deterministic Zig fixtures separately inject later spawn and owner errors.
    with socket.socket() as occupied:
        occupied.bind(("127.0.0.1", 0))
        occupied.listen(1)
        failed = subprocess.run([str(binary), "--shards", "3", "--port", str(occupied.getsockname()[1])],
                                cwd=wire.ROOT, capture_output=True, timeout=8)
        wire.require(failed.returncode != 0 and b"READY " not in failed.stderr,
                     "occupied listener did not fail before readiness")
    invalid = subprocess.run([str(binary), "--shards", "3", "--execution", "workers", "--workers", "2"],
                             cwd=wire.ROOT, capture_output=True, timeout=8)
    wire.require(invalid.returncode != 0 and b"InvalidConfiguration" in invalid.stderr and
                 b"READY " not in invalid.stderr, "multi-owner worker configuration was accepted")
    emit("native_listener_failure_and_invalid_worker_configuration")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", type=Path, default=wire.SERVER_BINARY)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    wire.require(1 <= args.timeout <= 300, "finite suite watchdog required")
    receipt = dict(schema_version=1, tool="bounded-http-windows-shards-integration", ok=False,
                   platform=sys.platform, server=str(args.server.resolve()), tests=[], sessions=[],
                   evidence_scope="native Windows IOCP owners; functional tests, not throughput measurements",
                   scheduling="live owners; deterministic Zig fixtures cover mailbox races and accepted_at retention",
                   watchdog=dict(suite_seconds=args.timeout, socket_seconds=5, shutdown_seconds=8,
                                 supervisor=os.environ.get("BOUNDED_HTTP_WINDOWS_WATCHDOG")))
    started = time.monotonic()

    def emit(name):
        wire.require(time.monotonic() - started < args.timeout, "whole-suite deadline exceeded")
        receipt["tests"].append(dict(name=name, ok=True))
        print("PASS " + name, file=sys.stderr, flush=True)

    try:
        wire.require(os.name == "nt", "this suite requires native Windows; no cross-compile substitution")
        wire.require(receipt["watchdog"]["supervisor"] == "process-tree supervisor",
                     "run this suite through tools/verify_windows.py for its process-tree watchdog")
        wire.require(args.server.is_file(), "build the selected Debug/ReleaseSafe server first")
        run(args.server.resolve(), emit, receipt["sessions"])
        receipt["ok"] = True
    except Exception as error:
        receipt["error"] = "%s: %s" % (type(error).__name__, error)
        traceback.print_exc(file=sys.stderr)
    receipt["seconds"] = round(time.monotonic() - started, 6)
    receipt["passed"] = len(receipt["tests"])
    encoded = json.dumps(receipt, sort_keys=True)
    print(encoded)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(encoded + "\n", encoding="utf-8")
    return 0 if receipt["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
