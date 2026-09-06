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
The [writing policy](https://github.com/technologylab-ai/zigllmwiki/blob/main/docs/technical-writing.md) applies to repository prose.
Code identifiers and exact-format text remain exempt.
