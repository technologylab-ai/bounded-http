# Module contracts

Exact Zig 0.16.0. The maintained parser, server, writer and platform adapters
share the ownership contract in [OWNERSHIP.md](OWNERSHIP.md).

## HTTP parser

`Limits`: max_header_bytes u32, max_header_count u16, max_body_bytes u32,
max_wire_bytes u32, max_target_bytes u16. Defaults may be declared by parser.
`Parser.init(limits)`, `reset()` and `parse(bytes: []const u8) ParseError!?Request`.
Input is one stable contiguous receive buffer; each call extends the prefix.
The parser retains scan state to avoid rescanning all earlier bytes. Reset
clears parser metadata; older response cells may still borrow immutable input.
Only the server knows when every such borrow has ended and compaction is safe.
Public `head_complete`, `expect_continue`, `headers_end` allow an interim 100
after validated headers and before waiting for a body. No allocation.

`Request`: method and target byte slices; raw headers slice; body_wire slice;
chunked bool; body_bytes usize; consumed usize; keep_alive bool;
expect_continue bool; head_only bool. `header(name)` returns first borrowed
match or null, `body()` returns iterator with `next() ?[]const u8` returning
logical body spans (skip chunk framing without coalescing copies).

`ParseError`: BadRequest, HeadersTooLarge, BodyTooLarge, TargetTooLong,
UnsupportedTransferEncoding, ExpectationFailed, UnsupportedVersion.

## Transport

`src/transport.zig` exports selected `Backend`, `Socket` (i32 for POSIX MVP),
`Completion { token: u64, result: i32 }` and `name`.
Operations are addressed by caller-chosen cells: `cellCount(max_connections)`
= `4 × max_connections + 2` fixed records. The server numbers them receive
cell = slot index, send cell = slots + index, their cancel cells at 2 × slots
and 3 × slots, then accept and cancel-accept.
One cell never holds two live operations, so admission and completion matching
are constant-time and the token is returned from the record.
Backend methods: `init(allocator, max_connections: u16, port: u16, reuse_port: bool) !Backend`,
`deinit()`, `accept(cell: u32, token: u64) !void`,
`recv(cell, token, socket, buffer: []u8) !void`,
`send(cell, token, socket, bytes: []const u8) !void`,
`enableGather() !void` during startup,
`sendv(cell, token, socket, vectors: []const iovec_const) !void`,
`cancel(cell, token, target_cell: u32) !void`,
`poll(out: []Completion, timeout_ms: u32) !usize`,
`flush() !void` to submit queued operations before the next poll,
`close(cell, socket) void`, `shutdown(socket) void`, `port() u16`.
Accepted sockets are returned as nonnegative completion results; zero recv is EOF;
negative results are terminal OS failures. Cancellation reports target and
cancel-request completions separately; cancelling an idle cell reports ENOENT.
Buffers and gather vectors remain borrowed until the target completion, and
close is only after outstanding operations return. A busy cell yields
`error.OperationCellBusy`. `wake()` is thread-safe for worker completions.

Linux uses actual low-level io_uring accept/recv/send, runtime opcode probes,
finite queues and explicit cancel drain. macOS uses nonblocking sockets/kqueue
and the same completion interface. IPv4 loopback binding initially; CLI can
expose other bind addresses later. No per-operation allocation.

Gather vectors live in the caller's per-connection startup storage; the adapter
points its msghdr at them and copies nothing. Up to `max_vectors` (1024) may be
submitted; the server bounds a batch at `2 × response_batch_limit + 1`. The
server caps aggregate bytes and advances partial sends across vector
boundaries. Adapter `operation_bytes` allows Config.heapBytes to include exact
requested operation storage; these counts exclude kernel ring/socket allocations.
With `reuse_port`, several backends bind one port and Linux distributes
connections across them in the tested configuration. The M3 Max branch fixture
observed every connection at the last-bound listener, so the current macOS
configuration rejects multiple shards. That observation is not a universal
XNU API guarantee.


## Cluster startup and application ownership

`Cluster.requestStopFromSignal()` only sets atomic shard stop flags.
The caller must retain the cluster throughout signal-handler access.
The method performs no wake or other system call.
Ordinary control threads can continue to use `Cluster.requestStop()`.

`Cluster.init` validates the process-wide admitted-connection ceiling and exact
requested heap plus startup stacks. Each shard reserves full connection storage.
`Cluster.start` prepares workers and secondary owners behind a release gate;
the caller seals its allocator before `Cluster.run` releases request I/O.
Partial startup aborts without dispatching callbacks. Secondary-owner failure
requests cluster stop; finite exit acknowledgements precede joins, with process
exit70 when ownership cannot be reconciled. See OWNERSHIP.md for embedding and
external-watchdog requirements. The same application pointer is shared between
shards: simultaneous handlers on different connections require immutable or
synchronized application state. Worker dispatch uses a slot-owned header cache
snapshot; inline dispatch reads its owner's cache directly.

## Unpublished response adapters

`Config.callback_output_reserve` bounds required free arena bytes before initial dispatch.
The default is `api.header_reserve_bytes`; the configured value must fit `output_bytes`.
The owner drains older output before dispatch when the reservation cannot fit.
This admission check preserves each request and prevents callback replay.

`Writer.draftStorage(required_bytes)` exposes only the current fresh response's requested scratch range.
`Writer.discardDraft()` resets an unpublished response without changing earlier frozen prefixes.
`Writer.writeDraftBody(bytes)` copies staged body bytes with overlap support and records the copied byte count.
These methods replace external access to writer fields and internal lifecycle methods.

`Writer.beginWithHeaders(status, content_type, length, extra_headers)` validates the complete head before mutation.
The writer copies Content-Type and complete CRLF-terminated additional header lines during the call.
Arena-backed inputs must use disjoint ranges after the current snapshot's `header_reserve_bytes` prefix.
Those ranges may become committed output during compaction and must not be overwritten afterward.
The caller reserves sufficient head and draft space before dispatch.
`Stats.response_draft_copy_bytes` records generated-body compaction separately from borrowed-body copies.
