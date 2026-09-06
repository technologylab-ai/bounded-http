#!/usr/bin/env python3
"""Serve repository files and route browser text navigation through the reader."""

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import socket
from urllib.parse import parse_qs, quote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = frozenset((".md", ".zig", ".py", ".json", ".sh"))


class DocumentationHandler(SimpleHTTPRequestHandler):
    def browser_navigation(self):
        mode = self.headers.get("Sec-Fetch-Mode")
        if mode:
            return mode.lower() == "navigate"
        for accepted in self.headers.get("Accept", "").split(","):
            fields = [field.strip().lower() for field in accepted.split(";")]
            if fields[0] not in ("text/html", "application/xhtml+xml"):
                continue
            quality = next((field[2:] for field in fields[1:] if field.startswith("q=")), "1")
            try:
                if float(quality) > 0:
                    return True
            except ValueError:
                continue
        return False

    def send_head(self):
        request = urlsplit(self.path)
        raw = "1" in parse_qs(request.query).get("raw", ())
        if not raw and self.browser_navigation():
            path = Path(self.translate_path(self.path))
            if path.suffix.lower() in TEXT_SUFFIXES and path.is_file():
                relative = path.relative_to(Path(self.directory)).as_posix()
                location = "/docs/read.html?file=" + quote(relative, safe="/")
                # Browsers retain the original fragment when Location omits one.
                self.send_response(302)
                self.send_header("Location", location)
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return None
        return super().send_head()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--directory", type=Path, default=ROOT)
    args = parser.parse_args()
    directory = args.directory.resolve()
    if not directory.is_dir():
        parser.error("--directory must name an existing directory")
    if not 0 <= args.port <= 65535:
        parser.error("--port must be between 0 and 65535")
    family, _, _, _, address = socket.getaddrinfo(
        args.bind, args.port, type=socket.SOCK_STREAM, flags=socket.AI_PASSIVE
    )[0]

    class Server(ThreadingHTTPServer):
        address_family = family

    handler = partial(DocumentationHandler, directory=str(directory))
    with Server(address, handler) as server:
        host, port = server.server_address[:2]
        host = "[{}]".format(host) if ":" in host else host
        print("Serving {} at http://{}:{}/".format(directory, host, port), flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
