# Bounded application notifications

A producer can wake a retained HTTP callback without occupying an application
worker while it waits. `Context.notification()` returns a copyable
`api.Notification` handle. Publish application data first, then call
`handle.signal()` from the producer. In the callback, return
`try context.waitNotification(timeout_ns)`; null means no heartbeat timeout.
The original request deadline remains in force.

A signal resumes the callback with `.notified`; the optional timer resumes it
with `.timer`. `Context.wait(delay_ns)` remains a timer-only operation. A pending
notification takes precedence over an optional notification timer at an owner
poll. Callbacks must flush pending output before either kind of wait. Like timed
continuations, a notification wait can precede first output and retain input
while an earlier pipelined response batch drains.

## Bounds and ownership

Each connection has one startup-reserved atomic notification cell. Its size is
included in the existing slot/heap accounting. Signals coalesce into one pending
bit: `signal()` returns `notified`, `coalesced` or `stale`, never a message count.
A signal received before waiting, during a callback or during a transport flush
stays pending until a notification wait consumes it. The application supplies
bounded data queues and decides how to handle their exhaustion.
The queue must synchronize its own data access. A notification does not provide
a publication barrier for unrelated application memory.

The owner scans armed waits at the existing polling cadence (up to 10 ms plus
scheduling/load delays). This implementation adds no OS wake primitive, thread,
allocation, blocking wait or new `std.Io` provider. Notification latency is not
an immediate-wakeup guarantee. Inline callbacks must still do bounded,
nonblocking work; worker callbacks still use the fixed startup pool.

Generations advance for every request, including requests on one keep-alive
connection, and never wrap. Exhaustion retires the cell. Terminal callbacks and
connection close invalidate handles atomically. Old handles cannot wake a
subsequent request in the same connection slot.

A handle does **not** extend storage lifetime. Stop and join every producer
before `Server.deinit` or `Cluster.deinit`, even when its request has already
finished and its handle returns `stale`. Producers keep notification handles,
not Context, writer or request pointers. Their application messages have their
own explicit ownership obligations.

Only the request owner consumes the bit, while no callback is running. Signals
use a bounded strong compare-and-swap attempt. Repeated signals are linearized
at observing the pending bit; they do not acknowledge application processing.
Request cancellation still resumes opted-in retained callbacks exactly once,
on the configured executor, after application/kernel borrows reconcile. A
cancelled callback only cleans up and closes; it cannot send or wait again.

## Verification

`zig build verify` includes cell coalescing/generation/retirement and scheduler
ownership tests. `tests/continuation_integration.py` exercises signals before a
wait, after a real parked wait, across output flushes and previous pipeline
batches, optional timeout precedence, disconnect, deadline, shutdown, stale
handles and slot reuse. Run the installed ReleaseSafe binary; native platform
receipts are required before promoting these additions. Cross-compilation is
not runtime evidence. Existing transport/backpressure gates remain separate.
