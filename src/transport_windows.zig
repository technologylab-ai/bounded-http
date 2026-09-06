//! Single-owner public Win32 IOCP adapter, separate from std.Io.Threaded/APC.
//! Default notification policy: immediate success still owns a terminal packet.
//! No FILE_SKIP_COMPLETION_PORT_ON_SUCCESS or low-bit OVERLAPPED event is used.
//! Payloads remain borrowed until collection; WSASend is ordinary copying I/O.
//!
//! Primary contracts: MicrosoftDocs/sdk-api@5f2625b6782d3e9c0df08756583c527a0a2872ca,
//! sdk-api-src/content/{ioapiset,winsock2,mswsock}; in particular nf-mswsock-acceptex.md,
//! nf-ioapiset-{cancelioex,getqueuedcompletionstatusex}.md and nf-winsock2-wsasend.md.
//! ABI declarations follow Zig 0.16.0's bundled Windows SDK headers. The sibling
//! wiki's windows_iocp_lifecycle and windows_iocp_tcp_file proofs preserve prior
//! evidence; their native results do not verify this new HTTP adapter.
const std = @import("std");
const common = @import("transport.zig");
const windows = std.os.windows;
const ws = windows.ws2_32;
const Socket = common.Socket;
const Completion = common.Completion;
const assert = std.debug.assert;
const invalid_socket = std.math.maxInt(usize);
const pending_error = 997;
const incomplete_error = 996;
const aborted_error = 995;
const not_found_error = 1168;
const timeout_error = 258;
const wake_key = std.math.maxInt(usize);
const data_key: usize = 1;
const address_bytes = @sizeOf(ws.sockaddr.in) + 16;

const Overlapped = extern struct {
    internal: usize = 0,
    internal_high: usize = 0,
    offset: u32 = 0,
    offset_high: u32 = 0,
    event: ?windows.HANDLE = null,
};
const Entry = extern struct { key: usize, overlapped: ?*Overlapped, internal_reserved: usize, bytes: u32 };
const Buffer = extern struct { len: u32, ptr: [*]u8 };
const Guid = extern struct { first: u32, second: u16, third: u16, rest: [8]u8 };
const AcceptEx = *const fn (usize, usize, [*]u8, u32, u32, u32, *u32, *Overlapped) callconv(.winapi) i32;
const WsaData = if (@sizeOf(usize) == 8) extern struct {
    version: u16,
    high_version: u16,
    max_sockets: u16,
    max_udp: u16,
    vendor: ?[*]u8,
    description: [257]u8,
    system_status: [129]u8,
} else extern struct {
    version: u16,
    high_version: u16,
    description: [257]u8,
    system_status: [129]u8,
    max_sockets: u16,
    max_udp: u16,
    vendor: ?[*]u8,
};
const win32 = struct {
    extern "kernel32" fn CreateIoCompletionPort(windows.HANDLE, ?windows.HANDLE, usize, u32) callconv(.winapi) ?windows.HANDLE;
    extern "kernel32" fn GetQueuedCompletionStatusEx(windows.HANDLE, [*]Entry, u32, *u32, u32, i32) callconv(.winapi) i32;
    extern "kernel32" fn PostQueuedCompletionStatus(windows.HANDLE, u32, usize, ?*Overlapped) callconv(.winapi) i32;
    extern "kernel32" fn GetOverlappedResult(windows.HANDLE, *Overlapped, *u32, i32) callconv(.winapi) i32;
    extern "kernel32" fn CancelIoEx(windows.HANDLE, *Overlapped) callconv(.winapi) i32;
    extern "kernel32" fn GetLastError() callconv(.winapi) u32;
    extern "kernel32" fn Sleep(u32) callconv(.winapi) void;
    extern "kernel32" fn GetTickCount64() callconv(.winapi) u64;
    extern "ws2_32" fn WSAStartup(u16, *WsaData) callconv(.winapi) i32;
    extern "ws2_32" fn WSACleanup() callconv(.winapi) i32;
    extern "ws2_32" fn WSAGetLastError() callconv(.winapi) i32;
    extern "ws2_32" fn WSASocketW(i32, i32, i32, ?*anyopaque, u32, u32) callconv(.winapi) usize;
    extern "ws2_32" fn WSAIoctl(usize, u32, ?*const anyopaque, u32, ?*anyopaque, u32, *u32, ?*Overlapped, ?*anyopaque) callconv(.winapi) i32;
    extern "ws2_32" fn bind(usize, *const ws.sockaddr, i32) callconv(.winapi) i32;
    extern "ws2_32" fn listen(usize, i32) callconv(.winapi) i32;
    extern "ws2_32" fn getsockname(usize, *ws.sockaddr, *i32) callconv(.winapi) i32;
    extern "ws2_32" fn setsockopt(usize, i32, i32, *const anyopaque, i32) callconv(.winapi) i32;
    extern "ws2_32" fn closesocket(usize) callconv(.winapi) i32;
    extern "ws2_32" fn shutdown(usize, i32) callconv(.winapi) i32;
    extern "ws2_32" fn WSARecv(usize, [*]Buffer, u32, ?*u32, *u32, *Overlapped, ?*anyopaque) callconv(.winapi) i32;
    extern "ws2_32" fn WSASend(usize, [*]const Buffer, u32, ?*u32, u32, *Overlapped, ?*anyopaque) callconv(.winapi) i32;
    extern "ws2_32" fn WSAGetOverlappedResult(usize, *Overlapped, *u32, i32, *u32) callconv(.winapi) i32;
};

