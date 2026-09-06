# Windows IOCP implementation and native verification

The user resumed Windows HTTP support on 2026-09-06.
The implementation uses a custom I/O completion port (IOCP) adapter with exact Zig 0.16.0.
An IOCP delivers terminal operation results to the server's I/O owner.
The adapter remains experimental.

## Implementation scope

The adapter retains the existing parser, response writer, output arena, batching, and callback contracts.
Windows requires one shard.
Inline execution creates no application workers.
Worker execution creates its configured threads and notification events during startup.

Each operation has a stable `OVERLAPPED` record, which Windows uses to identify pending work.
The backend reserves `4 × connections + 2` operation cells and equally bounded completion storage.
The backend also reserves `connections + 1` socket-table entries and a separate listener handle.
Pointer-sized Winsock handles remain inside that table; common completion results carry logical indices.

`AcceptEx` waits for a connection without requiring initial request bytes.
`WSARecv` receives into retained slot storage.
`WSASend` submits scalar or gathered response spans.
Winsock captures converted descriptors during submission; payload storage remains borrowed until terminal completion.
The selected notification mode preserves completion packets after immediate success.
Each `GetQueuedCompletionStatusEx` dequeue has a fixed 256-entry ceiling.
The adapter checks each result separately through documented result functions.

`CancelIoEx` requests cancellation without releasing the target record.
A cancellation acknowledgement and the target's terminal completion remain separate events.
Shutdown stops admission, cancels operations, drains completions, and reconciles application borrows before destruction.
Unreconciled ownership reaches the existing process-termination boundary.
Finite test watchdogs supervise the process because arbitrary application code can stall internal progress.

The reference executable accepts Ctrl-C and Ctrl-Break stop requests.
Console callbacks only access the cluster while a counted reference remains valid.
Teardown clears publication and waits for existing references before freeing the cluster.

## Resource and qualification limits

The listener accepts plain HTTP/1.1 on IPv4 loopback.
Exclusive Windows listener binding prevents this implementation from sharing its port across shards.
TLS, external network deployment, Windows service controls, console closure, and logoff handling remain unqualified.
The native gate targets x64; ARM64 and WOW64 remain outside its evidence.

Winsock creates a socket resource for each pending accept during admission.
Framework heap sealing does not intercept provider or kernel allocations.
Default socket closure can leave provider resources during background TCP cleanup.
The fixed table bounds application-owned handles, rather than all kernel resources retained over time.
Ordinary socket operations still copy across the kernel boundary.
This adapter establishes neither kernel zero-copy nor a hard real-time guarantee.

The suite excludes four maximum-cell fixtures that require POSIX process suspension.
Windows arena wire cases deliver input to a live owner.
Those cases do not force the same input timing as the POSIX suspension harness.
Separate Zig tests force internal completion ordering.
Windows CPU accounting remains `null` where the client cannot measure it.
The smoke workload checks 30,000 response bodies; its timings do not establish server capacity.
No Windows comparative performance measurement belongs to this report.

## Evidence and initial run

The [primary-source manifest](2026-09-06-windows-iocp/primary-source-manifest.json) preserves exact Microsoft documentation and Zig ABI identities.
The [evidence guide](../docs/EVIDENCE.md) links the pinned API contracts.
These implementation choices belong to this adapter, rather than `std.Io` or `std.Io.Threaded`.

