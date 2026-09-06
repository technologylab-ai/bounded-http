const std = @import("std");

pub fn build(b: *std.Build) void {
    const target = b.standardTargetOptions(.{});
    const optimize = b.standardOptimizeOption(.{});
    const dependency = b.dependency("bounded_http", .{ .target = target, .optimize = optimize });
    const module = b.createModule(.{
        .root_source_file = b.path("src/main.zig"),
        .target = target,
        .optimize = optimize,
        .link_libc = true,
        .imports = &.{.{ .name = "bounded_http", .module = dependency.module("bounded_http") }},
    });
    const executable = b.addExecutable(.{
        // Linux Debug needs LLVM/LLD for the installed GCC CRT relocations.
        .use_llvm = if (target.result.os.tag == .linux and optimize == .Debug) true else null,
        .use_lld = if (target.result.os.tag == .linux and optimize == .Debug) true else null,
        .name = "embedded-http",
        .root_module = module,
    });
    b.installArtifact(executable);
    const run = b.addRunArtifact(executable);
    if (b.args) |args| run.addArgs(args);
    b.step("run", "Run the bounded embedding example").dependOn(&run.step);
}
