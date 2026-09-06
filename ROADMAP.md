# bounded/http roadmap

The current deliverable is a working Linux/macOS/Windows MVP to iterate on ownership and
pending/resume. This is a separate project from the evidence wiki.

| Item | State | Boundary |
| --- | --- | --- |
| Fixed startup ownership model | done | One I/O owner per shard, default inline/zero workers or explicit startup workers, one callback per connection with bounded retained response cells, finite mailboxes and operation/cancel storage. |
| HTTP/1.1 parser and reference routes | done | Bounded framing, lazy optional headers, borrowed bodies, plaintext, preloaded HTML, echo and flush/resume. |
| Linux and macOS runtime slice | done | io_uring and kqueue, Debug/ReleaseSafe unit tests and hostile wire/ownership integration; final receipt records environments. |
| Architecture and integration documentation | done | Illustrated guides, an offline HTML whitepaper, packet-derived SVGs, and an independently built embedding example. GitHub Pages publishes the paper and browser-rendered Markdown with syntax highlighting. |
| Project naming | done | Public brand `bounded/http`; repository and executable `bounded-http`; Zig package and module `bounded_http`. Historical evidence retains its original identity. |
| Experiment API | partial | PR #3 adds `Context.flushAndWait()` for same-callback streaming on fixed workers. The existing return-and-resume API remains available. Native correctness and focused streaming cases passed on all three platforms. Remaining: compare continuations with alternatives, add finish/cancel release notifications for dynamic leases, and consider arbitrary app task integration. |
| Scheduling/copy improvements | partial | Direct Linux operation cells and configurable batch/callback budgets were measured on the pre-arena implementation (reports/2026-09-05-operation-cells.md, reports/2026-09-05-batch-quantum.md). The adopted arena/shard base (reports/2026-09-05-arena-adoption.md; original reference report preserved) supersedes them: output arena with heads written at begin, ready-ring scheduler, lane-scanning parser, cell-addressed transport with caller-owned vectors, and a reuse-port shard cluster, gated on Mac/Linux. Adoption hardens worker cache ownership, prearmed EOF/interim ordering, partial startup and secondary-shard failure, with exact coordinator/stack accounting. Remaining: profiled per-request efficiency at one core (parser attribution unproven), SINGLE_ISSUER/DEFER_TASKRUN ring modes, macOS shard distribution. |
| Reliability qualification | queued | Startup-failure and forced completion-order witnesses now exist. Remaining: broader deterministic fault/schedule injection, long mixed maximum-load runs, syscall failure catalog, full process/kernel resource accounting and shutdown diagnostics. |
| Windows HTTP adapter | done | Experimental IOCP adapter; native x64 Windows Server 2025 gate passed Debug/ReleaseSafe, 80 wire cases, and 30,000 exact smoke responses. Four POSIX suspension fixtures remain excluded. The 2026-09-06 Windows receipt preserves source identity, ownership limits, watchdogs, and raw results. Physical deployment and Windows performance remain unqualified. |
| Windows shard distribution | done | One exclusive listener, startup-bounded socket handoff, independent destination IOCPs, shared admission across transit and queued sockets, original deadlines, and publication-aware shutdown. Native x64 Debug/ReleaseSafe and nine additional wire cases passed. PR #2 merged at `1c74a4e`; its tree equals tested `419de544`. Explicit inline shard counts: 1–64; default: 1. Native fixtures cover 1–4. No Windows throughput or physical deployment qualification. |
| Comparative performance | partial | Pinned Linux mrhttp/libreactor comparison: 54 main + 18 client-sensitivity trials; inline and gather A/B sweeps preserved separately. Batch1/16 and one-core comparisons are complete; client depths32/64/128 and a separate recorded-performance-profile sweep are complete. Preserve the unresolved fixed-batch gap and prior unknown-profile observations. The integrated arena/shard candidate adds36 qualified Linux trials: three-core Zig/libreactor median ratios0.957/0.909/0.860 at depths1/16/128, one-core1.106/0.778/0.596; raw ranges and ownership checks retained. Remaining: HTML/Mac comparisons, dedicated-host/NIC saturation and qualified request tails; wrk corrected percentiles were rejected. |
| Higher-level features | queued | TLS boundary, routing/middleware, upload protocol and application state APIs after the core experiment. |

The wiki's M3-006 Windows deployment qualification stays postponed by user
decision. It is distinct from this project's native Windows HTTP slice.

Current cadence: macOS correctness and Linux runtime/performance, with Windows
HTTP builds and hosted runtime gates explicitly resumed on 2026-09-06. Coordinate host
load via `/tmp/zig-http-measurement.lock`; another agent also measures on the Mac.
The performance-profile sweep is complete; no queued architecture experiment is
an active agent or runner.
