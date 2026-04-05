import csv
import json
import math
import os
from datetime import datetime, timezone


def _read_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _pick_crc32_row(crc32_json: dict, payload_bytes: int) -> dict:
    for row in crc32_json.get("crc32", []):
        if int(row.get("payload_bytes", -1)) == int(payload_bytes):
            return row
    raise RuntimeError(f"perf_crc32.json does not contain payload_bytes={payload_bytes}")


def _scale(values: list[float], min_px: float, max_px: float) -> list[float]:
    if not values:
        return []
    lo = min(values)
    hi = max(values)
    if hi <= lo:
        return [0.5 * (min_px + max_px) for _ in values]
    out = []
    for v in values:
        t = (v - lo) / (hi - lo)
        out.append(min_px + t * (max_px - min_px))
    return out


def _drawio_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def _make_drawio_bar_pair(x: float, base_y: float, w: float, h: float, color: str, label: str, cell_id: str):
    style = f"rounded=0;whiteSpace=wrap;html=1;fillColor={color};strokeColor=#E6F0FF;"
    txt_style = "text;html=1;strokeColor=none;fillColor=none;align=center;verticalAlign=top;whiteSpace=wrap;"
    bar = f'<mxCell id="{cell_id}" value="" style="{style}" vertex="1" parent="1"><mxGeometry x="{x:.1f}" y="{base_y - h:.1f}" width="{w:.1f}" height="{h:.1f}" as="geometry"/></mxCell>'
    txt = f'<mxCell id="{cell_id}_t" value="{_drawio_escape(label)}" style="{txt_style}" vertex="1" parent="1"><mxGeometry x="{x-10:.1f}" y="{base_y + 6:.1f}" width="{w+20:.1f}" height="30" as="geometry"/></mxCell>'
    return bar + txt