The initial candidate was `02f0e2b32c2ca67e44e017a2c8814600c154a17d`.
[Run 34039231092](https://github.com/technologylab-ai/bounded-http/actions/runs/34039231092) failed in a Python fixture using unavailable Windows `SIGSTOP`.
Both native Zig modes passed 16 build steps and 83 tests, with six explicit skips per mode.
Both embedding probes and nine comparator checks passed before that fixture failure.
The overall run remains failed; those component results do not qualify the complete HTTP gate.
The [initial packet](2026-09-06-windows-iocp/first-run-34039231092/runtime-gate.json) and raw logs preserve the failure.

The test-only follow-up `70f9ae5917076b664081db59c62edc4959ca5041` removes the arena fixture's POSIX suspension dependency on Windows.
Server and transport sources remain unchanged by that follow-up.
[Run 34039591972](https://github.com/technologylab-ai/bounded-http/actions/runs/34039591972) passed on that exact pushed candidate.
The native supervisor ran from 14:35:24 to 14:38:39 UTC on 2026-09-06.
The job completed at 14:38:46 UTC.

## Successful native x64 gate

| Check | Result |
| --- | --- |
| Debug verifier | 16/16 build steps; 83/89 tests passed; six explicit skips. |
| ReleaseSafe verifier | 16/16 build steps; 83/89 tests passed; six explicit skips. |
| Independent embedding | Exact GET/HEAD/GET pipeline passed in both modes. |
| Comparator receipt tests | 9/9 passed. |
| Arena lifecycle wire cases | 8 passed with live Windows input. |
| Batch wire cases | 25 passed; four POSIX suspension cases skipped. |
| Gather, inline, and general wire cases | 11, 10, and 26 passed, respectively. |
| Total wire cases | 80 passed; four explicit skips. |
| Smoke | 30,000 exact responses; IOCP backend; ReleaseSafe. |
| Ownership and allocation | Saved shutdown counters have zero live connections, live operations, and late framework allocations. |
| Checkout | Clean before and after native execution. |

The six Zig skips comprise duplicated POSIX-only transport fixtures and two Linux shard fixtures.
Windows-specific IOCP counterparts execute separately.
The supervisor applies 300-second build watchdogs, 150-second integration watchdogs, and a 180-second smoke watchdog.
The GitHub job has a 35-minute outer timeout and uploads failure evidence.

The successful host ran Windows Server 2025 Datacenter 24H2, build `26100.33296`, on native x64.
The hosted image was `win25-vs2026`, version `20260824.214.3`.
The processor was AMD EPYC 9V74, with two exposed cores and four logical processors.
The host exposed 17,174,360,064 memory bytes and NTFS disks.
PowerShell was 7.6.5; Python was 3.12.10.
The native compiler was checksum-verified Zig 0.16.0.
The successful host differs from the initial run's AMD EPYC 7763 host.

The ReleaseSafe executable has native x64 PE machine identifier `8664`.
Its SHA-256 is `9130774c8df265c8fba2340b50577d3b828289c42643ff5e650c8a038fcbf02a`.
The [native summary](2026-09-06-windows-iocp/native-summary.json) records all counts and the exact environment.
The [native packet](2026-09-06-windows-iocp/native-run-34039591972/runtime-gate.json) includes commands, watchdogs, source hashes, and timestamps.
The [packet manifest](2026-09-06-windows-iocp/sha256.json) hashes preserved raw evidence.
Those repository copies retain evidence after hosted artifacts expire.

The preceding macOS Windows cross-builds passed seven steps in Debug and ReleaseSafe.
Those builds were compile-only evidence; the hosted native gate establishes the runtime results above.
Windows performance and the wiki's M3-006 physical deployment qualification remain postponed.


## Mac, Linux, and documentation regression gates

Both native regression gates used clean pushed candidate `70f9ae5917076b664081db59c62edc4959ca5041`.
Both gates preserved identical source hashes throughout execution.

| Host | Native result |
| --- | --- |
| Mac | Debug and ReleaseSafe each passed 16 steps and 78/80 tests, with two Linux-only skips. |
| Linux | Debug and ReleaseSafe each passed 16 steps and 80/80 tests. |
| Each host | Both embedding probes, 84 wire cases, nine comparator tests, and 30,000 exact smoke responses passed. |

Mac execution ran from 14:40:27 to 14:41:01 UTC.
The host was Apple M3 Max arm64, macOS 26.6.2 build `25G83`, Darwin 25.6.0, with Python 3.9.6.
The ReleaseSafe binary SHA-256 was `fa0ecc1b4e34c06a44733ef287955f258ed679d2e81e861a90454b7735115f34`.
The [Mac packet](2026-09-06-windows-iocp/native-macos/receipt.json) preserves commands and source identities.

Linux execution ran from 14:41:38 to 14:42:22 UTC through `ssh omarx1`.
The host ran Arch/Omarchy x86_64, kernel `7.1.9-arch1-2`, on Intel Core Ultra 7 258V.
The host used glibc 2.44, Python 3.14.7, and `io_uring_disabled=0`.
The ReleaseSafe binary SHA-256 was `b23ddaa0040ec485666b032176821814b4067ce1617b44b75a9d3e5c020707c2`.
The [Linux packet](2026-09-06-windows-iocp/native-linux/receipt.json) preserves commands, environment, and cleanup checks.
Both hosts released their reservations after owned child processes ended.
The Linux temporary checkout was removed; the authoring checkout remained untouched.

The updated documentation adds Windows to both platform labels below Zig 0.16.0.
The guides describe IOCP, socket ownership, shutdown, and qualification limits.
The startup SVG now includes console handlers.
Eight Chrome 152.0.7977.76 development browser cases passed against the local publication artifact.
Those cases cover both labels, report rendering, source links, diagrams, mobile width, offline reading, and print output.
The [browser receipt](2026-09-06-windows-iocp/browser-development.json) explicitly describes development content rather than a deployed commit.
Local document checks passed all six accessible SVGs, links, identifiers, and generated whitepaper content.

## Earlier rename gate and output capture

The rename's clean pushed Linux gate at `64f59ad1292601f1102d00ea12af1dd608a66a63` also passed both modes, 84 wire cases, and 30,000 responses.
Its ignored postprocessor initially failed because SSH interleaved a stderr progress line inside stdout JSON.
The original log and failure receipt remain preserved in the rename worktree.
Independent decoding removed exactly that progress line and confirmed every recorded result.
The maintained Linux wrapper now combines remote streams before SSH transmission to preserve output order.
That capture change does not modify the HTTP implementation.
