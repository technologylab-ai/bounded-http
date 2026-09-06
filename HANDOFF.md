# Windows shards merged — 2026-09-06

[PR #2](https://github.com/technologylab-ai/bounded-http/pull/2) merged with explicit user approval.
Merge commit: `1c74a4e379c365ec0a201e6fe3df1a5a9718d504`.
Its Git tree exactly matches verified feature commit `419de5445901a87ea6973020df5b13a420917483`.
The canonical `bounded-http` checkout is on synced main; other worktrees can fast-forward from origin/main.
The preserved feature worktree is `../bounded-http-windows-shards`, branch `feat/windows-shards`.

[Final Windows run 34044844060](https://github.com/technologylab-ai/bounded-http/actions/runs/34044844060) passed against the feature commit before merge.
The merge introduces no source difference; it is not a separate runtime execution.
Final macOS and Linux Debug/ReleaseSafe, wire, comparator, embedding, and exact-body smoke gates also passed on that feature commit.
The [merge Pages deployment](https://github.com/technologylab-ai/bounded-http/actions/runs/34045683304) passed.
This follow-up changes only the durable handoff and roadmap completion state.

Shard zero owns one exclusive listener and processes its own round-robin share.
Secondary owners receive unassociated sockets through startup-fixed queues before receiving request bytes.
Shared admission includes queued sockets and sockets moving between owners.
A publication barrier prevents receivers from exiting before the last possible queue entry.
Each original acceptance deadline survives transfer.
The callback, writer, Linux scheduling, and macOS topology contracts remain unchanged.

The [new receipt](reports/2026-09-06-windows-shards.md) pins candidate `514c901fafd005f140a0a6fdf10ee28d0ff8796a`.
[Native Windows run 34043829095](https://github.com/technologylab-ai/bounded-http/actions/runs/34043829095) passed exact Zig 0.16.0 Debug and ReleaseSafe.
Each mode passed 16 steps and 95 tests, with four explicit POSIX skips.
Windows passed 89 wire cases, four explicit POSIX wire skips, nine comparator cases, and 30,000 exact smoke responses.
Both embedding probes passed; final ownership and late allocation counters were zero.
The immutable raw packet includes source hashes, hosted metadata, commands, watchdogs, and artifact digest.

The same candidate passed Linux Debug and ReleaseSafe with 82 tests and two Windows skips per mode.
Linux passed 84 wire cases, nine comparator cases, both embedding probes, and 30,000 exact smoke responses.
The native Windows fixtures exercise one through four owners; higher configured counts lack separate runtime coverage.
Windows remains one shard by default; explicit inline configurations permit up to 64 within the resource budget.
Worker execution and macOS remain single-shard.
Windows throughput and physical deployment remain unqualified.

The illustrated architecture and whitepaper now include a seventh SVG for Windows handoff.
The documentation reader includes the new native shard receipt.
Final publication gates belong to the PR's exact pushed feature commit; consult its checks and description.
Do not reinterpret this candidate receipt as evidence for an unidentified later source tree.

Wiki synchronization is published in [commit `a48ddf3`](https://github.com/technologylab-ai/zigllmwiki/commit/a48ddf3ce6d956b4f7e1e0db6a7a31e403c0d27f).
The [HTTP design page](https://technologylab-ai.github.io/zigllmwiki/?page=wiki/bounded-http-server-design.md) links the merged implementation and pinned feature-runtime evidence.
The wiki preserves the final native Windows archive, qualified source inputs, and immutable historical packets.
Exact wiki publication receipts remain in `../zigllmwiki-windows-shards/.zig-cache/windows-shards-publication/summary.json`.
Do not rewrite earlier immutable source records or treat the merge as another Windows test run.
The wiki's M3-006 remains postponed.
The [roadmap](ROADMAP.md) still contains API, reliability, performance, and higher-level work.

An unrelated Baz website request reached this session and was stopped at the user's correction.
Its separate handoff is `../baz-website/BAZ-WEBSITE-HANDOFF.md`, commit `99729c3222cc4449a37f6a6b283b5b6f0cccc27a`.
No Baz implementation, dependency change, remote, or publication was made by this session.
Preserve both Baz worktrees and resume Baz only in its intended session.

The historical checkpoints below describe their original revisions and retain their earlier scope.

# Windows HTTP and platform documentation handoff — 2026-09-06

The experimental Windows IOCP adapter is implemented and native x64 verification passed.
The whitepaper and Markdown reader now show `ZIG 0.16.0` above `LINUX + MACOS + WINDOWS`.
The architecture, integration, ownership, and evidence guides describe Windows limits and shutdown.
The byline remains “for servers that stay within their bounds”.

The [Windows report](reports/2026-09-06-windows-iocp.md) preserves raw evidence and exact environments.
Clean pushed candidate `70f9ae5917076b664081db59c62edc4959ca5041` passed native Windows run [34039591972](https://github.com/technologylab-ai/bounded-http/actions/runs/34039591972).
Windows Debug and ReleaseSafe each passed 16 steps and 83 tests, with six explicit skips.
Windows passed 80 wire cases, nine comparator tests, both embedding probes, and 30,000 exact smoke responses.
Four maximum-cell wire fixtures require POSIX suspension and remain excluded on Windows.
The first run's Python suspension failure is preserved separately; its overall result remains failed.

The same candidate passed both Mac and Linux native regression gates.
Each host passed 84 wire cases, nine comparator tests, both embedding probes, and 30,000 exact smoke responses.
Mac passed 78 tests with two Linux-only skips per mode; Linux passed all 80 tests per mode.
Both host reservations were released after owned process cleanup.
Eight development browser checks passed, including both Windows labels and the native receipt reader.
Publication gates rerun on the final pushed main revision; use the recorded workflow commit when evaluating later runs.

Windows remains one shard, IPv4 loopback, and ordinary copied socket I/O.
The socket table bounds owned handles; provider allocation and delayed TCP cleanup remain outside framework heap accounting.
Windows performance, ARM64, service controls, physical deployment, and the wiki's M3-006 remain unqualified or postponed.
The [roadmap](ROADMAP.md) still contains API, reliability, performance, and higher-level work.
This delivery does not complete M4.

PR #1 and the `bounded_http` response reservation API remain merged.
The canonical directory is `../bounded-http`; `../zig-http` remains a compatibility symlink.
Keep `/tmp/zig-http-measurement.lock` unchanged and preserve other agents' worktrees.
The Tailscale documentation server remains available through the compatibility path.
The prior checkpoints below retain their original names, dates, and evidence scope.

# bounded/http rename handoff — 2026-09-06

The user selected **bounded/http** as the public name.
The byline is “for servers that stay within their bounds”.
The whitepaper keeps “Fast by design. Explicit about limits.”

The repository, canonical directory, executable, and HTTP Server token use `bounded-http`.
The Zig package, embedding dependency, and exported module use `bounded_http`.
The canonical repository is [technologylab-ai/bounded-http](https://github.com/technologylab-ai/bounded-http).
The [published whitepaper](https://technologylab-ai.github.io/bounded-http/) uses the new project path.
The [wiki design page](https://technologylab-ai.github.io/zigllmwiki/?page=wiki/bounded-http-server-design.md) records the same naming decision.

Current commands and tooling use the new executable path.
The comparison harness recognizes both current and historical implementation names.
Archived measurements, report bytes, and pinned source identities retain `zig-http`.
The displayed performance figures still describe those earlier binaries.
The rename adds no throughput measurement or production qualification.

The canonical Mac checkout is `../bounded-http`.
The old `../zig-http` path remains a compatibility symlink for existing tools and active worktrees.
Other agents own their existing worktrees; do not reset or rename those directories.
Git worktree metadata remains reachable through the compatibility path.
Update other clones with `git remote set-url origin git@github.com:technologylab-ai/bounded-http.git`.
Keep `/tmp/zig-http-measurement.lock` unchanged on both hosts.
Changing that shared path would let old and new agents run simultaneously.
The existing Tailscale documentation server continues through the compatibility path.

Verification and publication results are recorded in [the rename receipt](reports/2026-09-06-bounded-http-name.md).
Mac development passed 78 tests per mode, two Linux-only skips, 84 wire cases, nine comparator checks, and 30,000 smoke responses.
Seven HTTP and thirteen wiki browser checks passed.
Linux publication verification remains pending the available reservation.
Windows HTTP work has resumed separately on `feat/windows-iocp`.
Remaining API, reliability, and performance work stays in [ROADMAP.md](ROADMAP.md).
PR #1 merged at `c90281b600deb699a667e2bcc115da32862c794f` before the remaining source rename.
Its response-draft API remains intact, and the whitepaper now explains reservation before callbacks.
The older checkpoints below preserve their original names and evidence scope.

# HTTP documentation handoff — 2026-09-06

The architecture documentation is on main; preserve the earlier `docs/server-architecture` worktree.
The `docs/github-pages` branch adds the public site and Markdown reader.
Both the HTTP and wiki repositories are public by the user’s 2026-09-06 authorization.
The whitepaper and guides link to the [standalone wiki](https://technologylab-ai.github.io/zigllmwiki/).
Wiki links use its `page` query parameter and preserve Markdown heading fragments.
Pinned evidence retains its original revision links.
The [Pages site](https://technologylab-ai.github.io/zig-http/) publishes through `.github/workflows/pages.yml`.
Run `python3 tools/build_pages.py` to check the explicit publication artifact.
Run `python3 tools/serve_docs.py` for local Markdown and highlighted-source browsing.
The delivery extends the arena/shard implementation already adopted into main.
Runtime source under `src/` remains identical to publication `4b3cd5551d80b422ec6ef763627d019e6f1dfb83`.
Preserve all earlier reference branches and worktrees.

Start with [the architecture guide](docs/ARCHITECTURE.md), [integration guide](docs/USING.md), and [offline whitepaper](docs/whitepaper.html).
The whitepaper embeds six accessible SVGs and supports desktop, mobile, print, and reading without JavaScript.
The [independent embedding example](examples/embedding/src/main.zig) demonstrates dependency setup and the complete bounded lifecycle.
The root verifier compiles that consumer and checks its finite GET/HEAD/GET pipeline.

Edit `docs/whitepaper.template.html` and canonical SVGs under `docs/diagrams/`.
Run `python3 tools/render_whitepaper.py`, then `python3 tools/check_docs.py`.
The [documentation maintenance page](docs/README.md) pins plotting dependencies and explains regeneration.
The wiki now preserves the user's Simplified Technical English and Zinsser writing policy.

[Documentation validation](reports/2026-09-06-documentation.md) records source hashes, environments, and development checks.
Mac Debug and ReleaseSafe each passed 16 build steps, 67 tests, and the independent consumer probe.
Two Linux-only tests were skipped per Mac mode.
The browser review passed offline loading, chart selection, print visibility, and mobile overflow checks.
Linux Debug and ReleaseSafe each passed 16 build steps, 69 tests, and the independent consumer probe.
Linux also passed 84 wire cases, eight comparator tests, and 30,000 exact smoke responses.
A standalone checkout passed document checks after correcting a sibling-only runbook link.
No new benchmark measurements accompany this delivery.

Continue with the unfinished [roadmap items](ROADMAP.md).
Priorities include profiling one-core efficiency, dynamic lease release, optional offload, and broader reliability qualification.
HTML, macOS contender, external-network, and qualified response-tail comparisons remain queued.
Windows HTTP remains unimplemented; Windows tuning stays deferred, and wiki M3-006 remains postponed.
This documentation delivery does not complete M4.

Acquire `/tmp/zig-http-measurement.lock` before heavy builds, runtime suites, or browser rendering on either host.
Use the sibling wiki's `docs/platform-testing.md` for reservation metadata and remote-run commands.
A queued roadmap item does not identify an active agent or runner.

## Historical handoff: arena/shard adoption

# HTTP experiment handoff — 2026-09-05

Arena/shard adoption is the current base on `integrate/arena-shards` in
`zig-http-arena-integration`. Measured/hardened source is pushed
**bbcec8aa9516efc470238b9edeea4f01b1f4a6d7**, descended from the external
`perf/arena-shards-plus-main` at d5b6d9b. Original reference branches and external
worktrees remain unchanged and are pushed. The separate wiki proposal is
merged into its integration branch with navigation restored and claims audited.

[Adoption evidence](reports/2026-09-05-arena-adoption.md) preserves all36 qualified
Linux trials:1,053,649,993 timed responses and3,840 exact preflights. With three
server CPUs, Zig/libreactor ratios of medians are0.957/0.909/0.860 at depths
1/16/128. One CPU gives1.106/0.778/0.596; depth128 remains a substantial
efficiency gap, whose cause requires profiling. No client-bottleneck or
parser-only causal conclusion is established. Desktop/power endpoints and
full ranges remain in the packet; no wrk tail/SLO claim is valid.

Clean pushed bbcec8a passed both native gates: Mac67/69tests per mode with
2Linux-only skips, Linux69/69,84wire cases,8comparator tests and30k exact smoke
bodies on each. New witnesses cover worker header-cache ownership, EOF/interim
completion ordering, exact16callback clock groups, partial shard startup,
secondary-shard failure and exact coordinator/stack budgets. Framework
requested heap is29,635,986bytes/88,907,590bytes at1/3shards; admission remains
process-wide128 while each shard reserves full slot capacity. Inline handlers
can run concurrently across shards and must synchronize shared application state.

Both timed blocks finished and the Linux reservation was released after child
cleanup. The extraction compatibility failure was recovered from the original
raw download without rerunning load. Final publication repeats native gates
on the clean pushed main commit; its durable receipt belongs in the wiki.
No queued follow-up implies an active runner. Preserve shared
`/tmp/zig-http-compare.PIwh35` and all named worktrees. Future load must reacquire
the host-local measurement lock. Windows tuning stays deferred; M3-006 postponed.

Remaining work: profiled one-core efficiency, lease release/optional offload,
broader fault and combined-limit qualification, HTML/Mac/NIC/tail comparisons
and Windows HTTP. This adoption does not complete M4. The older handoff below
is historical; its defaults and queued-sharding statements are superseded.

Completed performance work is consolidated on `perf/batch-quantum` in
`/Users/rs/code/github.com/technologylab.ai/zig-http-batchq` before main publication.
Direct operation cells are preserved at adf24f380ac56b2ae142e514a1491be1e08d4a20
on `perf/direct-operation-cells` / `zig-http-opcells`. Batch/quantum measured
source is dbb639859e4c8503310933a2e53f0aaf45e2fca0. Both named worktrees and
pushed branches are durable; `git worktree list` locates them after interruption.

[Operation-cell evidence](reports/2026-09-05-operation-cells.md): both native
gates passed 58 tests/mode,69 wire cases,8 comparator tests and30,000 smoke bodies.
All 48 Linux paired trials passed. At 128 active clients,1024 reserved connections
improved median throughput76%/29%/17% at depths1/16/128;128 reserved connections
improved14%/4%/5%. Cold binding/close scans remain; startup heap is unchanged.

[Batch/callback evidence](reports/2026-09-05-batch-quantum.md): both native gates
passed 59 tests/mode,77 wire cases,8 comparator tests and30,000 smoke bodies.
All 24 same-binary matrix trials passed. At client depth128, B16/Q64 measured
1.951M/s and B64/Q256 2.780M/s; full ranges remain in the packet. Requested heap
is 31,100,880/59,805,648 bytes at B16/B64; Q alone adds no heap. Defaults16/64
remain. Tests exercised320 native spans,64 retained cells during cancellation,
partial/flush/close order, and bounded cold service amid seven hot pipelines.

Implementation/platform agents and both timed runners finished; all owned
measurement locks were released. The evidence agent finished and verified both complete packets. Parent owns
final publication gates; measured/native source is unchanged by the doc merge. No queued roadmap
item implies a running agent. API release/offload, fault/combined-limit
qualification, output representation/sharding, Mac/HTML/NIC/tail comparisons
and Windows HTTP remain queued; this does not complete M4.

The external `.claude/worktrees/perf-architecture` remains independent and
untouched. Preserve shared `/tmp/zig-http-compare.PIwh35` tools: that agent also
borrows wrk/libreactor. Acquire the host-local `/tmp/zig-http-measurement.lock`
atomically before future builds/runtime/timing, check pre-existing processes,
and hold through child cleanup. Windows tuning gates are deferred by the user.

## Historical evidence before this batch/quantum experiment

Latest measurement: [recorded performance-profile depth sweep](reports/2026-09-05-power-profile.md)
at exact bda54040bb0b809c82824b87a782e96826f05dff, Zig 0.16.0 ReleaseSafe.
All 24 trials/warmups passed: 643,222,112 timed responses, 2,880 exact preflights.
One-core Zig medians at depths 16/32/64/128 were 1.746/1.742/1.919/1.923M/s;
libreactor 4.298/7.263/10.938/13.627M/s. Server batch/callback limits remain 16/64;
zero final owners/late allocations/timeouts/refusals. Both are faster than the
preceding unqualified profile sweep, but no controlled profile A/B is established.
All power-profile and EPP endpoints read performance; governor remained powersave.
Current-frequency observations are untimed endpoints, not average active clocks.

The preparation agent and Linux timed sweep finished. No timed runner remains
active. Mac/Windows timings were not run. Windows gates are deferred while tuning
this Linux/macOS-only HTTP implementation, per the user's explicit decision.
Another agent takes Mac measurements: use the host-local atomic directory
`/tmp/zig-http-measurement.lock` on both hosts before load/build/runtime suites.
If it exists or an earlier benchmark process is active, hold off. Record
owner.json metadata, keep your lock through child cleanup, then remove only your
own reservation. The sweep's initial trials predated this new protocol; the
Linux lock was acquired during the sweep and released after zero owned processes.
Full protocol: sibling wiki docs/platform-testing.md. Do not assume the hosts
remain free after an earlier check.

Current performance checkpoints:

- `b8a3afe1bcfd7dd933060e1064cab55c4f7a41c3`: unchanged MVP versus pinned
  Round23 leaders, 113k/s versus mrhttp3.20M/libreactor4.04M at128connections,
  pipeline16. All54+18 trials passed; raw wrk latency percentiles rejected.
- `a164d42badb05e3d5cb11d3ea3789f06ffcd196d`: optional inline execution,
  24-trial same-sweep gain from117k to134k/s; zero application workers.
- `ca2eccf262632eda943615b119573c23e0f6e4fc`: inline and gather become defaults.
  A12-trial same-sweep comparison measured125k scalar-inline versus344k gather.
  Mac/Linux native wire/cancellation evidence is in reports/2026-09-05-gather.md.
- `b7ac35558dea3e418e7dab5e41b1d3bb9054ca73`: generic response batching,
  default16 cells, global64-callback budget, deferred compaction and flush
  barriers. Same-binary pipeline16: batch1 234k/s, batch16 1.22M/s. Separate
  one-core experiment: Zig1.83M/s versus libreactor2.62M/s. All 24+12 trials passed.
- `5620905193e496af1c4b297a576c4fe7edd6c4a9`: separate multi-cell pending-cancel
  witness; both Mac and Linux retained16 cells and drained every owner. Both
  hosts pass52 tests in Debug/ReleaseSafe,26+10+11+16 wire cases,30k smoke bodies.
- `3f1963f21a8d5c84b08efed94c90e1cbb9434330`: deeper client pipeline support
  in the harness and distinct-body wire tests at32/64/128. All22 batch cases
  pass on Mac/Linux; runtime server source is unchanged from5620905.
  The24-trial one-core depth16/32/64/128 sweep passed, but Zig plateaued near
  1.06–1.19M/s while libreactor reached7.41M/s at128. The depth16 control also
  regressed versus the preceding sweep; retain its follow-up old/current binary
  control before attributing that change to code. That control also varied:
  unchanged current binary1.02–1.81M/s, original0.96–1.16M/s. It cannot isolate
  a code regression; all6 trials passed and the variation remains explicit.
  Preserve all earlier checkpoints; do not relabel their data as the new code.

Inline application callbacks must be bounded and nonblocking. Worker mode is
explicit; per-request optional offload and multiple I/O owners remain future
work. Gather metadata and all borrowed payloads survive target completion,
independently of cancellation acknowledgements. See current code/docs and the
next batching packet before changing ownership. Read ROADMAP.md for scope.

This is the first working Zig 0.16.0 HTTP/1.1 experiment. Start with README.md,
AGENTS.md, docs/OWNERSHIP.md, docs/EVIDENCE.md and ROADMAP.md. The current code is
the maintained runnable example; the adjacent zigllmwiki stores reusable
source-pinned guidance. Do not restart the project or copy its Zig into wiki text.

Use ReleaseSafe for every timing experiment. Debug is a separate correctness
gate. On omarx1 the default Debug ELF linker rejects R_X86_64_PC64 in GCC 16's
crt1.o .sframe. The user suggested ReleaseSafe, and its default selection passed
without linker overrides. build.zig selects LLVM/LLD only for Linux Debug to
retain both correctness gates. Do not upgrade Zig to work around this.

Core model: one I/O owner, raw io_uring on Linux/nonblocking kqueue on macOS,
inline callbacks by default, optional fixed startup workers with slot affinity. Callback state survives
`return writer.flush()`, which sends all committed bytes before `.flushed`.
`finish()` ends framing. Borrow only request-owned input or immutable
server-lifetime assets; dynamic completion/release notifications are pending.
Timeouts close networking but retain storage until running handlers return.
Unreconciled ownership at the shutdown deadline requires whole-process exit70.

The integration suite exercises malformed framing, exact/over limits,
pipelining, forced partial sends, worker isolation/recovery and shutdown. The
slow-reader witness must show bytes_sent below its 2MiB payload; Linux otherwise
can finish the echo into kernel buffers and merely time out the next idle read.
SO_SNDBUF4096 is an OS request used to force that witness, not a portable exact
kernel allocation size.

Budget tracks/refuses framework allocator growth and counts late attempts.
It excludes libc/pthread metadata, actual stack mappings, kernel socket/ring
storage, allocator overhead and application allocations; do not call it an RSS
cap. No extra workers or request queues appear under load. Pipeline suffix
compaction happens only after batch completion, remains measured, and is still
an optimization target for deeper client pipelines.

Mac maxross is preferred for expensive portable work; Linux runtime uses
`tools/verify_linux_ssh.sh omarx1`, which streams into a validated temporary
directory and preserves remote authoring checkouts. From Linux use ssh maxross
when available; continue on omarx1 during travel outages. Windows is queued.
Final validation details belong in reports/; preserve earlier failed/narrower
results rather than silently relabeling them. All contributors finish before
publication; no queued roadmap item implies a running agent.

The first pinned implementation and native gate packet is in
[reports/2026-09-05-mvp.md](reports/2026-09-05-mvp.md): 44 test executions in
each mode and 26 integration cases per host. Full finite smoke runs validated
30,000 responses per host in ReleaseSafe. See ROADMAP.md for remaining work.

The next isolated architecture experiment is token-addressed Linux operation
cells: preserve exact slot/generation/kind checks and cancellation reserve while
removing admission/CQE searches. The single-owner thread, whole-slot scheduler
scan, six per-request clock reads and generic header formatting remain current
costs, not profiled bottlenecks. Tune server batch limits separately from client
pipeline depth. I/O sharding, optional offload and dynamic release remain queued.

Latest evidence is [the batching report](reports/2026-09-05-batch.md), including
24 batch-limit,12 one-core,24 deeper-pipeline and6 old/current trials. All72
baseline/client trials and the separate inline/gather checkpoints remain intact.
All agents and timed runners finished. Use the final clean pushed documentation
revision for local and Linux publication gates. Windows HTTP remains unimplemented;
the sibling wiki's hosted Windows checks cover its lifecycle proofs only.

## Arena/shard architecture branch (Claude, worktree `perf-architecture`)

Reference branch `perf/arena-shards` (measured commit `ad424c7`, handoff at
`122e903`) is kept untouched for comparison against experiments on the old
main. `perf/arena-shards-plus-main` merges main's operation-cell, batch/quantum
and ABBA-harness work on top of it (source resolved to the arena/shard side,
main's reports, comparator tests, chunked demo routes and a maximum-64-cell
fixture ported); both native gates pass on the merge. Worktree
`.claude/worktrees/perf-architecture` is checked out on the merge branch. Report
[reports/2026-09-05-arena-shards.md](reports/2026-09-05-arena-shards.md),
design [docs/PERF-ARCHITECTURE.md](docs/PERF-ARCHITECTURE.md). It replaces the
fixed response cells with a per-connection output arena (head written at
`begin()`, small borrows copied, one span per batch), a FIFO ready ring and
turn clock, a lane-scanning parser, cell-addressed transport operations with
caller-owned vectors, and a shard cluster (one owner per allowed CPU on Linux,
SO_REUSEPORT, shared admission ceiling). Interleaved Linux pairs at `ad424c7`:
three CPUs depth 16 7.0–7.2M/s versus libreactor 7.6–7.7M/s; one core depth 128
6.6–6.9M/s versus 10.0M/s; three CPUs depth 1 549–588k/s versus 558–568k/s.
Both native gates pass (Linux with eight auto shards). It overlaps main's
direct-operation-cell and batch/quantum work in `src/transport*.zig`,
`src/server.zig`, `src/main.zig` and `tests/batch_integration.py`; resolve by
taking this branch's source and keeping main's reports, tools and comparator
tests. `--inline-callback-budget` corresponds to `--callbacks-per-turn`.
Pre-armed receives and eager submission are implemented, measured without
gain, off by default and covered by the batch suite's overlap variants.
