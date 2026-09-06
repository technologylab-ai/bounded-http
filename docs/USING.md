# Using bounded/http

Use the exported `bounded_http` module to embed the framework in a Zig application.
Use exact Zig 0.16.0, as specified by [.zig-version](../.zig-version).
The framework supports Linux and macOS native execution.
Windows support remains pending.

The current listener accepts plain HTTP/1.1 on IPv4 loopback only.
The framework has no Transport Layer Security (TLS), general file server, protocol upgrade, or tunnel implementation.
Treat the current API as experimental.

The [architecture guide](ARCHITECTURE.md) introduces owners, shards, slots, arenas, and completion handling.
The [reference executable](../src/main.zig) supplies maintained examples of request handling and lifecycle management.

## Run the reference executable

Acquire the host reservation described under [verification and measurement](#verification-and-measurement) before building or running suites on shared hosts.
Run these commands from the repository root:

```sh
zig version
zig build verify -Doptimize=ReleaseSafe
zig build -Doptimize=ReleaseSafe
./zig-out/bin/bounded-http --port 8080 --connections 128 --shards 1
```

The version command must print `0.16.0`.
ReleaseSafe preserves assertions and runtime safety checks.
The project also supports Debug.
The build rejects ReleaseFast and ReleaseSmall.

The server prints `READY` to stderr after preparing its resources.
Request `/plaintext` for the fixed 13-byte `Hello, World!` response.
Request `/index.html` for the HTML asset loaded during startup.
The [README](../README.md) lists the other demonstration routes.

SIGINT and SIGTERM request shutdown in the reference executable.
Use `--duration-ms 30000` for a finite experiment.
Use `--port 0` to let the operating system choose an available port.
Read the selected port from `READY`.

## Add the framework to your project

The [embedding example](../examples/embedding/src/main.zig) is an independent consuming project.
Its [package manifest](../examples/embedding/build.zig.zon) declares a local dependency on this repository.
Its [build file](../examples/embedding/build.zig) imports the exported module.

The example's dependency path is `../..` because the example lives two directories below the repository root.
Copy the example into your application project and change that dependency path to your framework checkout.
Keep the framework checkout pinned to a reviewed commit.

The dependency name and imported module name serve different purposes.
The example names the package dependency `bounded_http`.
The framework exports a module named `bounded_http`.
The consumer obtains that module with `dependency.module("bounded_http")`.
The consumer exposes it to its source as the `bounded_http` import.

The example passes its selected target and optimization mode to the dependency.
Its executable links libc.
The exported module is the framework entry point; the demo executable is not an embedding dependency.

The example uses one shard and an immutable fixed response.
It includes the allocator budget, startup barrier, allocator seal, finite run, and shutdown boundary.
Use its maintained source rather than reconstructing those steps from isolated snippets.

Run the independent example from its directory:

```sh
cd examples/embedding
zig build -Doptimize=ReleaseSafe
zig build run -Doptimize=ReleaseSafe -- --port 8081 --duration-ms 30000
```

The example replies to GET and HEAD requests on any path.
It stops after the configured duration without installing signal handlers.

The repository's Linux Debug executable explicitly selects LLVM and LLD.
That selection addresses the named Linux host's startup-object linker failure.
An external executable controls its own linker selection.
The example preserves the same choice for Linux Debug.
ReleaseSafe uses the default toolchain selection.

## Preserve the lifecycle

Use `Cluster` as the application entry point, including single-shard applications.
The module also exposes `Config`, `Server`, `api`, and `Budget`.
`Server` represents one shard and does not replace cluster-wide accounting.

1. Select limits in `Config` before allocating framework storage.
2. Call `Cluster.validate(config)` to reject inconsistent topology and memory limits.
3. Prepare application state and immutable assets before serving requests.
4. Reserve `Cluster.stackBytes(config)` from the total configured memory budget.
5. Construct `Budget` with the remaining heap limit and a startup allocator.
6. Pass `budget.allocator()` and the application pointer to `Cluster.init()`.
7. Call `cluster.start()` to prepare startup threads behind the barrier.
8. Seal the framework allocator after startup succeeds.
9. Announce readiness, then call `cluster.run()` to release request processing.
10. Collect statistics after a successful return from `run()`.
11. Destroy the cluster before releasing its application state and assets.

The `Budget` value must remain at a stable address throughout this lifecycle.
The cluster retains its allocator context.
The application pointer and referenced assets must also remain valid until cluster destruction.

Preserve the example's error handling around `Cluster.run()`.
A run failure can leave application or kernel references outstanding.
The reference executable terminates the process with exit code 70 in that case.
Do not convert that failure into ordinary deferred destruction.

## Provide a callback

`api.Handler` is a function pointer taking `*api.Context` and returning `api.Action`.
The handler signature does not return an error union.
The [reference handler](../src/main.zig) delegates to a helper that can return errors.
Its bridge converts helper errors into `.close`.

Returning `.close` closes the connection.
The framework does not generate an automatic 500 response for that action.
The connection might already contain partially transmitted output.
Closing may discard earlier finished responses that remain buffered.

The callback context provides these fields:

| Field | Application use |
| --- | --- |
| `request` | Read the current parsed request and borrowed input spans. |
| `writer` | Prepare response bytes during this callback. |
| `event` | Distinguish initial `.request` dispatch from `.flushed` continuation. |
| `state` | Retain continuation state in eight `usize` words allocated with the connection slot. |
| `application` | Access the application pointer supplied during cluster initialization. |
| `cancelled` | Observe cooperative cancellation through an atomic flag. |

The framework clears all eight state words before each request's first callback.
State survives successful flush continuations for that request.
Store progress before returning a flush action.
Offsets and small state values work well here.

The context itself exists only during the callback.
Do not retain its address or hand its fields to background tasks.
The framework does not support arbitrary asynchronous application tasks that outlive their callbacks.

## Read a request

The first callback runs after the complete bounded request has arrived.
The framework currently provides no application callback for partially received request bodies.
Request size therefore remains a startup choice.

`request.method` and `request.target` reference parsed input.
The target retains its original bytes.
The parser does not decode percent escapes or normalize application paths.
The demo's route helper separates its own path and query handling.

`request.header(name)` performs a case-insensitive field-name lookup.
It returns the first matching value, with surrounding spaces and tabs removed.
The result references request storage.
The lookup does not combine repeated fields.
Applications must choose explicit policies for repeated application-specific fields.

The parser has already validated header syntax and framing fields before callback dispatch.
Lazy lookup therefore postpones application interpretation, rather than framing validation.

`request.body()` creates an iterator over logical body spans.
Its `next()` method returns payload without copying or combining the spans.
For chunked input, the iterator skips chunk framing.
`request.body_wire` instead includes the original body framing.
Use the iterator when an endpoint accepts both fixed-length and chunked bodies.

The `/echo` handler demonstrates body iteration across flush continuations.
It preserves iterator progress in `context.state` before yielding.
The `/borrowed-body` handler deliberately accepts only fixed-length request bodies.

A larger application upload requires an application protocol or a different request limit.
Clients can divide an upload into independently bounded requests.
The application must define upload identifiers, ordering, retry behavior, and final assembly.
The HTTP framework does not supply those higher-level rules.

## Begin and write a response

Call `writer.begin(status, content_type, length)` once during the `.request` callback.
Do not call `begin()` again during `.flushed` continuations.
The writer places the response head into the connection's output arena immediately.

Supply a length for a response with known logical body size.
Supply `null` for chunked response framing when the body size is unknown.
The server enforces `max_response_bytes` cumulatively across all flushes.

A snapshot is the committed output frozen by one flush or finish action.
Choose one body path for each snapshot:

| Method | Behavior |
| --- | --- |
| `reserve(count)` and `commit(count)` | Generate initialized bytes directly inside the output arena. |
| `write(bytes)` | Copy existing bytes into the output arena. |
| `borrow(bytes)` | Reference eligible existing storage, with the configured small-copy exception. |

Keep at most one uncommitted reservation.
Commit only the bytes that the callback initialized.
A commit can use fewer bytes than its reservation.
Do not retain a reservation after returning from the callback.

Use generated bytes or one borrowed span within a snapshot.
Do not mix these paths in the same snapshot.
The small-copy optimization does not weaken this application contract.

Only the framework calls the writer's lifecycle methods, including `open()`, `release()`, and `resumeSnapshot()`.
Application code uses `begin()`, body methods, `flush()`, and `finish()`.

### Bounded response adapters

A higher-level adapter can prepare an unpublished response before it commits headers.
Set `Config.callback_output_reserve` to the adapter's complete scratch requirement before cluster initialization.
The default remains `api.header_reserve_bytes` for ordinary callbacks.
The owner drains older output before dispatch when the remaining arena cannot satisfy this requirement.
The owner preserves the request and does not replay application side effects.

The writer exposes three checked methods for these adapters:

| Method | Contract |
| --- | --- |
| `draftStorage(required_bytes)` | Return the requested scratch range for a fresh response. Return an ordinary error for invalid state or insufficient space. |
| `discardDraft()` | Reset only the current unpublished response. Preserve earlier frozen output. Reject a frozen or committed response. |
| `writeDraftBody(bytes)` | Copy staged body bytes after `begin()`. Permit overlapping source and destination ranges. Count the copied bytes. |

Call `draftStorage(0)` to check draft state without borrowing a nonempty range.
Keep scratch access within the active callback and invalidate adapter metadata after discard.
Do not call internal writer lifecycle methods or inspect writer fields from an external adapter.
The `response_draft_copy_bytes` statistic counts staged body copies, including logical HEAD bodies.

Use `beginWithHeaders(status, content_type, length, extra_headers)` to include additional response fields.
Supply complete header lines with CRLF terminators.
The writer validates names, values, reserved fields, and head capacity before mutation.
Repeated fields remain separate lines.
The writer copies Content-Type and additional headers synchronously during the successful call.
Arena-backed arguments must use disjoint ranges after the current snapshot's `header_reserve_bytes` prefix.
Header compaction can turn those original arena ranges into committed output.
Do not overwrite arena-backed arguments after the call.
The adapter must reserve additional header space through `callback_output_reserve`.

### Borrow lifetimes

`borrow()` accepts current request storage or immutable assets that live for the entire server lifetime.
Both `begin()` and `beginWithHeaders()` copy their `content_type` argument during the call.
The caller can reuse external argument storage after a successful call.
Arena-backed argument storage may now contain committed output and must remain unchanged.
Do not pass callback-local arrays or recyclable buffers to `borrow()`.

The default threshold copies eligible borrowed spans of at most 256 bytes when arena space permits.
Larger borrowed spans remain outside the arena.
Set `borrow_copy_threshold` to zero to disable that optimization.
Keep the same lifetime discipline regardless of the selected threshold.

A large immutable asset can exceed one arena's capacity.
The transport can send that borrowed asset in bounded operations.
The logical response limit still applies.
The application must account for the asset's storage separately.

The API has no release callback for dynamically leased output buffers.
Neither `finish()` nor cancellation transfers responsibility for releasing such buffers back to arbitrary application code.
Consult the [ownership contract](OWNERSHIP.md) before extending the lifetime model.

### Flush and resume

`flush()` means transmit everything currently committed by the writer.
The method freezes that snapshot and returns an `api.Action`.
The method itself does not wait for network progress.
Return its result immediately from the callback.

The owner drains earlier batched responses and the current snapshot.
Successful transmission schedules the same handler with `event = .flushed`.
The writer then permits another snapshot for the same response.
Resume from saved state without regenerating already committed bytes.

The local socket accepting bytes does not prove that the peer received or processed them.
A disconnect, timeout, or shutdown can prevent the next callback entirely.
An empty flush does not terminate a chunked response.

`finish()` freezes the final snapshot and returns another `api.Action`.
Return that result immediately.
The owner completes response framing without another callback for that response.
Finished responses can remain buffered within a batch before transmission.

### Capacity and `WouldBlock`

`Writer.capacity()` reports conservative body capacity after a flush.
It does not report the arena space currently remaining.
Earlier responses can occupy the shared arena when a new callback begins.

`reserve()` can therefore return `WouldBlock` for a request smaller than `capacity()`.
Preserve continuation state, flush committed output, and retry after `.flushed`.
The `/buffered` handler demonstrates this case.

A reservation larger than `capacity()` needs a different strategy.
Split generated output into pieces no larger than `capacity()` before retrying.
A reservation larger than the entire output arena cannot succeed after any number of flushes.
Update application progress only after committing the corresponding bytes.

### Length, HEAD, and bodyless responses

For a declared `Content-Length`, the cumulative logical body must equal that length at finish.
An excess or short final body closes the connection.
Choose the length before `begin()` because the writer commits headers immediately.

HEAD uses the same callback path as other requests.
The owner suppresses body transmission after validating the callback's logical output.
The callback must still supply the declared logical body through writer calls.
For example, a declared length of 13 still requires 13 logical body bytes before finish.
The reference plaintext handler follows this rule automatically.

Status codes 204 and 304 require zero body bytes in this implementation.
Use zero logical length for those responses.
The writer omits their body framing headers.

## Choose startup limits

Set application limits before `Cluster.init()`.
`Cluster.validate()` checks the combined topology and resource budget.
The [architecture guide](ARCHITECTURE.md#resource-boundaries) explains which resources belong to that accounting.

| Configuration field | Default | Application decision |
| --- | --- | --- |
| `connections` | 128 | Bound admitted connections across the process. |
| `shards` | 0, automatic | Select owner count; start with one for a predictable embedding experiment. |
| `execution` | `.inline_event_loop` | Use bounded nonblocking callbacks, or explicitly choose fixed workers. |
| `workers` | 0 | Choose a positive count with worker execution. |
| `max_body` | 65,536 bytes | Bound decoded request body bytes. |
| `max_header` | 16,384 bytes | Bound the request line, headers, and shared trailer budget. |
| `max_headers` | 64 | Bound the combined header and trailer count. |
| `output_bytes` | 65,536 bytes | Reserve one output arena per slot. |
| `callback_output_reserve` | 384 bytes | Reserve free output before initial callback dispatch; include complete scratch space for one-shot adapters. |
| `response_batch_limit` | 128 | Bound retained response snapshots; worker execution uses one. |
| `max_response_bytes` | 16 MiB | Bound logical response bytes across flushes. |
| `callbacks_per_turn` | 0, automatic | Bound inline callbacks per owner turn. |
| `timeout_ms` | 5000 | Bound a request cycle while the owner can execute. |
| `shutdown_ms` | 5000 | Bound shutdown coordination and drain waits. |
| `memory_budget_bytes` | 512 MiB | Bound requested framework heap and startup stack reservations. |
| `worker_stack_bytes` | 1 MiB | Reserve requested stack space for each worker and secondary owner. |

The reference CLI maps `--execution workers` to two workers unless `--workers` overrides that choice.
Direct library configuration does not apply that CLI default.
Set `workers` explicitly when selecting `.workers` in application code.
Worker execution currently requires one shard.

Automatic inline callback limits use connections multiplied by the effective batch limit, capped at 8192.
Automatic Linux shards use the allowed CPU count, capped at 16.
Automatic macOS and worker configurations use one shard.
Each shard reserves the full configured connection capacity.
More shards therefore increase framework heap requirements despite the shared admission ceiling.

Keep `prearm_receive` false and `submit_batch` zero for the default behavior.
These options remain explicit transport experiments.
Use [Config](../src/server.zig) for complete ranges and less common controls.
Do not set `reuse_port` directly; the cluster owns that setting.

## Application execution and stopping

Inline callbacks must avoid blocking calls, sleeps, and waits for other work.
A slow inline callback stalls every connection owned by that shard.
Fixed workers can separate finite blocking callbacks from network processing.
A blocked worker still delays its assigned slots.

Preallocate application resources before serving requests if the application needs the same allocation discipline as the framework.
The sealed framework allocator does not prevent allocations through unrelated application allocators.
Keep shared application state immutable or synchronize it across concurrent callbacks.
Keep each callback's temporary progress in its own `state` words where practical.

An ordinary control thread can call `cluster.requestStop()` while the cluster remains alive.
Use `cluster.requestStopFromSignal()` for an atomic-only signal stop request.
The helper performs no wake, allocation, logging, or other system call.
Existing polling and callback-progress limits still apply.
Do not introduce logging, allocation, or ordinary shutdown calls into that signal handler.

Collect `cluster.stats()` after `run()` returns and owner threads have stopped.
The current API does not provide synchronized live snapshots of all counters.
Read allocator counters separately, as the reference executable does.
Destroy the cluster only after successful shutdown reconciles its owners.

The framework cannot preempt arbitrary application code.
A stuck callback can prevent internal deadlines from advancing.
Keep an external process watchdog for experiments involving deliberately blocked callbacks.

## Verification and measurement

Before heavy builds, runtime suites, or benchmarks, reserve the execution host with atomic directory creation.
Use `/tmp/zig-http-measurement.lock` on both `maxross` and `omarx1`.
Record owner metadata and inspect existing measurement processes before starting work.
Retain the reservation until every child process has stopped.
Release only your own reservation.
Follow the [wiki platform runbook](https://technologylab-ai.github.io/zigllmwiki/?page=docs/platform-testing.md) for the complete protocol.

The [Linux verification wrapper](../tools/verify_linux_ssh.sh) runs maintained native gates through `ssh omarx1`.
That wrapper does not acquire the host reservation for its caller.
Native results apply to their recorded platform and exact source revision.
Cross-compilation does not establish runtime behavior.

| Tool or suite | Purpose |
| --- | --- |
| `zig build verify` | Check the compiler version, formatting, executable, and registered Zig tests. |
| [integration suites](../tests) | Exercise framing, bounds, partial progress, batches, cancellation, and shutdown. |
| [smoke.py](../tools/smoke.py) | Run a finite verified request smoke experiment. |
| [benchmark.py](../tools/benchmark.py) | Check response bodies while measuring a supplied endpoint. |
| [compare.py](../tools/compare.py) | Run configured contenders with recorded ordering and resource assignments. |

Finish all builds before timed comparisons.
Use ReleaseSafe for timing measurements.
Record compiler, commit, host, CPU assignments, limits, commands, and raw results.
Check returned bodies and server statistics alongside throughput.

The demo prints `STATS` after clean shutdown.
Those counters include operation peaks, connection activity, flush activity, copied bytes, and framework allocation attempts.
Enable `callback_timing` to collect queue and handler timing maxima.
Those maxima remain zero when that option is disabled.
Timing the callbacks adds clock reads to their execution path.

A client can limit measured throughput.
Closed-loop request measurements do not establish an open-loop latency guarantee.
Use [recorded reports](../reports) for existing experiments and their exact scope.
Use the [roadmap](../ROADMAP.md) to identify remaining qualification work.
