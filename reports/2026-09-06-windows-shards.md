# Windows IOCP shard verification — 2026-09-06

Candidate `514c901fafd005f140a0a6fdf10ee28d0ff8796a` passed native x64 Windows verification.
[Run 34043829095](https://github.com/technologylab-ai/bounded-http/actions/runs/34043829095) exercised the pushed `feat/windows-shards` branch.
This report records functional evidence; it contains no Windows performance comparison.

The candidate adds bounded socket handoff between independent IOCP owners.
The [architecture guide](../docs/ARCHITECTURE.md#windows-socket-handoff) explains the design and shutdown order.
The previous [single-owner receipt](2026-09-06-windows-iocp.md) remains unchanged.

## Source and environment

The [source manifest](2026-09-06-windows-shards/source-inputs.json) records all 295 candidate files with SHA-256.
The hosted supervisor also hashes 28 selected build, runtime, and fixture inputs.
Every selected hash matched the candidate commit.
The checkout was clean before and after execution.

| Property | Recorded environment |
| --- | --- |
| Compiler | Exact Zig 0.16.0, native x64 compiler, PE machine `8664` |
| Compiler archive SHA-256 | `68659eb5f1e4eb1437a722f1dd889c5a322c9954607f5edcf337bc3684a75a7e` |
| Operating system | Windows Server 2025 Datacenter, 24H2, build `26100.33296` |
| Hosted image | `win25-vs2026`, version `20260824.214.3` |
| Processor | AMD EPYC 7763; runner exposes two cores and four logical processors |
| Memory | 17,174,360,064 bytes |
| Filesystem | NTFS |
| Python / PowerShell | 3.12.10 / 7.6.5 |
| Network | Native x64 IPv4 loopback; client and server share the hosted machine |
| Native phases | 2026-09-06, from 15:56:34 UTC; job finished at 16:00:11 UTC |
| ReleaseSafe executable SHA-256 | `aa779d324697dcf960d7c89ce7bcbfbee47015d1ee6e278ea8d00457c64870d4` |

The workflow downloads Zig from the official release index and verifies its archive checksum.
The supervisor checks the executable architecture and exact compiler version before recording evidence.

## Results

| Gate | Result |
| --- | --- |
| `zig build verify --summary all` | 16/16 steps; 95/99 tests passed, four explicit POSIX skips |
| `zig build verify -Doptimize=ReleaseSafe --summary all` | 16/16 steps; 95/99 tests passed, four explicit POSIX skips |
| Independent embedding | Three exact responses per build mode |
| Comparator fixtures | 9/9 |
| Existing wire suites | 80 passed; four explicit POSIX suspension skips |
| New Windows shard suite | 9/9 |
| Exact-body smoke | 30,000 responses; zero reported errors, rejections, or timeouts |
| Final framework ownership | Zero live connections, operations, and late allocation calls |

The four Zig skips are POSIX client fixtures reached through two test roots.
The four wire skips require POSIX process suspension for maximum-cell schedule control.
Neither skip class represents Windows runtime evidence.

The new [wire suite](../tests/windows_shards_integration.py) records these witnesses:

- Two, three, and four owners each process distinct borrowed response pipelines.
- Twelve concurrent clients produce 192 exact responses across four owners.
- Six acknowledged connections hold the global ceiling; four excess connections are rejected, followed by successful recovery.
- Twenty-four fresh streams exercise slot reuse, half-close, prearmed receive, and flush continuations.
- Console shutdown interrupts three partial borrowed responses while three incomplete receives remain owned.
- Repeated idle shutdown finishes across three owners.
- An occupied listener fails before readiness; multi-owner worker execution is rejected.

The pipeline fixtures recorded three accepted connections and nine completed responses on every configured owner.
The concurrent fixture recorded three accepted connections and 48 completed responses on each of four owners.
Every completed session matched queue publications with queue removals.
The wire suite runs live owners and does not claim forced mailbox interleavings.

Deterministic Zig fixtures separately establish internal transitions:

- Zero-data accept finishes before socket export and destination association.
- Capacity and association failures preserve detached ownership for retry or closure.
- Source cancellation cannot end a destination receive's lifetime.
- Two preloaded queues retain admission while a third actual acceptance is refused.
- A receiver-only stop propagates to the accepting owner and drains every queue.
- Adoption preserves the acceptance timestamp; an explicitly aged entry expires without application dispatch.
- Partial startup failure aborts prepared owners; secondary failure stops the primary without a duration escape.
- A fixed queue preserves FIFO order, full-queue ownership, and publication visibility across threads.

These fixtures ran natively on Windows with assertions enabled.
Earlier Mac cross-compilation checked both Windows build modes, but contributes no Windows runtime evidence.

## Bounds and shutdown

Let `C` denote configured connections and `S` denote configured shards.
Windows supports explicit inline configurations from one through 64 shards.
Windows still defaults to one shard; worker execution still requires one shard.
The native fixtures exercise one through four owners.
Counts five through 64 remain source-supported configurations without separate runtime coverage in this packet.

Shard zero owns the single listener and handles its own round-robin connection share.
Each secondary owner has an independent IOCP and private connection storage.
No additional accepting thread is created.

Admission includes producer transit, queue residence, consumer transit, and adopted connections.
The admission charge remains held throughout those transitions.
The shared successful reservation count never exceeds `C`.
Each secondary queue has usable capacity `C`, backed by `C + 1` optional entries.
Checked startup accounting includes all queue entries, queue metadata, full shard storage, and requested owner stacks.

One pending accept can own an additional staging socket.
The cluster therefore owns at most `C + 1` nonlistener socket handles, plus one listener.
That bound excludes the kernel backlog, provider allocations, and background TCP cleanup after handle closure.

The destination receives request bytes only after owning and associating the socket.
Socket transfer copies metadata; it does not copy request payloads between shards.
Ordinary Winsock receive and send still copy across the kernel boundary.
The implementation does not claim kernel zero-copy networking.

Queue residence retains the original acceptance deadline.
Each destination checks time before adoption and processes at most `C` queued entries per turn.
Remaining queued entries force nonblocking polling; wake notifications have a ten-millisecond polling fallback.

Any stopping owner requests cluster-wide stop.
Receivers acquire `producer_done`, then recheck queue emptiness before exiting.
The flag means no further publications; an errored producer can still retain outstanding kernel operations.
Failed owners retain their storage under the process-termination boundary.
Successful shutdown drains queues, connections, operations, and separate cancellation acknowledgements before adapter destruction.
The listener and Winsock startup references remain alive until every owner exits.

The [pinned evidence inputs](../docs/EVIDENCE.md) identify the Microsoft association, AcceptEx, cancellation, and cleanup contracts.
These custom adapter rules are not `std.Io` interface guarantees or `std.Io.Threaded` behavior.

## Watchdogs and regression scope

The manual workflow has a 35-minute job timeout.
The supervisor gives each Zig verification phase 300 seconds and each wire process 150 seconds.
Wire suites declare a 120-second internal deadline and bounded socket operations.
Smoke has a 180-second outer watchdog.
Timeout cleanup terminates and waits for the complete owned process tree.

Server shutdown uses configured finite drain and thread-exit watchdogs.
The deterministic queued-socket fixtures add a five-second external watchdog thread.
The framework cannot preempt arbitrary application callbacks.
Embedding applications must preserve the process-exit boundary when ownership cannot be reconciled.

The same clean pushed candidate passed Linux regression on `omarx1`.
Both build modes passed 16/16 steps and 82/84 tests, with two Windows-only skips.
Linux also passed 84 wire cases, nine comparator fixtures, both embedding probes, and 30,000 exact smoke responses.
The host used kernel `7.1.9-arch1-2`, glibc 2.44, Python 3.14.7, and exact Zig 0.16.0.
The processor was Intel Core Ultra 7 258V with eight logical CPUs.
The [Linux summary](2026-09-06-windows-shards/linux-summary.json) records exact identity, hashes, cleanup, and scope.

Final feature publication gates are recorded on the PR's exact pushed commit.
This candidate report remains immutable and does not silently acquire later source revisions.
Windows performance, ARM64, service integration, physical deployment, and long-duration qualification remain outside this evidence.
macOS shard distribution remains queued; the wiki's M3-006 remains postponed.

## Preserved artifacts

- [Native summary](2026-09-06-windows-shards/native-summary.json) and [native packet](2026-09-06-windows-shards/native-run-34043829095/runtime-gate.json).
- [Original hosted archive](2026-09-06-windows-shards/native-artifact.zip), verified against GitHub's artifact digest.
- [Recorded file hashes](2026-09-06-windows-shards/sha256.json) and [candidate source hashes](2026-09-06-windows-shards/source-inputs.json).
- [Linux candidate packet](2026-09-06-windows-shards/linux-candidate.tar.gz), including raw commands, outputs, metadata, and cleanup receipts.

Hosted archive SHA-256: `63aa7be73a0d7582908d1d8c6db01e7e338ee72e329b219694e14a59067dcec0`.
Linux archive SHA-256: `6a40872fd8451d3e06c4f90882e6750d035f7cfbb9ad841d37b7703ae980965e`.
Raw Windows files retain their original bytes through `.gitattributes`.
