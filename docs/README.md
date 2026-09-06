# Documentation map

Read the [architecture guide](ARCHITECTURE.md) for concepts, startup order, ownership, resource accounting, and shutdown.
Read the [integration guide](USING.md) to embed the framework and implement callbacks.
Open the [whitepaper](whitepaper.html) in a browser for the illustrated design and performance discussion.
The HTML document works offline and includes all six SVG graphics.

The [ownership contract](OWNERSHIP.md) records the detailed storage and cancellation rules.
The [performance design](PERF-ARCHITECTURE.md) preserves the arena/shard experiment's implementation rationale.
The [qualified comparison](../reports/2026-09-05-arena-adoption.md) records measurements and their limits.

## Maintain the documents

Keep conceptual diagrams in [diagrams/](diagrams/topology.svg).
Edit [whitepaper.template.html](whitepaper.template.html), then regenerate the standalone document:

```sh
python3 tools/render_whitepaper.py
python3 tools/check_docs.py
```

Run these commands from the repository root.
The generator embeds canonical SVGs without external assets.
The checker validates local links, accessible graphic labels, unique identifiers, and generated content.
Review prose and source accuracy separately.

The performance figures derive from the preserved comparison packet.
Their renderer requires CPython 3.12.3, Matplotlib 3.9.4, and NumPy 2.5.2.
Run the renderer in an isolated environment:

```sh
uv run --python 3.12.3 --with matplotlib==3.9.4 --with numpy==2.5.2 python tools/render_performance_figures.py
python3 tools/render_whitepaper.py
```

The renderer performs no runtime measurements.
Preserve source revisions, environments, sample ranges, and measurement limits when updating performance prose.
The [writing policy](https://technologylab-ai.github.io/zigllmwiki/?page=docs/technical-writing.md) applies to repository prose.
Code identifiers and exact-format text remain exempt.

## Read and publish on the web

The [public site](https://technologylab-ai.github.io/zig-http/) serves the whitepaper and its architecture and integration guides.
The browser reader renders Markdown, tables, heading links, diagrams, and highlighted code.
Source and evidence links open the public GitHub repository at the deployment revision.
Wiki navigation opens the [standalone wiki reader](https://technologylab-ai.github.io/zigllmwiki/).
Use its `page` query parameter with a wiki repository path for new viewing links.
Preserve immutable GitHub revision links when citing pinned evidence.
The standalone whitepaper remains readable without JavaScript.
The Markdown reader requires JavaScript and an HTTP server.

For local browsing, run:

```sh
python3 tools/serve_docs.py --bind 127.0.0.1 --port 8766
```

The server converts document navigation into reader URLs.
The reader requests original bytes with `raw=1`.
Select a Tailscale address with `--bind` to browse from another device.

Build the publication artifact with:

```sh
python3 tools/build_pages.py
```

The builder selects explicit documents and reader assets into `.zig-cache/github-pages`.
The Pages workflow publishes that directory after relevant changes reach `main`.
The workflow also supports manual dispatch.
The workflow does not run Zig compilation or performance measurements.

The reader vendors Marked, DOMPurify, and Highlight.js.
[The vendor manifest](vendor/manifest.json) pins package versions, archive integrity, and extracted file hashes.
Adjacent license files preserve each dependency's license terms.
The site uses no external script or stylesheet service.
The Zig highlighting rules follow the exact 0.16.0 tokenizer keywords.
