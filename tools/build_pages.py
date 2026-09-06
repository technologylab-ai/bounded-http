#!/usr/bin/env python3
"""Build the GitHub Pages artifact from an explicit documentation allowlist."""
import hashlib
import html
import json
from pathlib import Path, PurePosixPath
import posixpath
import re
import shutil
import subprocess
from urllib.parse import parse_qs, quote, unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / '.zig-cache/github-pages'
DOCUMENTS = ['docs/ARCHITECTURE.md', 'docs/USING.md']
DIAGRAMS = ['docs/diagrams/' + name + '.svg' for name in
            ('topology', 'startup', 'request-lifecycle', 'output-arena')]
READER = ['docs/read.html', 'docs/reader.js', 'docs/reader.css']


def build():
    subprocess.run(['python3', 'tools/check_docs.py'], cwd=ROOT, check=True)
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    if not re.fullmatch('[0-9a-f]{40}', revision):
        raise ValueError('Expected a full publication commit.')
    repository = 'https://github.com/technologylab-ai/zig-http/blob/' + revision + '/'
    directories = {'tests', 'reports'}
    vendor = json.loads((ROOT / 'docs/vendor/manifest.json').read_text())
    vendor_files = ['docs/vendor/manifest.json']
    for package in vendor:
        for filename, digest in package['files_sha256'].items():
            path = 'docs/vendor/' + filename
            if hashlib.sha256((ROOT / path).read_bytes()).hexdigest() != digest:
                raise ValueError('Vendor checksum mismatch: ' + path)
            vendor_files.append(path)
    files = DOCUMENTS + DIAGRAMS + READER + vendor_files
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    OUTPUT.mkdir(parents=True)
    for name in files:
        destination = OUTPUT / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, destination)
    assets = DIAGRAMS + ['docs/whitepaper.html']
    config = {'public': True, 'documents': DOCUMENTS, 'assets': assets,
              'repository': repository, 'directories': sorted(directories)}
    (OUTPUT / 'docs/site-config.js').write_text('window.DOC_SITE = ' + json.dumps(config) + ';\n')
    paper = (ROOT / 'docs/whitepaper.html').read_text()

    def links(match):
        original = html.unescape(match.group(1))
        url = urlsplit(original)
        if url.scheme or url.netloc or not url.path:
            return match.group(0)
        path = posixpath.normpath('docs/' + unquote(url.path))
        if path == 'docs/read.html':
            file = parse_qs(url.query).get('file', [''])[0]
            if file not in DOCUMENTS:
                result = repository + quote(file, safe='/') + ('#' + url.fragment if url.fragment else '')
                return 'href="' + html.escape(result, quote=True) + '"'
        elif path not in files + assets:
            result = repository + quote(path, safe='/') + ('#' + url.fragment if url.fragment else '')
            return 'href="' + html.escape(result, quote=True) + '"'
        return match.group(0)

    paper = re.sub(r'href="([^"]+)"', links, paper)
    (OUTPUT / 'docs/whitepaper.html').write_text(paper)

    def root_links(match):
        href = html.unescape(match.group(1))
        url = urlsplit(href)
        if url.scheme or url.netloc or not url.path:
            return match.group(0)
        return 'href="' + html.escape('docs/' + href, quote=True) + '"'

    (OUTPUT / 'index.html').write_text(re.sub(r'href="([^"]+)"', root_links, paper))
    (OUTPUT / '.nojekyll').write_text('')
    allowed = set(files + ['docs/site-config.js', 'docs/whitepaper.html', 'index.html', '.nojekyll'])
    actual = {str(path.relative_to(OUTPUT)) for path in OUTPUT.rglob('*') if path.is_file()}
    if actual != allowed:
        raise ValueError('Unexpected Pages artifact files: ' + repr(actual ^ allowed))
    print('Pages artifact: {} files, publication {}, {}'.format(len(actual), revision, OUTPUT))


if __name__ == '__main__':
    build()
