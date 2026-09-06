#!/usr/bin/env python3
"""Render qualified HTTP figures from hashed raw receipts and RESULT records.

Use Python 3.12 with matplotlib==3.9.4 for reproducible SVG output.
Install plotting dependencies in an isolated environment, not the HTTP runtime.
"""

import argparse
import hashlib
import io
import json
from pathlib import Path
import statistics
import tarfile
import xml.etree.ElementTree as ET

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patheffects as effects

ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / "reports/2026-09-05-arena-adoption/packet.json"
PALETTE = {"zig-http": "#d94b2b", "libreactor": "#172f40"}
BACKGROUND = "#fffef9"
GRID = "#d2d7d0"
SVG = "http://www.w3.org/2000/svg"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def measured_rows():
    packet = json.loads(PACKET.read_text())
    archive = PACKET.with_name("evidence.tar.gz")
    require(hashlib.sha256(archive.read_bytes()).hexdigest() ==
            packet["artifact_sha256"][archive.name], "evidence archive hash mismatch")
    rows = []
    with tarfile.open(archive) as evidence:
        def member(name):
            content = evidence.extractfile(name).read()
            require(hashlib.sha256(content).hexdigest() == packet["archive_member_sha256"][name],
                    "evidence member hash mismatch: " + name)
            return content

        for cpus in (1, 3):
            prefix = "linux/qualified/{}cpu/".format(cpus)
            receipt = json.loads(member(prefix + "results.json"))
            require(receipt["ok"] and len(receipt["trials"]) == 18, "incomplete qualified receipt")
            require(receipt["configuration"]["implementation_commit"] == packet["implementation_commit"],
                    "qualified source identity mismatch")
            rates = {(server, depth): [] for server in PALETTE for depth in (1, 16, 128)}
            for trial in receipt["trials"]:
                name = "{index:03d}-{server}-c{connections}-p{pipeline}-wrk.log".format(**trial)
                records = [json.loads(line[7:]) for line in member(prefix + name).decode().splitlines()
                           if line.startswith("RESULT ")]
                require(len(records) == 1, "missing or duplicate raw RESULT")
                raw = records[0]
                require(all(trial["result"][key] == value for key, value in raw.items()),
                        "raw RESULT disagrees with receipt")
                rate = raw["requests"] * 1e6 / raw["duration_us"]
                rates[trial["server"], trial["pipeline"]].append(rate)
            for depth in (1, 16, 128):
                published = next(row for row in packet["summary"]["rows"]
                                 if len(row["server_cpus"]) == cpus and row["pipeline"] == depth)
                row = dict(cpus=cpus, depth=depth, servers={})
                for server in PALETTE:
                    samples = rates[server, depth]
                    require(len(samples) == 3, "wrong sample count")
                    values = dict(n=3, min=min(samples), median=statistics.median(samples), max=max(samples))
                    require(values == published["servers"][server]["responses_per_second"],
                            "derived distribution disagrees with packet")
                    row["servers"][server] = values
                rows.append(row)
    return rows