fn createSocket() !usize {
    // Kernel/provider resource creation is bounded by the socket table. These
    // control calls are not a hard-real-time or arbitrary-provider guarantee.
    const socket = win32.WSASocketW(ws.AF.INET, ws.SOCK.STREAM, ws.IPPROTO.TCP, null, 0, 0x01 | 0x80);
    if (socket == invalid_socket) return error.SocketFailed;
    return socket;
}

fn closeSocket(socket: usize) void {
    assert(socket != invalid_socket);
    // Linger is never enabled, and no outstanding operation may borrow this handle.
    assert(win32.closesocket(socket) == 0);
}

fn negative(code: u32) i32 {
    const err: std.c.E = switch (code) {
        aborted_error => .CANCELED,
        not_found_error => .NOENT,
        10054 => .CONNRESET,
        10053 => .CONNABORTED,
        10055 => .NOBUFS,
        10060 => .TIMEDOUT,
        else => .IO,
    };
    return -@as(i32, @intFromEnum(err));
}

pub const Backend = struct {
    const Kind = enum { free, accept, recv, send, sendv, cancel };
    const Operation = struct {
        overlapped: Overlapped = .{},
        kind: Kind = .free,
        token: u64 = 0,
        socket: Socket = -1,
        result: ?i32 = null,
        submitted: bool = false,
        flags: u32 = 0,
        length: u32 = 0,
        buffer: Buffer = undefined,
        vectors: []const std.c.iovec_const = &.{},
        addresses: [2 * address_bytes]u8 = undefined,
    };
    const SocketEntry = struct { handle: usize = invalid_socket, owned: u32 = 0, next: ?u32 = null };
    pub const operation_bytes = @sizeOf(Operation) + @sizeOf(u32);

    allocator: std.mem.Allocator,
    operations: []Operation,
    ready: []u32,
    ready_head: usize = 0,
    ready_count: usize = 0,
    sockets: []SocketEntry,
    free_socket: ?u32,
    socket_count: usize = 0,
    outstanding: usize = 0,
    listener: usize,
    queue: windows.HANDLE,
    accept_ex: AcceptEx,
    bound_port: u16,
    gather_enabled: bool = false,
    wake_pending: std.atomic.Value(bool) = .init(false),
    poll_failed: bool = false,
    /// One owner reuses these descriptors only after WSASend captures them.
    /// Payloads and the caller's vectors remain borrowed until collection.
    send_buffers: [common.max_vectors]Buffer = undefined,

    pub fn heapBytes(max_connections: u16) !usize {
        const operations = try std.math.mul(usize, common.cellCount(max_connections), operation_bytes);
        return std.math.add(usize, operations, try std.math.mul(usize, @as(usize, max_connections) + 1, @sizeOf(SocketEntry)));
    }

    pub fn init(allocator: std.mem.Allocator, max_connections: u16, port_number: u16, reuse_port: bool) !Backend {
        if (max_connections == 0 or max_connections > 16383) return error.InvalidConnectionLimit;
        if (reuse_port) return error.ReusePortUnsupported;
        var wsa_data: WsaData = undefined;
        if (win32.WSAStartup(0x0202, &wsa_data) != 0) return error.WinsockStartupFailed;
        errdefer assert(win32.WSACleanup() == 0);
        if (wsa_data.version != 0x0202) return error.WinsockVersionUnsupported;
        const operations = try allocator.alloc(Operation, common.cellCount(max_connections));
        errdefer allocator.free(operations);
        @memset(operations, .{});
        const ready = try allocator.alloc(u32, operations.len);
        errdefer allocator.free(ready);
        const sockets = try allocator.alloc(SocketEntry, @as(usize, max_connections) + 1);
        errdefer allocator.free(sockets);
        for (sockets, 0..) |*entry, index| entry.* = .{ .next = if (index + 1 < sockets.len) @intCast(index + 1) else null };
        const listener = try createSocket();
        errdefer closeSocket(listener);
        const one: i32 = 1;
        // No SO_REUSEADDR: Windows interprets that option differently from POSIX.
        if (win32.setsockopt(listener, ws.SOL.SOCKET, ~@as(i32, ws.SO.REUSEADDR), &one, @sizeOf(i32)) != 0) return error.SocketOptionFailed;
        var address: ws.sockaddr.in = .{ .port = std.mem.nativeToBig(u16, port_number), .addr = std.mem.nativeToBig(u32, 0x7f000001) };
        if (win32.bind(listener, @ptrCast(&address), @sizeOf(@TypeOf(address))) != 0) return error.BindFailed;
        if (win32.listen(listener, @intCast(max_connections)) != 0) return error.ListenFailed;
        var length: i32 = @sizeOf(@TypeOf(address));
        if (win32.getsockname(listener, @ptrCast(&address), &length) != 0) return error.SocketNameFailed;
        const guid: Guid = .{ .first = 0xb5367df1, .second = 0xcbac, .third = 0x11cf, .rest = .{ 0x95, 0xca, 0x00, 0x80, 0x5f, 0x48, 0xa1, 0x92 } };
        var accept_ex: AcceptEx = undefined;
        var returned: u32 = 0;
        // Resolve the listener's provider extension at startup, before IOCP association.
        if (win32.WSAIoctl(listener, 0xc8000006, &guid, @sizeOf(Guid), @ptrCast(&accept_ex), @sizeOf(AcceptEx), &returned, null, null) != 0 or returned != @sizeOf(AcceptEx)) return error.AcceptExUnavailable;
        const queue = win32.CreateIoCompletionPort(@ptrFromInt(invalid_socket), null, 0, 1) orelse return error.IocpCreateFailed;
        errdefer windows.CloseHandle(queue);
        if (win32.CreateIoCompletionPort(@ptrFromInt(listener), queue, data_key, 0) != queue) return error.IocpAssociateFailed;
        return .{ .allocator = allocator, .operations = operations, .ready = ready, .sockets = sockets, .free_socket = 0, .listener = listener, .queue = queue, .accept_ex = accept_ex, .bound_port = std.mem.bigToNative(u16, address.port) };
    }

    pub fn enableGather(self: *Backend) !void {
        assert(self.outstanding == 0 and !self.gather_enabled);
        self.gather_enabled = true;
    }

    pub fn deinit(self: *Backend) void {
        // The engine must drain both target and cancel cells, then close sockets.
        // A failed shutdown retains this storage and terminates the whole process.
        assert(self.outstanding == 0 and self.ready_count == 0 and self.socket_count == 0);
        for (self.operations) |op| assert(op.kind == .free);
        closeSocket(self.listener);
        windows.CloseHandle(self.queue);
        self.allocator.free(self.sockets);
        self.allocator.free(self.ready);
        self.allocator.free(self.operations);
        assert(win32.WSACleanup() == 0);
        self.* = undefined;
    }

    fn claim(self: *Backend, cell: u32, kind: Kind, token: u64) !*Operation {
        if (cell >= self.operations.len) return error.OperationCellInvalid;
        const op = &self.operations[cell];
        if (op.kind != .free) return error.OperationCellBusy;
        op.* = .{ .kind = kind, .token = token };
        self.outstanding += 1;
        assert(self.outstanding <= self.operations.len);
        return op;
    }

    fn socketEntry(self: *Backend, socket: Socket) *SocketEntry {
        assert(socket >= 0 and socket < self.sockets.len);
        const entry = &self.sockets[@intCast(socket)];
        assert(entry.handle != invalid_socket);
        return entry;
    }

    fn allocateSocket(self: *Backend) !Socket {
        const index = self.free_socket orelse return error.SocketCapacityExceeded;
        const entry = &self.sockets[index];
        assert(entry.handle == invalid_socket and entry.owned == 0);
        const handle = try createSocket();
        self.free_socket = entry.next;
        entry.* = .{ .handle = handle };
        self.socket_count += 1;
        assert(self.socket_count <= self.sockets.len);
        return @intCast(index);
    }

    fn finish(self: *Backend, op: *Operation, result: i32) void {
        assert(op.kind != .free and !op.submitted and op.result == null);
        op.result = result;
        const index = (@intFromPtr(op) - @intFromPtr(self.operations.ptr)) / @sizeOf(Operation);
        assert(index < self.operations.len and self.ready_count < self.ready.len);
        self.ready[(self.ready_head + self.ready_count) % self.ready.len] = @intCast(index);
        self.ready_count += 1;
    }

    fn initiation(self: *Backend, op: *Operation, immediate: bool) void {
        const code: u32 = if (immediate) 0 else @intCast(win32.WSAGetLastError());
        if (code == 0 or code == pending_error) {
            // Immediate success still queues exactly one data packet.
            op.submitted = true;
        } else self.finish(op, negative(code));
    }

    pub fn accept(self: *Backend, cell: u32, token: u64) !void {
        const op = try self.claim(cell, .accept, token);
        op.socket = self.allocateSocket() catch {
            self.finish(op, negative(10055));
            return;
        };
        self.socketEntry(op.socket).owned += 1;
        var received: u32 = 0;
        const immediate = self.accept_ex(self.listener, self.socketEntry(op.socket).handle, &op.addresses, 0, address_bytes, address_bytes, &received, &op.overlapped) != 0;
        // Zero receive length prevents an idle peer from withholding acceptance.
        self.initiation(op, immediate);
    }

    pub fn recv(self: *Backend, cell: u32, token: u64, socket: Socket, buffer: []u8) !void {
        assert(buffer.len > 0 and buffer.len <= std.math.maxInt(i32));
        const entry = self.socketEntry(socket);
        const op = try self.claim(cell, .recv, token);
        op.socket = socket;
        op.length = @intCast(buffer.len);
        op.buffer = .{ .len = op.length, .ptr = buffer.ptr };
        entry.owned += 1;
        self.initiation(op, win32.WSARecv(entry.handle, @ptrCast(&op.buffer), 1, null, &op.flags, &op.overlapped, null) == 0);
    }

    pub fn send(self: *Backend, cell: u32, token: u64, socket: Socket, bytes: []const u8) !void {
        assert(bytes.len > 0 and bytes.len <= std.math.maxInt(i32));
        const entry = self.socketEntry(socket);
        const op = try self.claim(cell, .send, token);
        op.socket = socket;
        op.length = @intCast(bytes.len);
        op.buffer = .{ .len = op.length, .ptr = @constCast(bytes.ptr) };
        entry.owned += 1;
        self.initiation(op, win32.WSASend(entry.handle, @ptrCast(&op.buffer), 1, null, 0, &op.overlapped, null) == 0);
    }

    pub fn sendv(self: *Backend, cell: u32, token: u64, socket: Socket, vectors: []const std.c.iovec_const) !void {
        if (!self.gather_enabled) return error.GatherSendNotEnabled;
        assert(vectors.len > 0 and vectors.len <= common.max_vectors);
        var length: usize = 0;
        for (vectors, self.send_buffers[0..vectors.len]) |vector, *buffer| {
            length = try std.math.add(usize, length, vector.len);
            if (length > std.math.maxInt(i32)) return error.SendTooLarge;
            buffer.* = .{ .len = @intCast(vector.len), .ptr = @constCast(vector.base) };
        }
        assert(length > 0);
        const entry = self.socketEntry(socket);
        const op = try self.claim(cell, .sendv, token);
        op.socket = socket;
        op.length = @intCast(length);
        op.vectors = vectors;
        entry.owned += 1;
        self.initiation(op, win32.WSASend(entry.handle, &self.send_buffers, @intCast(vectors.len), null, 0, &op.overlapped, null) == 0);
    }

    pub fn cancel(self: *Backend, cell: u32, token: u64, target_cell: u32) !void {
        assert(cell != target_cell and target_cell < self.operations.len);
        const cancellation = try self.claim(cell, .cancel, token);
        const target = &self.operations[target_cell];
        var result = negative(not_found_error);
        if (target.submitted) {
            assert(target.kind != .free and target.kind != .cancel and target.result == null);
            const handle = if (target.kind == .accept) self.listener else self.socketEntry(target.socket).handle;
            result = if (win32.CancelIoEx(@ptrFromInt(handle), &target.overlapped) != 0) 0 else negative(win32.GetLastError());
        }
        // Cancellation only requests action. The target retains all ownership
        // until its own packet, including ERROR_NOT_FOUND completion races.
        self.finish(cancellation, result);
    }

    pub fn flush(_: *Backend) !void {}

    fn retire(self: *Backend, entry: Entry) void {
        const overlapped = entry.overlapped orelse {
            assert(entry.key == wake_key and entry.bytes == 0);
            assert(self.wake_pending.swap(false, .acq_rel));
            return;
        };
        assert(entry.key == data_key);
        const first = @intFromPtr(&self.operations[0].overlapped);
        const address = @intFromPtr(overlapped);
        assert(address >= first);
        const delta = address - first;
        assert(delta % @sizeOf(Operation) == 0 and delta / @sizeOf(Operation) < self.operations.len);
        const op = &self.operations[delta / @sizeOf(Operation)];
        assert(op.submitted and op.result == null and op.kind != .free and op.kind != .cancel);
        const handle = if (op.kind == .accept) self.listener else self.socketEntry(op.socket).handle;
        var bytes: u32 = 0;
        var flags: u32 = 0;
        const success = if (op.kind == .accept)
            win32.GetOverlappedResult(@ptrFromInt(handle), overlapped, &bytes, 0) != 0
        else
            win32.WSAGetOverlappedResult(handle, overlapped, &bytes, 0, &flags) != 0;
        const code: u32 = if (success) 0 else if (op.kind == .accept) win32.GetLastError() else @intCast(win32.WSAGetLastError());
        // A packet with an incomplete target contradicts the ownership contract.
        // Assert before releasing any buffer; do not inspect reserved NTSTATUS.
        assert(code != incomplete_error);
        op.submitted = false;
        var result: i32 = if (success) @intCast(bytes) else negative(code);
        if (success) {
            assert(bytes == entry.bytes and bytes <= op.length);
            if (op.kind == .accept) {
                const socket = self.socketEntry(op.socket).handle;
                const one: i32 = 1;
                if (win32.setsockopt(socket, ws.SOL.SOCKET, 0x700b, &self.listener, @sizeOf(usize)) != 0 or
                    win32.setsockopt(socket, ws.IPPROTO.TCP, ws.TCP.NODELAY, &one, @sizeOf(i32)) != 0 or
                    win32.CreateIoCompletionPort(@ptrFromInt(socket), self.queue, data_key, 0) != self.queue)
                {
                    result = negative(0);
                } else result = op.socket;
            }
        }
        self.finish(op, result);
    }

    fn collect(self: *Backend, out: []Completion) usize {
        var count: usize = 0;
        while (count < out.len and self.ready_count > 0) {
            const cell = self.ready[self.ready_head];
            self.ready_head = (self.ready_head + 1) % self.ready.len;
            self.ready_count -= 1;
            const op = &self.operations[cell];
            assert(op.kind != .free and !op.submitted and op.result != null and self.outstanding > 0);
            if (op.socket >= 0) {
                const socket = self.socketEntry(op.socket);
                assert(socket.owned > 0);
                socket.owned -= 1;
                if (op.kind == .accept and op.result.? < 0) self.releaseSocket(op.socket);
            }
            out[count] = .{ .token = op.token, .result = op.result.? };
            count += 1;
            op.* = .{};
            self.outstanding -= 1;
        }
        return count;
    }

    pub fn poll(self: *Backend, out: []Completion, timeout_ms: u32) !usize {
        assert(out.len > 0 and timeout_ms < std.math.maxInt(u32));
        if (self.poll_failed) return error.IocpPollFailed;
        const collected = self.collect(out);
        var entries: [256]Entry = undefined;
        var count: u32 = 0;
        if (win32.GetQueuedCompletionStatusEx(self.queue, &entries, entries.len, &count, if (collected > 0) 0 else timeout_ms, 0) == 0) {
            if (win32.GetLastError() == timeout_error) return collected;
            self.poll_failed = true;
            // Already returned results transferred ownership; surface a port
            // failure on the next call instead of discarding those completions.
            if (collected > 0) return collected;
            return error.IocpPollFailed;
        }
        assert(count > 0 and count <= entries.len);
        for (entries[0..count]) |entry| self.retire(entry);
        return collected + if (collected < out.len) self.collect(out[collected..]) else @as(usize, 0);
    }

    pub fn wake(self: *Backend) void {
        if (self.wake_pending.swap(true, .acq_rel)) return;
        if (win32.PostQueuedCompletionStatus(self.queue, 0, wake_key, null) == 0) {
            // The engine's finite polling deadline remains the fallback.
            self.wake_pending.store(false, .release);
        }
    }

    fn releaseSocket(self: *Backend, socket: Socket) void {
        const entry = self.socketEntry(socket);
        assert(entry.owned == 0 and self.socket_count > 0);
        closeSocket(entry.handle);
        entry.* = .{ .next = self.free_socket };
        self.free_socket = @intCast(socket);
        self.socket_count -= 1;
    }

    pub fn close(self: *Backend, cell: u32, socket: Socket) void {
        assert(cell < self.operations.len and self.operations[cell].kind == .free);
        self.releaseSocket(socket);
    }

    pub fn setSendBuffer(self: *Backend, socket: Socket, bytes: u32) !void {
        assert(bytes > 0 and bytes <= std.math.maxInt(i32));
        const value: i32 = @intCast(bytes);
        if (win32.setsockopt(self.socketEntry(socket).handle, ws.SOL.SOCKET, ws.SO.SNDBUF, &value, @sizeOf(i32)) != 0) return error.SocketOptionFailed;
    }

    pub fn shutdown(self: *Backend, socket: Socket) void {
        _ = win32.shutdown(self.socketEntry(socket).handle, 2);
    }

    pub fn port(self: *const Backend) u16 {
        return self.bound_port;
    }
};

