#!/usr/bin/env python3
"""Exercise the consuming project with finite GET/HEAD and ownership checks.

Acquire the shared host reservation before invoking this runtime gate.
The probe validates an application example, not general HTTP behavior.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import signal
import socket
import subprocess
import tempfile
import time


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def read_log(path):
    with path.open('rb') as stream:
        return stream.read(65536)


def response(stream, method):
    status = stream.readline(8193)
    require(status == b"HTTP/1.1 200 OK\r\n", "unexpected response status")
    headers = {}
    total = len(status)
    while True:
        line = stream.readline(8193)
        total += len(line)
        require(total <= 8192 and line.endswith(b"\r\n"), "invalid or oversized response head")
        if line == b"\r\n":
            break
        name, value = line[:-2].split(b":", 1)
        name = name.lower()
        require(name not in headers, "duplicate response header")
        headers[name] = value.strip()
    require(headers.get(b"content-length") == b"13", "wrong logical body length")
    require(headers.get(b"content-type") == b"text/plain", "wrong response type")
    require(b"date" in headers and b"transfer-encoding" not in headers, "wrong response framing")
    if method != "HEAD":
        require(stream.read(13) == b"Hello, World!", "wrong response body")
    return headers


def check(binary):
    started = time.monotonic()
    command = [str(binary), "--port", "0", "--duration-ms", "1500"]
    with tempfile.TemporaryDirectory(prefix="bounded-http-embedding-") as directory, (Path(directory) / "server.log").open("w+b") as log:
        log_path = Path(directory) / "server.log"
        process = subprocess.Popen(command, stdout=log, stderr=log,
                                   start_new_session=(os.name == "posix"))
        try:
            ready = None
            deadline = started + 10
            while time.monotonic() < deadline:
                ready = re.search(rb"^READY port=(\d+)$", read_log(log_path), re.MULTILINE)
                if ready:
                    break
                require(process.poll() is None, "example exited before READY")
                time.sleep(0.01)
            require(ready is not None, "example did not announce readiness")
            port = int(ready.group(1))
            require(0 < port <= 65535, "example did not bind an ephemeral port")
            with socket.create_connection(("127.0.0.1", port), timeout=2) as connection:
                connection.settimeout(2)
                methods = ("GET", "HEAD", "GET")
                request = b"".join(
                    (method + " /example HTTP/1.1\r\nHost: localhost\r\n" +
                     ("Connection: close\r\n" if index == 2 else "") + "\r\n").encode()
                    for index, method in enumerate(methods)
                )
                connection.sendall(request)
                with connection.makefile("rb") as stream:
                    for method in methods:
                        headers = response(stream, method)
                    require(headers.get(b"connection") == b"close", "close barrier was lost")
                    require(stream.read(1) == b"", "unexpected bytes after the final response")
            process.wait(timeout=max(0.01, deadline - time.monotonic()))
            output = read_log(log_path).decode()
            require(process.returncode == 0, "example exited unsuccessfully: " + output)
            stats_lines = [line[6:] for line in output.splitlines() if line.startswith("STATS ")]
            require(len(stats_lines) == 1, "missing or duplicate final STATS")
            stats = json.loads(stats_lines[0])
            require(stats["completed"] == 3, "wrong completed response count")
            require(stats["execution"] == "inline_event_loop", "wrong callback execution mode")
            require(stats["shards"] == 1 and stats["workers"] == 0, "wrong example topology")
            for name in ("allocation_calls_after_start", "live_connections", "live_operations",
                         "worker_dispatches", "rejected", "timeouts"):
                require(stats[name] == 0, "nonzero final counter: " + name)
            require(0 < stats["framework_heap_peak_bytes"] <= stats["framework_heap_limit_bytes"],
                    "framework heap escaped its budget")
            return dict(ok=True, command=command, platform=platform.platform(),
                        binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
                        exact_responses=3, methods=list(methods), stats=stats,
                        elapsed_seconds=time.monotonic() - started, server_log=output)
        finally:
            if process.poll() is None:
                if os.name == "posix":
                    os.killpg(process.pid, signal.SIGTERM)
                else:
                    process.terminate()
                try:
                    process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    if os.name == "posix":
                        os.killpg(process.pid, signal.SIGKILL)
                    else:
                        process.kill()
                    process.wait(timeout=2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    args = parser.parse_args()
    def watchdog(signum, frame):
        raise TimeoutError("embedding probe exceeded its twelve-second watchdog")
    if hasattr(signal, "SIGALRM"):
        signal.signal(signal.SIGALRM, watchdog)
        signal.alarm(12)
    try:
        print(json.dumps(check(args.binary.resolve()), sort_keys=True))
    finally:
        if hasattr(signal, "SIGALRM"):
            signal.alarm(0)


if __name__ == "__main__":
    main()
