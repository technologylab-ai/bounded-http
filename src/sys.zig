//! The POSIX calls bounded/http makes outside the Windows transport, with
//! libc's signatures and return conventions (-1 and `errno`).
//!
//! When libc is linked, and on every system other than Linux, these are the
//! `std.c` functions. On Linux without libc they are direct system calls via
//! `std.os.linux`, so an application can link no libc at all (for example
//! `-Dtarget=x86_64-linux-musl` with a static binary, or `x86_64-linux-none`).
//! `errno` reads the calling thread's last failure in both cases.
const std = @import("std");
const builtin = @import("builtin");
const c = std.c;
const linux = std.os.linux;

/// True when calls go straight to the kernel instead of through libc.
pub const direct = builtin.os.tag == .linux and !builtin.link_libc;

pub const E = c.E;

/// The last failure of a direct call on this thread (libc keeps its own).
threadlocal var last_errno: linux.E = .SUCCESS;

fn int(rc: usize) c_int {
    const err = linux.errno(rc);
    if (err != .SUCCESS) {
        last_errno = err;
        return -1;
    }
    return @intCast(rc);
}

fn size(rc: usize) isize {
    const err = linux.errno(rc);
    if (err != .SUCCESS) {
        last_errno = err;
        return -1;
    }
    return @intCast(rc);
}

/// The error of a failed call (`rc == -1`), else `.SUCCESS`.
pub fn errno(rc: anytype) E {
    if (!direct) return c.errno(rc);
    return if (rc == -1) @enumFromInt(@intFromEnum(last_errno)) else .SUCCESS;
}

pub fn socket(domain: c_uint, socket_type: c_uint, protocol: c_uint) c_int {
    if (!direct) return c.socket(domain, socket_type, protocol);
    return int(linux.socket(domain, socket_type, protocol));
}

pub fn setsockopt(fd: c.fd_t, level: i32, name: u32, value: *const anyopaque, len: c.socklen_t) c_int {
    if (!direct) return c.setsockopt(fd, level, name, value, len);
    return int(linux.setsockopt(fd, level, name, @ptrCast(value), len));
}

pub fn bind(fd: c.fd_t, address: *const c.sockaddr, len: c.socklen_t) c_int {
    if (!direct) return c.bind(fd, address, len);
    return int(linux.bind(fd, address, len));
}

pub fn listen(fd: c.fd_t, backlog: c_uint) c_int {
    if (!direct) return c.listen(fd, backlog);
    return int(linux.listen(fd, backlog));
}

pub fn getsockname(fd: c.fd_t, noalias address: *c.sockaddr, noalias len: *c.socklen_t) c_int {
    if (!direct) return c.getsockname(fd, address, len);
    return int(linux.getsockname(fd, address, len));
}

/// `fcntl` with one explicit argument (0 when the command takes none).
pub fn fcntl(fd: c.fd_t, cmd: c_int, arg: usize) c_int {
    if (!direct) return c.fcntl(fd, cmd, arg);
    return int(linux.fcntl(fd, cmd, arg));
}

pub fn close(fd: c.fd_t) c_int {
    if (!direct) return c.close(fd);
    return int(linux.close(fd));
}

pub fn connect(fd: c.fd_t, address: *const c.sockaddr, len: c.socklen_t) c_int {
    if (!direct) return c.connect(fd, address, len);
    return int(linux.connect(fd, address, len));
}

pub fn send(fd: c.fd_t, bytes: *const anyopaque, len: usize, flags: u32) isize {
    if (!direct) return c.send(fd, bytes, len, flags);
    return size(linux.sendto(fd, @ptrCast(bytes), len, flags, null, 0));
}

pub fn recv(fd: c.fd_t, bytes: *anyopaque, len: usize, flags: u32) isize {
    if (!direct) return c.recv(fd, bytes, len, @intCast(flags));
    return size(linux.recvfrom(fd, @ptrCast(bytes), len, flags, null, null));
}

pub fn poll(fds: [*]c.pollfd, count: c.nfds_t, timeout_ms: c_int) c_int {
    if (!direct) return c.poll(fds, count, timeout_ms);
    return int(linux.poll(fds, count, timeout_ms));
}

pub fn shutdown(fd: c.fd_t, how: c_int) c_int {
    if (!direct) return c.shutdown(fd, how);
    return int(linux.shutdown(fd, how));
}

pub fn pipe(fds: *[2]c.fd_t) c_int {
    if (!direct) return c.pipe(fds);
    return int(linux.pipe(fds));
}

pub fn read(fd: c.fd_t, bytes: [*]u8, len: usize) isize {
    if (!direct) return c.read(fd, bytes, len);
    return size(linux.read(fd, bytes, len));
}

pub fn write(fd: c.fd_t, bytes: [*]const u8, len: usize) isize {
    if (!direct) return c.write(fd, bytes, len);
    return size(linux.write(fd, bytes, len));
}

pub fn clock_gettime(clock: c.clockid_t, time: *c.timespec) c_int {
    if (!direct) return c.clock_gettime(clock, time);
    return int(linux.clock_gettime(clock, time));
}

pub fn nanosleep(request: *const c.timespec, remaining: ?*c.timespec) c_int {
    if (!direct) return c.nanosleep(request, remaining);
    return int(linux.nanosleep(request, remaining));
}

/// Exit at once: no atexit handlers, no unwinding (see server.failFast).
pub fn exitNow(code: u8) noreturn {
    // std.process.exit without libc is already _exit: exit_group on Linux.
    // With libc it would call exit(3) and run atexit handlers, so use _exit.
    if (builtin.link_libc) c._exit(code);
    std.process.exit(code);
}

test "direct calls report failures through errno like libc" {
    if (comptime builtin.os.tag == .windows) return error.SkipZigTest;
    const bad: c.fd_t = -1;
    const result = close(bad);
    try std.testing.expectEqual(@as(c_int, -1), result);
    try std.testing.expectEqual(E.BADF, errno(result));
    var fds: [2]c.fd_t = undefined;
    try std.testing.expectEqual(@as(c_int, 0), pipe(&fds));
    defer _ = close(fds[0]);
    defer _ = close(fds[1]);
    try std.testing.expectEqual(@as(isize, 1), write(fds[1], "x", 1));
    var byte: [1]u8 = undefined;
    try std.testing.expectEqual(@as(isize, 1), read(fds[0], &byte, 1));
    try std.testing.expectEqual(@as(u8, 'x'), byte[0]);
    var now: c.timespec = undefined;
    try std.testing.expectEqual(@as(c_int, 0), clock_gettime(.MONOTONIC, &now));
}