const fixture = struct {
    extern "ws2_32" fn connect(usize, *const ws.sockaddr, i32) callconv(.winapi) i32;
    extern "ws2_32" fn send(usize, [*]const u8, i32, i32) callconv(.winapi) i32;
    extern "ws2_32" fn recv(usize, [*]u8, i32, i32) callconv(.winapi) i32;

    fn client(port_number: u16) !usize {
        const socket = try createSocket();
        errdefer closeSocket(socket);
        const timeout: u32 = 1000;
        if (win32.setsockopt(socket, ws.SOL.SOCKET, ws.SO.RCVTIMEO, &timeout, @sizeOf(u32)) != 0 or
            win32.setsockopt(socket, ws.SOL.SOCKET, ws.SO.SNDTIMEO, &timeout, @sizeOf(u32)) != 0) return error.ClientTimeoutFailed;
        var address: ws.sockaddr.in = .{ .port = std.mem.nativeToBig(u16, port_number), .addr = std.mem.nativeToBig(u32, 0x7f000001) };
        // Only this fixture uses blocking connection setup. The hosted process
        // watchdog bounds a stuck provider; the HTTP owner uses AcceptEx.
        if (connect(socket, @ptrCast(&address), @sizeOf(@TypeOf(address))) != 0) return error.ClientConnectFailed;
        return socket;
    }

    fn completion(backend: *Backend) !Completion {
        var out: [1]Completion = undefined;
        const deadline = win32.GetTickCount64() + 3000;
        while (win32.GetTickCount64() < deadline) {
            if (try backend.poll(&out, 20) == 1) return out[0];
        }
        return error.CompletionDeadline;
    }

    fn readExact(socket: usize, bytes: []u8) !void {
        const deadline = win32.GetTickCount64() + 3000;
        var offset: usize = 0;
        while (offset < bytes.len) {
            if (win32.GetTickCount64() >= deadline) return error.ClientReadDeadline;
            const count = recv(socket, bytes[offset..].ptr, @intCast(bytes.len - offset), 0);
            if (count <= 0) return error.ClientReadFailed;
            offset += @intCast(count);
        }
    }
};

