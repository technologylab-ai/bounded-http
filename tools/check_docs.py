#!/usr/bin/env python3
"""Check documentation links, accessible SVGs, and the offline whitepaper."""
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET
from urllib.parse import parse_qs, unquote, urlsplit

from render_whitepaper import render

ROOT = Path(__file__).resolve().parents[1]
errors = []


class Document(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.links = []
        self.references = []
        self.svg_count = 0

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if 'id' in values:
            self.ids.append(values['id'])
        if tag == 'a' and 'href' in values:
            self.links.append(values['href'])
        for attr in ('aria-labelledby', 'aria-describedby'):
            self.references.extend(values.get(attr, '').split())
        if tag == 'svg':
            self.svg_count += 1
            if values.get('role') != 'img' or not values.get('aria-labelledby'):
                errors.append('Inline SVG lacks an accessible name.')
        if tag in ('script', 'img', 'iframe', 'link'):
            resource = values.get('src') or values.get('href')
            if resource:
                errors.append('Whitepaper has an external asset: ' + resource)


def check_link(path, href, ids=None):
    url = urlsplit(href)
    if url.scheme or url.netloc:
        return
    target = (path.parent / unquote(url.path)).resolve() if url.path else path
    if not target.is_relative_to(ROOT):
        errors.append('{}: relative link leaves this repository: {}'.format(path.relative_to(ROOT), href))
    if url.path.endswith('read.html'):
        requested = parse_qs(url.query).get('file', [''])[0]
        source = (ROOT / requested).resolve()
        if not requested or not source.is_relative_to(ROOT) or not source.is_file():
            errors.append('Reader link has an invalid document: ' + href)
    if not target.exists():
        errors.append('{}: missing {}'.format(path.relative_to(ROOT), href))
    if url.fragment and target == path and ids is not None and unquote(url.fragment) not in ids:
        errors.append('{}: missing anchor {}'.format(path.relative_to(ROOT), href))


paper = ROOT / 'docs/whitepaper.html'
body = paper.read_text()
if body != render():
    errors.append('Whitepaper differs from the template and SVGs.')
if '<!-- diagram:' in body:
    errors.append('Whitepaper contains an unresolved diagram placeholder.')
document = Document()
document.feed(body)
for value, count in Counter(document.ids).items():
    if count > 1:
        errors.append('Duplicate HTML/SVG id: ' + value)
for value in document.references:
    if value not in document.ids:
        errors.append('Missing accessible label: ' + value)
for href in document.links:
    check_link(paper, href, document.ids)
for reference in re.findall(r'url\(#([^\)]+)\)', body):
    if reference not in document.ids:
        errors.append('Missing SVG reference: ' + reference)
svg_files = sorted((ROOT / 'docs/diagrams').glob('*.svg'))
for path in svg_files:
    svg = ET.parse(path).getroot()
    if not svg.get('viewBox') or svg.get('role') != 'img' or not svg.get('aria-labelledby'):
        errors.append(path.name + ': missing viewport or accessible name.')
if document.svg_count != len(svg_files):
    errors.append('Whitepaper does not include every canonical SVG exactly once.')
for name in ('README.md', 'docs/README.md', 'docs/ARCHITECTURE.md', 'docs/USING.md'):
    path = ROOT / name
    source = re.sub(r'```[\s\S]*?```', '', path.read_text())
    for href in re.findall(r'!?\[[^\]]*\]\(([^\s\)]+)\)', source):
        check_link(path, href)
if errors:
    print('\n'.join(errors), file=sys.stderr)
    raise SystemExit(1)
print('Documentation links, {} accessible SVGs, unique IDs, and offline generation pass.'.format(len(svg_files)))