def render(rows, cpus, preview_dir):
    matplotlib.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 11, "svg.fonttype": "none",
        "svg.hashsalt": "zig-http-qualified-arena-2026-09-05-{}cpu".format(cpus), "text.color": PALETTE["libreactor"],
        "axes.labelcolor": PALETTE["libreactor"], "xtick.color": PALETTE["libreactor"],
        "ytick.color": PALETTE["libreactor"],
    })
    fig, axis = plt.subplots(figsize=(10, 4.8), facecolor=BACKGROUND)
    fig.subplots_adjust(left=0.13, right=0.97, bottom=0.19, top=0.76)
    axis.set_facecolor(BACKGROUND)
    selected = [row for row in rows if row["cpus"] == cpus]
    description = []
    for server_index, (server, color) in enumerate(PALETTE.items()):
        for index, row in enumerate(selected):
            value = row["servers"][server]
            median = value["median"] / 1e6
            low, high = value["min"] / 1e6, value["max"] / 1e6
            y = index + (-0.18 if server_index == 0 else 0.18)
            axis.barh(y, median, height=0.29, color=color, zorder=3,
                      label=("bounded/http" if server == "zig-http" else "libreactor") if index == 0 else None)
            whisker = axis.errorbar(median, y, xerr=[[median - low], [high - median]], fmt="none",
                                    ecolor=PALETTE["libreactor"], capsize=4, elinewidth=1.2, zorder=4)
            for artist in (*whisker[1], *whisker[2]):
                artist.set_path_effects([effects.Stroke(linewidth=3.5, foreground=BACKGROUND), effects.Normal()])
            axis.text(high + 0.16, y, "{:.3f} M/s".format(median), va="center", fontsize=10)
            description.append("Depth {}: {} median {:.6f} million responses/s; range {:.6f} to {:.6f}.".format(
                row["depth"], "bounded/http (recorded as zig-http)" if server == "zig-http" else server, median, low, high))
    axis.set_xlim(0, 16)
    axis.set_xticks(range(0, 17, 2))
    axis.set_yticks(range(3), ["Depth {}".format(row["depth"]) for row in selected])
    axis.set_ylim(2.55, -0.55)
    axis.set_xlabel("Completed responses per second (millions)", labelpad=10)
    axis.tick_params(axis="both", length=0, pad=8)
    axis.grid(axis="x", color=GRID, linewidth=0.8, zorder=0)
    for spine in axis.spines.values():
        spine.set_visible(False)
    axis.legend(loc="lower right", bbox_to_anchor=(1, 1.01), frameon=False, ncol=2)
    title = "One allowed server CPU" if cpus == 1 else "Three allowed server CPUs"
    fig.text(0.13, 0.935, title, fontsize=19, weight="bold")
    fig.text(0.13, 0.87, "128 connections · 3 trials · 5 seconds each", fontsize=11)
    fig.text(0.13, 0.045, "Bars: medians · Whiskers: observed min–max · Closed-loop HTTP/1.1", fontsize=9)
    output = io.BytesIO()
    fig.savefig(output, format="svg", metadata={"Date": None, "Creator": "tools/render_performance_figures.py"})
    if preview_dir:
        preview_dir.mkdir(parents=True, exist_ok=True)
        fig.savefig(preview_dir / "performance-{}cpu.png".format(cpus), dpi=120)
    plt.close(fig)
    ET.register_namespace("", SVG)
    ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")
    root = ET.fromstring(output.getvalue())
    identity = "performance-{}cpu".format(cpus)
    ids = {element.get("id"): identity + "-" + element.get("id")
           for element in root.iter() if element.get("id")}
    for element in root.iter():
        for attribute, value in list(element.attrib.items()):
            if attribute == "id":
                element.set(attribute, ids[value])
            else:
                if attribute == "style":
                    value = value.replace("'DejaVu Sans'", "'DejaVu Sans', system-ui, -apple-system, 'Segoe UI', sans-serif")
                for previous, current in ids.items():
                    value = value.replace("url(#" + previous + ")", "url(#" + current + ")")
                    if value == "#" + previous:
                        value = "#" + current
                element.set(attribute, value)
    root.attrib.pop("width", None)
    root.attrib.pop("height", None)
    root.set("class", "chart-svg")
    root.set("role", "img")
    root.set("aria-labelledby", identity + "-title " + identity + "-desc")
    ET.SubElement(root, "{" + SVG + "}title", id=identity + "-title").text = title
    ET.SubElement(root, "{" + SVG + "}desc", id=identity + "-desc").text = " ".join(description)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True) + b"\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="compare without changing SVG files")
    parser.add_argument("--preview-dir", type=Path)
    args = parser.parse_args()
    rows = measured_rows()
    for cpus in (1, 3):
        path = ROOT / "docs/diagrams/performance-{}cpu.svg".format(cpus)
        content = render(rows, cpus, args.preview_dir)
        if args.check:
            require(path.read_bytes() == content, "stale figure: " + str(path))
        else:
            path.write_bytes(content)
        print("{} {}".format(hashlib.sha256(content).hexdigest(), path.relative_to(ROOT)))


if __name__ == "__main__":
    main()
