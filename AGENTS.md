# bounded/http agent contract

Use **bounded/http** in prose and page branding.
Use `bounded-http` for the repository, directory, executable, and HTTP Server token.
Use `bounded_http` for the Zig package, dependency key, and module.
Preserve historical evidence names and the shared `/tmp/zig-http-measurement.lock` path.

Use exact Zig 0.16.0 from `.zig-version`. This standalone M4 implementation is
informed by `../zigllmwiki`; runnable server code belongs here under `src/` and
tests, not copied into wiki pages. Preserve the wiki's source/evidence hierarchy.

Preallocate framework threads, buffers, queues and operation state at startup.
Never allocate, spawn threads or perform blocking work on the request I/O loop.
Application workers receive borrowed input and exclusive output reservations;
retain storage until all application and kernel borrows have returned.
Use explicit bounds, checked arithmetic and assertions of ownership invariants.
Malformed HTTP is an ordinary error, never an internal assertion failure.

Compile/test every Zig file with `zig build verify`. Use Debug/ReleaseSafe;
do not disable assertions for benchmarks. Run Python integration tests for
wire framing, partial progress, overload, deadlines and shutdown. Record exact
platforms; cross compilation is not runtime evidence. All code is experimental
until the named gate passes; do not claim arbitrary application isolation.

Use subagents for independent parser, transport and lifecycle work. Keep file
ownership explicit. The parent owns integration, README, docs and build setup.

Repository prose follows Simplified Technical English (ASD-STE100), guided by Zinsser.
Use one idea per sentence and active voice with a named actor.
Limit sentences to 20 words, or 25 words for descriptions.
Define technical terms at first use and use one term per concept.
Keep each word's meaning and grammatical role consistent.
Give every pronoun a clear referent.
Code identifiers, quoted output, error strings, and exact-format text are exempt.
The [writing policy](https://github.com/technologylab-ai/zigllmwiki/blob/main/docs/technical-writing.md) records the supplied guidance and its scope.

Maintain architecture graphics under `docs/diagrams/`.
Edit `docs/whitepaper.template.html`, then run `python3 tools/render_whitepaper.py`.
Run `python3 tools/render_whitepaper.py --check` before publishing documentation.
The generated whitepaper embeds the canonical SVGs for offline reading.

Before benchmarks, heavy builds or runtime suites on maxross or omarx1, acquire
`/tmp/zig-http-measurement.lock` with atomic mkdir on the execution host. If it
exists, hold off; owner.json records who and why. Also inspect pre-existing
measurement processes that may not honor the new protocol. Retain your lock
through child cleanup and remove only your own metadata/directory. Never steal
an old lock by age alone. The full cooperative protocol is in the sibling wiki's
`docs/platform-testing.md`. Mac measurements by another agent take precedence
while that agent holds its reservation. Windows performance/publication gates
are deferred during the current Linux/macOS HTTP tuning loop by user decision.
