# Architecture documentation delivery — 2026-09-06

The delivery adds architecture and integration guides, an offline HTML whitepaper, six SVG graphics, and an independent embedding example.
The documents describe runtime source at `4b3cd5551d80b422ec6ef763627d019e6f1dfb83`.
The server implementation under `src/` remains unchanged.

## Deliverables

- [Architecture](../docs/ARCHITECTURE.md): terms, topology, `main.zig`, scheduling, resource accounting, transport, and shutdown.
- [Integration](../docs/USING.md): dependency setup, lifecycle, callbacks, writer operations, storage lifetimes, and limits.
- [Whitepaper](../docs/whitepaper.html): illustrated design, optimization mechanisms, measurement results, and remaining boundaries.
- [Embedding example](../examples/embedding/src/main.zig): an independently built consumer of the exported `bounded_http` module.
- [Documentation maintenance](../docs/README.md): canonical graphics, reproducible generation, and structural checks.

The four conceptual SVGs describe startup, cluster ownership, request progress, and output layout.
The two performance SVGs derive medians and ranges from the preserved comparison packet.
The renderer verifies archive hashes and compares raw results with published summaries.
The figures introduce no new performance measurements.

## Native development verification

The [receipt](2026-09-06-documentation/receipt.json) identifies source hashes and exact environments.
The development worktree was uncommitted during these checks.
The receipt identifies that boundary explicitly.

macOS used Apple M3 Max, arm64, macOS 26.6.2 build 25G83, and Darwin 25.6.0.
Exact Zig 0.16.0 passed both Debug and ReleaseSafe verification.
Each mode passed 16 build steps and 67 tests.
Each mode skipped two Linux-only tests.

The root verifier now builds the independent consumer and runs its finite HTTP probe.
The probe validates a GET/HEAD/GET pipeline, exact bodies, and final connection closure.
Each mode completed three responses.
Final connection and operation counters were zero.
Late framework allocations, worker dispatches, rejections, and timeouts were zero.
The example requested 3,709,026 peak framework heap bytes within its 16 MiB heap ceiling.
The [Debug log](2026-09-06-documentation/macos-debug.log) and [ReleaseSafe log](2026-09-06-documentation/macos-release-safe.log) preserve raw results.

Linux used `omarx1`, Omarchy 4.0.2, x86_64, kernel 7.1.9-arch1-2, and glibc 2.44.
The kernel reported `io_uring_disabled=0`.
The maintained SSH wrapper passed both native modes with exact Zig 0.16.0.
Each mode passed 16 build steps, 69 tests, and the independent consumer probe.
Linux also passed 84 wire cases, eight comparator tests, and 30,000 exact smoke responses.
The Linux example requested 3,705,746 peak framework heap bytes.

The appended Linux document check exposed a runbook link that required a sibling wiki checkout.
The integration guide now links to the repository URL.
Fresh standalone checkouts passed the document checker on Mac and Linux after that correction.
The checker now rejects relative links outside the HTTP repository.
The [Linux log](2026-09-06-documentation/linux-development.log) preserves the initial failure after successful native gates.
The [Mac recheck](2026-09-06-documentation/standalone-link-recheck.log) and [Linux recheck](2026-09-06-documentation/linux-docs-recheck.json) preserve the correction’s results.

The initial Linux environment collector identified the mise launcher instead of the selected compiler.
The wrapper independently checked `zig version` as 0.16.0 before verification.
The [identity correction](2026-09-06-documentation/linux-compiler.json) records the actual compiler path and SHA-256.
The [Linux summary](2026-09-06-documentation/linux-development-summary.json) preserves native counts and the original document failure.

## Document review

Source review checked the guides against the maintained implementation.
The review corrected partial-send progression, lazy-header scope, per-request continuation state, and HEAD ownership descriptions.
The prose applies the repository's supplied technical-writing policy.
The review does not claim formal ASD-STE100 certification.

Browser review used an isolated Chrome profile on macOS.
Desktop and mobile viewports measured 1440 × 1000 and 390 × 844 pixels.
Neither viewport produced document-level horizontal overflow.
Wide graphics and tables provide their own scrolling areas.

The whitepaper requested no external document assets and produced no uncaught JavaScript exceptions.
The processor selector changed the visible performance figure.
Both figures remained available with JavaScript disabled and in print mode.
The [browser checks](2026-09-06-documentation/browser-checks.json) preserve those results.

`python3 tools/check_docs.py` passed local links, accessible SVG labels, unique identifiers, and generated-document consistency.
Visual inspection covered all four conceptual graphics, both performance figures, and desktop and mobile layouts.

## Evidence boundaries

The performance discussion retains the existing qualified Linux experiment and its environment.
The discussion preserves the one-core depth-128 gap, sample variation, and rejected latency interpretation.
The delivery establishes no new TechEmpower ranking, production capacity, or latency guarantee.
The delivery adds no Windows implementation or Windows runtime evidence.
Remaining API, reliability, platform, and performance work stays in [ROADMAP.md](../ROADMAP.md).