test "IOCP exact startup storage includes socket table and rejects one byte short" {
    const Budget = @import("budget.zig").Budget;
    const required = try Backend.heapBytes(2);
    var short: Budget = .{ .upstream = std.testing.allocator, .limit_bytes = required - 1 };
    try std.testing.expectError(error.OutOfMemory, Backend.init(short.allocator(), 2, 0, false));
    try std.testing.expectEqual(@as(usize, 0), short.live_bytes);
    var exact: Budget = .{ .upstream = std.testing.allocator, .limit_bytes = required };
    var backend = try Backend.init(exact.allocator(), 2, 0, false);
    try std.testing.expectEqual(required, exact.live_bytes);
    exact.sealed.store(true, .release);
    try backend.accept(8, 11);
    try backend.cancel(9, 12, 8);
    for (0..2) |_| _ = try fixture.completion(&backend);
    backend.deinit();
    try std.testing.expectEqual(@as(usize, 0), exact.live_bytes);
    try std.testing.expectEqual(@as(usize, 0), exact.late_calls.load(.acquire));
}

test "IOCP accepts without initial data and retains receive gather and EOF ownership" {
    var backend = try Backend.init(std.testing.allocator, 2, 0, false);
    defer backend.deinit();
    try backend.enableGather();
    const client = try fixture.client(backend.port());
    defer closeSocket(client);
    try backend.accept(8, 21);
    const accepted = try fixture.completion(&backend);
    try std.testing.expectEqual(@as(u64, 21), accepted.token);
    try std.testing.expect(accepted.result >= 0);
    const peer = accepted.result;
    defer backend.close(0, peer);
    try backend.setSendBuffer(peer, 1024);
    var input: [32]u8 = undefined;
    try backend.recv(0, 22, peer, &input);
    const payload = "borrowed input";
    try std.testing.expectEqual(@as(i32, payload.len), fixture.send(client, payload, payload.len, 0));
    const received = try fixture.completion(&backend);
    try std.testing.expectEqual(@as(u64, 22), received.token);
    try std.testing.expectEqual(@as(i32, payload.len), received.result);
    try std.testing.expectEqualStrings(payload, input[0..payload.len]);
    const vectors = [_]std.c.iovec_const{ common.vector("header:"), common.vector("body"), common.vector(":end") };
    const expected = "header:body:end";
    var offset: usize = 0;
    for (0..expected.len) |_| {
        if (offset == expected.len) break;
        var skip = offset;
        var selected: [3]std.c.iovec_const = undefined;
        var count: usize = 0;
        for (vectors) |vector| {
            if (skip >= vector.len) {
                skip -= vector.len;
                continue;
            }
            selected[count] = common.vector(vector.base[skip..vector.len]);
            skip = 0;
            count += 1;
        }
        try backend.sendv(2, 23, peer, selected[0..count]);
        const sent = try fixture.completion(&backend);
        try std.testing.expectEqual(@as(u64, 23), sent.token);
        try std.testing.expect(sent.result > 0 and sent.result <= expected.len - offset);
        offset += @intCast(sent.result);
    }
    try std.testing.expectEqual(expected.len, offset);
    var output: [expected.len]u8 = undefined;
    try fixture.readExact(client, &output);
    try std.testing.expectEqualStrings(expected, &output);
    try backend.recv(0, 24, peer, &input);
    try backend.cancel(4, 25, 0);
    var receive_canceled = false;
    var cancel_seen = false;
    for (0..2) |_| {
        const result = try fixture.completion(&backend);
        switch (result.token) {
            24 => {
                try std.testing.expect(!receive_canceled);
                try std.testing.expectEqual(negative(aborted_error), result.result);
                receive_canceled = true;
            },
            25 => {
                try std.testing.expect(!cancel_seen);
                try std.testing.expectEqual(@as(i32, 0), result.result);
                cancel_seen = true;
            },
            else => return error.UnexpectedToken,
        }
    }
    try std.testing.expect(receive_canceled and cancel_seen);
    try std.testing.expectEqual(@as(i32, 0), win32.shutdown(client, 1));
    try backend.recv(0, 26, peer, &input);
    const eof = try fixture.completion(&backend);
    try std.testing.expectEqual(@as(u64, 26), eof.token);
    try std.testing.expectEqual(@as(i32, 0), eof.result);
}

