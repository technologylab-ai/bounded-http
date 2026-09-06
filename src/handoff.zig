const std = @import("std");
const assert = std.debug.assert;

/// One producer and one consumer transfer exclusive ownership through fixed
/// storage. One unused entry distinguishes a full queue from an empty queue.
/// A successful push consumes the caller's optional value before publication.
pub fn Queue(comptime T: type) type {
    return struct {
        const Self = @This();
        entries: []?T,
        read: std.atomic.Value(usize) = .init(0),
        write: std.atomic.Value(usize) = .init(0),

        pub fn init(entries: []?T) Self {
            assert(entries.len >= 2);
            @memset(entries, null);
            return .{ .entries = entries };
        }

        /// Only the producer calls push. Failure preserves caller ownership.
        pub fn push(self: *Self, value: *?T) bool {
            assert(value.* != null);
            const write = self.write.load(.monotonic);
            const next = (write + 1) % self.entries.len;
            if (next == self.read.load(.acquire)) return false;
            assert(self.entries[write] == null);
            self.entries[write] = value.*;
            value.* = null;
            self.write.store(next, .release);
            return true;
        }

        /// Only the consumer calls pop and empty while the owners run.
        pub fn pop(self: *Self) ?T {
            const read = self.read.load(.monotonic);
            if (read == self.write.load(.acquire)) return null;
            const value = self.entries[read].?;
            self.entries[read] = null;
            self.read.store((read + 1) % self.entries.len, .release);
            return value;
        }

        pub fn empty(self: *const Self) bool {
            return self.read.load(.monotonic) == self.write.load(.acquire);
        }
    };
}

test "bounded handoff preserves ownership on full queues and wraps arbitrary capacities" {
    var entries: [4]?u32 = undefined;
    var queue = Queue(u32).init(&entries);
    for (0..100) |turn| {
        for (0..3) |index| {
            var value: ?u32 = @intCast(turn * 3 + index);
            try std.testing.expect(queue.push(&value));
            try std.testing.expect(value == null);
        }
        var retained: ?u32 = 999;
        try std.testing.expect(!queue.push(&retained));
        try std.testing.expectEqual(@as(?u32, 999), retained);
        for (0..3) |index| try std.testing.expectEqual(@as(?u32, @intCast(turn * 3 + index)), queue.pop());
        try std.testing.expect(queue.pop() == null and queue.empty());
    }
}

test "handoff publication and producer completion preserve FIFO across threads" {
    const Fixture = struct {
        queue: Queue(u32),
        done: std.atomic.Value(bool) = .init(false),
        failed: std.atomic.Value(bool) = .init(false),

        fn produce(self: *@This()) void {
            for (0..10000) |index| {
                var value: ?u32 = @intCast(index);
                var attempts: usize = 0;
                while (!self.queue.push(&value)) : (attempts += 1) {
                    if (attempts == 1000000) {
                        self.failed.store(true, .release);
                        self.done.store(true, .release);
                        return;
                    }
                    std.Thread.yield() catch {};
                }
            }
            self.done.store(true, .release);
        }
    };
    var entries: [8]?u32 = undefined;
    var fixture: Fixture = .{ .queue = Queue(u32).init(&entries) };
    const producer = try std.Thread.spawn(.{}, Fixture.produce, .{&fixture});
    defer producer.join();
    var received: u32 = 0;
    var ordered = true;
    // The producer has a finite attempt budget even if the consumer regresses.
    while (true) {
        if (fixture.queue.pop()) |value| {
            ordered = ordered and value == received;
            received += 1;
        } else if (fixture.done.load(.acquire) and fixture.queue.empty()) {
            // Acquire completion first, then recheck the queue. A producer may
            // publish its last entry between the earlier pop and this acquire.
            break;
        } else std.Thread.yield() catch {};
    }
    try std.testing.expect(!fixture.failed.load(.acquire));
    try std.testing.expect(ordered);
    try std.testing.expectEqual(@as(u32, 10000), received);
}
