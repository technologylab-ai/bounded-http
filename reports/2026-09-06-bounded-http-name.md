# bounded/http naming and publication — 2026-09-06

The user selected **bounded/http** for the brand.
The repository, canonical directory, executable, and HTTP product token use `bounded-http`.
The Zig package, dependency key, and exported module use `bounded_http`.
The byline is “for servers that stay within their bounds”.
The whitepaper retains “Fast by design. Explicit about limits.”

The public repository is [technologylab-ai/bounded-http](https://github.com/technologylab-ai/bounded-http).
GitHub retained repository identity `1358292683` during the rename.
The [website](https://technologylab-ai.github.io/bounded-http/) uses the new Pages path.
The canonical Mac directory is `/Users/rs/code/github.com/technologylab.ai/bounded-http`.
The old `zig-http` path remains a compatibility symlink for active worktrees and the Tailscale documentation server.
The shared reservation path remains `/tmp/zig-http-measurement.lock` on both hosts.

The Zig manifest retains the package identity while updating its name checksum.
The response Server field grows by four bytes.
The header cache still fits its fixed storage.
The comparison harness validates both current `bounded-http` and historical `zig-http` implementation names.
Nine comparator fixtures check successful receipts and rejection of invalid optimization, shutdown, ownership, allocation, and admission results.

Historical reports, raw benchmark keys, source revisions, and binary hashes retain their original identities.
The chart renderer changes visible labels without changing measurement data or historical SVG hash salts.
No throughput measurement accompanies the rename.

The approved [response-adapter PR](https://github.com/technologylab-ai/bounded-http/pull/1) merged at `c90281b600deb699a667e2bcc115da32862c794f`.
Its 32-file post-branding manifest matched every published input before merging.
Its native receipt remains [separate](2026-09-06-app-response-reservation.md).
The whitepaper adds the reserve-before-callback principle and cites the adapter source at `e52f09f723388685263d14a9bfa265f2456a3744`.

The initial [branding deployment](https://github.com/technologylab-ai/bounded-http/actions/runs/34037583269) passed at `6f78368`.
The [smaller italic byline](https://github.com/technologylab-ai/bounded-http/actions/runs/34037695335) passed at `09a70a8`.
The [revised byline](https://github.com/technologylab-ai/bounded-http/actions/runs/34037762629) passed at `8e483bf`.
HTTP fetches confirmed the requested byline on GitHub Pages and the existing Tailscale address.
These presentation commits contain no runtime source changes.

Mac development verification used exact Zig 0.16.0 on Apple M3 Max, arm64, macOS 26.6.2 build 25G83.
Debug and ReleaseSafe each passed 16 build steps, 78 tests, and two Linux-only skips.
The independent embedding checks passed in both modes.
All 84 wire cases, nine comparator tests, and 30,000 exact smoke bodies passed.
A separate finite probe verified GET, HEAD, and 404 responses with the new Server token.
Runtime, build, and test source hashes remained unchanged through the gate.
The gate released its host reservation at 14:12:46 UTC.
The ignored packet is `.zig-cache/bounded-http-macos-development-20260906/` in the rename worktree.

Both generated performance SVGs passed regeneration checks with the documented plotting versions.
Seven HTTP browser cases and all thirteen wiki browser cases passed on Chrome 152.0.7977.76.
The HTTP cases covered names, byline placement, historical chart labels, embedding links, diagrams, mobile layout, offline reading, and print.
The first browser probe expected a GitHub URL for raw Markdown; the harness was corrected to expect the bundled artifact.
The reader's separate source links already targeted the renamed repository.
The final browser run released its reservation after all checks and cleanup.
The ignored browser packet is `.zig-cache/branding-browser/`.

The clean pushed rename commit will receive the relevant Linux publication gate after the short wiki verifier releases its reservation.
Windows HTTP work has separately resumed in `feat/windows-iocp`.
That adapter has no runtime result yet.
M3-006 physical deployment qualification remains postponed in the wiki.