test "IOCP cancel races retain terminal ownership and reusable cell generations" {
    var backend = try Backend.init(std.testing.allocator, 2, 0, false);
    defer backend.deinit();
    for (1..33) |generation| {
        // Each race uses a fresh stream: an aborted receive does not promise
        // byte rollback or a known unread suffix on the previous stream.
        const client = try fixture.client(backend.port());
        defer closeSocket(client);
        try backend.accept(8, 1);
        const accepted = try fixture.completion(&backend);
        try std.testing.expect(accepted.result >= 0);
        const peer = accepted.result;
        defer backend.close(0, peer);
        var input: [1]u8 = undefined;
        const token = (@as(u64, generation) << 32) | 1;
        try backend.recv(0, token, peer, &input);
        try std.testing.expectEqual(@as(i32, 1), fixture.send(client, "x", 1, 0));
        try backend.cancel(4, token + 1, 0);
        // A queued target or cancellation result still reserves its cell.
        try std.testing.expectError(error.OperationCellBusy, backend.recv(0, token + 2, peer, &input));
        var data_seen = false;
        var cancel_seen = false;
        for (0..2) |_| {
            const result = try fixture.completion(&backend);
            if (result.token == token) {
                try std.testing.expect(!data_seen);
                data_seen = true;
                if (result.result != negative(aborted_error)) {
                    try std.testing.expectEqual(@as(i32, 1), result.result);
                    try std.testing.expectEqual(@as(u8, 'x'), input[0]);
                }
            } else {
                try std.testing.expectEqual(token + 1, result.token);
                try std.testing.expect(!cancel_seen);
                try std.testing.expect(result.result == 0 or result.result == negative(not_found_error));
                cancel_seen = true;
            }
        }
        try std.testing.expect(data_seen and cancel_seen);
        try std.testing.expectEqual(@as(usize, 0), backend.outstanding);
    }
}

test "IOCP startup worker wakes the owner without borrowing a caller token" {
    var backend = try Backend.init(std.testing.allocator, 1, 0, false);
    defer backend.deinit();
    const Worker = struct {
        fn run(target: *Backend) void {
            win32.Sleep(20);
            target.wake();
        }
    };
    const worker = try std.Thread.spawn(.{}, Worker.run, .{&backend});
    defer worker.join();
    var out: [1]Completion = undefined;
    const started = win32.GetTickCount64();
    try std.testing.expectEqual(@as(usize, 0), try backend.poll(&out, 1000));
    try std.testing.expect(win32.GetTickCount64() - started < 900);
}