def main():
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    data_dir = os.path.join(repo_root, "Exports", "diagrams", "data")
    os.makedirs(data_dir, exist_ok=True)

    crc32 = _read_json(os.path.join(data_dir, "perf_crc32.json"))
    video = _read_json(os.path.join(data_dir, "perf_video_pipeline.json"))

    crc_row = _pick_crc32_row(crc32, payload_bytes=4096)
    crc_baseline = crc_row["baseline_naive"]
    crc_current = crc_row["current_lookup_table"]

    resize_base = video["resize"]["baseline_direct_resize"]
    resize_curr = video["resize"]["current_letterbox_resize"]

    jpeg_curr = video["jpeg"]["current_quality_70"]
    jpeg_base = video["jpeg"]["comparison_quality_90"]

    summary = {
        "meta": {
            "generated_at": _now_iso(),
            "sources": ["perf_crc32.json", "perf_video_pipeline.json"],
            "notes": [
                "baseline 字段为对照实现或对照参数组合（不改变当前产品实现）；current 字段为当前实现。",
                "CRC32 的 current 对应 host-app/main.js 的查表法实现；baseline 为按位计算的对照实现。",
                "视频链路的 resize current 对应 slave-sim/simulator.py 的 letterbox；baseline 为直接缩放至 320x240 的对照实现。",
                "JPEG quality=70 为当前实现（slave-sim/simulator.py）；quality=90 为对照参数。",
            ],
        },
        "metrics": [
            {
                "group": "crc32",
                "metric": "latency_mean",
                "baseline": crc_baseline["mean_us_op"],
                "current": crc_current["mean_us_op"],
                "unit": "us/op",
                "scope": "payload=4096B",
            },
            {
                "group": "crc32",
                "metric": "throughput_mean",
                "baseline": crc_baseline["throughput_MBps"],
                "current": crc_current["throughput_MBps"],
                "unit": "MB/s",
                "scope": "payload=4096B",
            },
            {
                "group": "resize",
                "metric": "latency_mean",
                "baseline": resize_base["time_ms_op"]["mean"],
                "current": resize_curr["time_ms_op"]["mean"],
                "unit": "ms/op",
                "scope": "640x480 -> 320x240",
            },
            {
                "group": "jpeg",
                "metric": "latency_mean",
                "baseline": jpeg_base["time_ms_op"]["mean"],
                "current": jpeg_curr["time_ms_op"]["mean"],
                "unit": "ms/op",
                "scope": "encode 320x240, q90 vs q70",
            },
            {
                "group": "jpeg",
                "metric": "size_mean",
                "baseline": jpeg_base["size_kb_frame"]["mean"],
                "current": jpeg_curr["size_kb_frame"]["mean"],
                "unit": "KB/frame",
                "scope": "encode 320x240, q90 vs q70",
            },
        ],
    }

    out_json = os.path.join(data_dir, "perf_summary.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    out_csv = os.path.join(data_dir, "perf_summary.csv")
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["group", "metric", "baseline", "current", "unit", "scope"])
        for m in summary["metrics"]:
            w.writerow([m["group"], m["metric"], m["baseline"], m["current"], m["unit"], m["scope"]])

    diagram_dir = os.path.join(repo_root, "Exports", "diagrams", "drawio")
    os.makedirs(diagram_dir, exist_ok=True)
    out_drawio = os.path.join(diagram_dir, "性能对比柱状图.drawio")

    baseline_color = "#FF6600"
    current_color = "#00E5FF"
    bg = "#121212"
    fg = "#E6F0FF"

    latency_ms = [
        float(crc_baseline["mean_us_op"]) / 1000.0,
        float(crc_current["mean_us_op"]) / 1000.0,
        float(resize_base["time_ms_op"]["mean"]),
        float(resize_curr["time_ms_op"]["mean"]),
        float(jpeg_base["time_ms_op"]["mean"]),
        float(jpeg_curr["time_ms_op"]["mean"]),
    ]
    latency_h = _scale(latency_ms, min_px=40, max_px=220)

    base_y = 520.0
    x0 = 80.0
    bw = 30.0
    gap = 26.0

    bars = []
    labels = [
        "CRC32(4096B)\\n对照",
        "CRC32(4096B)\\n当前",
        "Resize\\n对照",
        "Resize\\n当前",
        "JPEG(q90)\\n对照",
        "JPEG(q70)\\n当前",
    ]
    colors = [baseline_color, current_color, baseline_color, current_color, baseline_color, current_color]
    for i, (h, c, lab) in enumerate(zip(latency_h, colors, labels)):
        x = x0 + i * (bw + gap)
        bars.append(_make_drawio_bar_pair(x, base_y, bw, h, c, lab, f"bar{i+1}"))

    legend = (
        f'<mxCell id="legend_title" value="图例" style="text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=top;fontColor={fg};" vertex="1" parent="1">'
        f'<mxGeometry x="520" y="80" width="200" height="30" as="geometry"/></mxCell>'
        f'<mxCell id="legend_b" value="对照(优化前)" style="rounded=0;whiteSpace=wrap;html=1;fillColor={baseline_color};strokeColor={fg};fontColor={fg};" vertex="1" parent="1">'
        f'<mxGeometry x="520" y="120" width="140" height="26" as="geometry"/></mxCell>'
        f'<mxCell id="legend_c" value="当前(优化后)" style="rounded=0;whiteSpace=wrap;html=1;fillColor={current_color};strokeColor={fg};fontColor={bg};" vertex="1" parent="1">'
        f'<mxGeometry x="520" y="154" width="140" height="26" as="geometry"/></mxCell>'
    )

    title = (
        f'<mxCell id="title" value="性能对比柱状图（实测数据：CRC32/Resize/JPEG）" style="text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=top;fontSize=16;fontColor={fg};" vertex="1" parent="1">'
        f'<mxGeometry x="60" y="30" width="720" height="30" as="geometry"/></mxCell>'
    )

    subtitle = (
        f'<mxCell id="subtitle" value="指标：均值延迟（毫秒，越低越好）。数据源：Exports/diagrams/data/perf_summary.*" style="text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=top;fontColor={fg};" vertex="1" parent="1">'
        f'<mxGeometry x="60" y="58" width="720" height="30" as="geometry"/></mxCell>'
    )

    axis = (
        f'<mxCell id="axis_x" value="" style="endArrow=none;strokeColor={fg};" edge="1" parent="1"><mxGeometry relative="1" as="geometry"><mxPoint x="60" y="{base_y:.1f}" as="sourcePoint"/><mxPoint x="470" y="{base_y:.1f}" as="targetPoint"/></mxGeometry></mxCell>'
        f'<mxCell id="axis_y" value="" style="endArrow=none;strokeColor={fg};" edge="1" parent="1"><mxGeometry relative="1" as="geometry"><mxPoint x="60" y="280" as="sourcePoint"/><mxPoint x="60" y="{base_y:.1f}" as="targetPoint"/></mxGeometry></mxCell>'
    )

    bg_cell = (
        f'<mxCell id="bg" value="" style="rounded=0;whiteSpace=wrap;html=1;fillColor={bg};strokeColor={bg};" vertex="1" parent="1">'
        f'<mxGeometry x="0" y="0" width="780" height="580" as="geometry"/></mxCell>'
    )

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<mxfile host="app.diagrams.net" modified="' + _drawio_escape(_now_iso()) + '" agent="Trae" version="24.7.8">'
        '<diagram id="perf" name="性能对比柱状图"><mxGraphModel dx="1200" dy="800" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="827" pageHeight="1169" math="0" shadow="0">'
        '<root><mxCell id="0"/><mxCell id="1" parent="0"/>'
        + bg_cell
        + title
        + subtitle
        + legend
        + axis
        + "".join(bars)
        + "</root></mxGraphModel></diagram></mxfile>"
    )

    with open(out_drawio, "w", encoding="utf-8") as f:
        f.write(xml)

    print(out_json)
    print(out_csv)
    print(out_drawio)


if __name__ == "__main__":
    main()

