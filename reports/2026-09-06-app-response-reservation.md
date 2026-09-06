# Bounded response adapter verification — 2026-09-06

This receipt qualifies the response adapter changes on engine base
`2b41a0801a655f02223a9ece2e8ebddfffed64f7`.
The [32-file manifest](2026-09-06-app-response-reservation/linux/source-input.sha256.json)
identifies every compiled source, build, fixture, and verification tool input.
All recorded input hashes remained unchanged through both native gates.
The branch was rebased onto branding commit `6f78368aacd78bac8fe4bb6d5ae6b75364ad2f58`.
Only `tools/build_pages.py` changed among those 32 inputs; it changed the Pages repository URL.
All compiled sources, build files, and native verification inputs still match.
The [post-branding manifest](2026-09-06-app-response-reservation/post-branding-input.sha256.json) records that distinction.
Documentation generation and link checks passed again after the rebase.

The public adapter reserves output before callback dispatch.
It supports checked unpublished drafts, validated additional headers, body-copy accounting, and atomic-only cluster stopping.
Existing direct handlers retain the 384-byte default output reservation.
These changes add no transport implementation or custom `std.Io` provider.

| Gate | macOS | Linux |
| --- | --- | --- |
| Exact compiler | Zig 0.16.0 | Zig 0.16.0 |
| Native host | Apple M3 Max, arm64, macOS 26.6.2 (25G83), kqueue | omarx1, Core Ultra 7 258V, x86_64, Linux 7.1.9-arch1-2, io_uring |
| Debug verify | 16/16 steps; 78/80 tests, two Linux-only skips | 16/16 steps; 80/80 tests |
| ReleaseSafe verify | 16/16 steps; 78/80 tests, two Linux-only skips | 16/16 steps; 80/80 tests |
| Independent embedding | GET/HEAD/GET passed in both modes | GET/HEAD/GET passed in both modes |
| Core wire cases | 84 passed | 84 passed |
| Comparator tests | 8 passed | 8 passed |
| ReleaseSafe smoke | 30,000 exact response bodies | 30,000 exact response bodies |

The 84 core cases comprise arena lifecycle (8), batching (29), gather output (11), inline execution (10), and wire integration (26).
Smoke throughput fields are correctness-run observations, not a new performance comparison.
All load and warmup binaries used ReleaseSafe with assertions enabled.
Debug was used only for correctness checks.

[Mac logs and command receipts](2026-09-06-app-response-reservation/macos/)
record finite watchdogs and process-group cleanup.
[Linux summary](2026-09-06-app-response-reservation/linux/summary.json)
records all ten commands and their process identities.
Both runs used the cooperative host reservation protocol.
All observed engine child groups were absent after verification.
The owners retained their host reservations for the dependent Baz verification session.

The Mac runner source imports the included cleanup-runner snapshot through its original Baz fixture path.
The receipt preserves executed paths; replay requires selecting the local checkout paths.
The Linux runner and platform metadata are included beside its raw output.

This is scoped native correctness evidence.
It does not qualify Windows, arbitrary callback isolation, dynamic output leases, or a production deployment.
The separate Baz package must pass its own dependency and application gates.
