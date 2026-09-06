#!/usr/bin/env python3
"""Build the offline whitepaper from its template and canonical SVG diagrams."""
import argparse
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]

def render():
    source = (ROOT / 'docs/whitepaper.template.html').read_text()
    def diagram(match):
        name = match.group(1)
        svg = (ROOT / 'docs/diagrams' / (name + '.svg')).read_text()
        svg = re.sub(r'<\?xml[^>]*\?>', '', svg)
        svg = re.sub(r'<!DOCTYPE[\s\S]*?\]>', '', svg)
        svg = re.sub(r'<!DOCTYPE[^>]*>', '', svg)
        return svg.strip()
    return re.sub(r'<!-- diagram: ([a-z0-9-]+) -->', diagram, source)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    path = ROOT / 'docs/whitepaper.html'
    result = render()
    if args.check:
        if not path.exists() or path.read_text() != result:
            raise SystemExit('Whitepaper differs. Run python3 tools/render_whitepaper.py.')
        print('Whitepaper matches its template and canonical diagrams.')
    else:
        path.write_text(result)
        print(path)
