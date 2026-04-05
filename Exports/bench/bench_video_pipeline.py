import csv
import json
import os
import platform
import statistics
import time
import tracemalloc
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

import cv2
import numpy as np


@dataclass
class BenchResult:
    name: str
    unit: str
    samples: list[float]

    @property
    def mean(self) -> float:
        return float(statistics.mean(self.samples)) if self.samples else 0.0

    @property
    def median(self) -> float:
        return float(statistics.median(self.samples)) if self.samples else 0.0

    @property
    def p95(self) -> float:
        if not self.samples:
            return 0.0
        s = sorted(self.samples)
        idx = max(0, min(len(s) - 1, int(round(0.95 * (len(s) - 1)))))
        return float(s[idx])


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _load_source_image(repo_root: str) -> np.ndarray:
    img_path = os.path.join(repo_root, "slave-sim", "assets", "real_sewer.jpg")
    img = cv2.imread(img_path, cv2.IMREAD_COLOR)
    if img is None:
        raise RuntimeError(f"Cannot read image: {img_path}")
    return img


def _baseline_direct_resize(img_bgr: np.ndarray, target_w: int, target_h: int) -> np.ndarray:
    return cv2.resize(img_bgr, (target_w, target_h), interpolation=cv2.INTER_AREA)


def _current_letterbox_resize(img_bgr: np.ndarray, target_w: int, target_h: int) -> np.ndarray:
    h, w = img_bgr.shape[:2]
    scale = min(target_w / w, target_h / h)
    new_w, new_h = int(w * scale), int(h * scale)
    resized = cv2.resize(img_bgr, (new_w, new_h), interpolation=cv2.INTER_AREA)
    canvas = np.zeros((target_h, target_w, 3), dtype=np.uint8)
    x_offset = (target_w - new_w) // 2
    y_offset = (target_h - new_h) // 2
    canvas[y_offset : y_offset + new_h, x_offset : x_offset + new_w] = resized
    return canvas


def _bench(fn, iters: int, warmup: int) -> BenchResult:
    samples_ms: list[float] = []
    for _ in range(warmup):
        fn()
    for _ in range(iters):
        t0 = time.perf_counter()
        fn()
        t1 = time.perf_counter()
        samples_ms.append((t1 - t0) * 1000.0)
    return BenchResult(name=fn.__name__, unit="ms/op", samples=samples_ms)


def _bench_jpeg_encode(img_bgr: np.ndarray, quality: int, iters: int, warmup: int) -> tuple[BenchResult, BenchResult]:
    times_ms: list[float] = []
    sizes_kb: list[float] = []
    params = [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)]
    for _ in range(warmup):
        ok, data = cv2.imencode(".jpg", img_bgr, params)
        if not ok:
            raise RuntimeError("cv2.imencode failed in warmup")
        _ = data.tobytes()
    for _ in range(iters):
        t0 = time.perf_counter()
        ok, data = cv2.imencode(".jpg", img_bgr, params)
        if not ok:
            raise RuntimeError("cv2.imencode failed")
        raw = data.tobytes()
        t1 = time.perf_counter()
        times_ms.append((t1 - t0) * 1000.0)
        sizes_kb.append(len(raw) / 1024.0)
    return (
        BenchResult(name=f"jpeg_encode_q{quality}", unit="ms/op", samples=times_ms),
        BenchResult(name=f"jpeg_size_q{quality}", unit="KB/frame", samples=sizes_kb),
    )


def _memory_profile(fn, runs: int) -> dict:
    tracemalloc.start()
    for _ in range(runs):
        fn()
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {"current_bytes": int(current), "peak_bytes": int(peak)}


def main():
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    out_dir = os.path.join(repo_root, "Exports", "diagrams", "data")
    os.makedirs(out_dir, exist_ok=True)

    img = _load_source_image(repo_root)
    target_w, target_h = 320, 240

    src_w, src_h = 640, 480
    src_frame = cv2.resize(img, (src_w, src_h), interpolation=cv2.INTER_AREA)

    direct = lambda: _baseline_direct_resize(src_frame, target_w, target_h)
    letterbox = lambda: _current_letterbox_resize(src_frame, target_w, target_h)

    resize_direct = _bench(direct, iters=300, warmup=30)
    resize_letterbox = _bench(letterbox, iters=300, warmup=30)

    mem_direct = _memory_profile(direct, runs=100)
    mem_letterbox = _memory_profile(letterbox, runs=100)

    out_direct = direct()
    out_letterbox = letterbox()
    enc_q70_t, enc_q70_s = _bench_jpeg_encode(out_letterbox, quality=70, iters=300, warmup=30)
    enc_q90_t, enc_q90_s = _bench_jpeg_encode(out_letterbox, quality=90, iters=300, warmup=30)

    meta = {
        "generated_at": _now_iso(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "opencv_version": getattr(cv2, "__version__", "unknown"),
        "source_image": {"path": "slave-sim/assets/real_sewer.jpg", "shape_hwc": list(img.shape)},
        "source_frame": {"shape_hwc": list(src_frame.shape), "note": "用于模拟 render_engine.render() 输出的 640x480 BGR 帧"},
        "target_frame": {"width": target_w, "height": target_h},
    }

    data = {
        "meta": meta,
        "resize": {
            "baseline_direct_resize": {
                "time_ms_op": {"mean": resize_direct.mean, "median": resize_direct.median, "p95": resize_direct.p95},
                "memory_bytes": mem_direct,
            },
            "current_letterbox_resize": {
                "time_ms_op": {"mean": resize_letterbox.mean, "median": resize_letterbox.median, "p95": resize_letterbox.p95},
                "memory_bytes": mem_letterbox,
            },
        },
        "jpeg": {
            "current_quality_70": {
                "time_ms_op": {"mean": enc_q70_t.mean, "median": enc_q70_t.median, "p95": enc_q70_t.p95},
                "size_kb_frame": {"mean": enc_q70_s.mean, "median": enc_q70_s.median, "p95": enc_q70_s.p95},
            },
            "comparison_quality_90": {
                "time_ms_op": {"mean": enc_q90_t.mean, "median": enc_q90_t.median, "p95": enc_q90_t.p95},
                "size_kb_frame": {"mean": enc_q90_s.mean, "median": enc_q90_s.median, "p95": enc_q90_s.p95},
            },
        },
    }

    out_json = os.path.join(out_dir, "perf_video_pipeline.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    out_csv = os.path.join(out_dir, "perf_video_pipeline.csv")
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["group", "variant", "metric", "mean", "median", "p95", "unit"])
        w.writerow(["resize", "baseline", "time", resize_direct.mean, resize_direct.median, resize_direct.p95, "ms/op"])
        w.writerow(["resize", "current", "time", resize_letterbox.mean, resize_letterbox.median, resize_letterbox.p95, "ms/op"])
        w.writerow(["jpeg", "q70", "encode_time", enc_q70_t.mean, enc_q70_t.median, enc_q70_t.p95, "ms/op"])
        w.writerow(["jpeg", "q90", "encode_time", enc_q90_t.mean, enc_q90_t.median, enc_q90_t.p95, "ms/op"])
        w.writerow(["jpeg", "q70", "size", enc_q70_s.mean, enc_q70_s.median, enc_q70_s.p95, "KB/frame"])
        w.writerow(["jpeg", "q90", "size", enc_q90_s.mean, enc_q90_s.median, enc_q90_s.p95, "KB/frame"])

    print(out_json)
    print(out_csv)


if __name__ == "__main__":
    main()
