const std = @import("std");
const framework = @import("bounded_http");
const api = framework.api;

const Application = struct { greeting: []const u8 = "Hello, World!" };

pub fn main(init: std.process.Init) !void {
    var config: framework.Config = .{
        .port = 8081,
        .connections = 16,
        .execution = .inline_event_loop,
        .workers = 0,
        .shards = 1,
        .duration_ms = 30_000,
        .memory_budget_bytes = 16 * 1024 * 1024,
    };
    var args = try std.process.Args.Iterator.initAllocator(init.minimal.args, init.gpa);
    defer args.deinit();
    _ = args.next();
    while (args.next()) |flag| {
        const value = args.next() orelse return error.MissingArgument;
        if (std.mem.eql(u8, flag, "--port")) {
            config.port = try std.fmt.parseInt(u16, value, 10);
        } else if (std.mem.eql(u8, flag, "--duration-ms")) {
            config.duration_ms = try std.fmt.parseInt(u32, value, 10);
        } else return error.UnknownArgument;
    }
    // The example stops itself after a finite duration without a signal handler.
    if (config.duration_ms == 0) return error.InvalidDuration;
    try framework.Cluster.validate(config);
    var application: Application = .{};
    var budget: framework.Budget = .{
        .upstream = init.gpa,
        .limit_bytes = config.memory_budget_bytes - try framework.Cluster.stackBytes(config),
    };
    defer std.debug.assert(budget.live_bytes == 0);
    const cluster = try framework.Cluster.init(budget.allocator(), config, handler, &application);
    defer cluster.deinit();
    try cluster.start();
    budget.sealed.store(true, .release);
    std.debug.print("READY port={d}\n", .{cluster.port()});
    cluster.run() catch |err| {
        // An uncertain run error can leave callbacks or kernel operations owning memory.
        std.debug.print("FATAL {s}; retained owners require process exit\n", .{@errorName(err)});
        std.c._exit(70);
    };
    var stats = cluster.stats();
    stats.allocation_calls_after_start = budget.late_calls.load(.acquire);
    stats.framework_heap_peak_bytes = budget.peak_bytes;
    stats.framework_heap_limit_bytes = budget.limit_bytes;
    const encoded = try std.json.Stringify.valueAlloc(init.gpa, stats, .{});
    defer init.gpa.free(encoded);
    std.debug.print("STATS {s}\n", .{encoded});
}

fn handler(context: *api.Context) api.Action {
    return respond(context) catch .close;
}

fn respond(context: *api.Context) !api.Action {
    const method = context.request.method;
    if (!std.mem.eql(u8, method, "GET") and !std.mem.eql(u8, method, "HEAD")) {
        try context.writer.begin(501, "text/plain", 0);
        return context.writer.finish();
    }
    // Every callback reads the same immutable greeting throughout the cluster lifetime.
    const application: *const Application = @ptrCast(@alignCast(context.application.?));
    try context.writer.begin(200, "text/plain", application.greeting.len);
    try context.writer.borrow(application.greeting);
    return context.writer.finish();
}
