const fs = require("fs");
const os = require("os");
const path = require("path");

function nowIso() {
  return new Date().toISOString();
}

const crcTable = new Uint32Array(256);
(function () {
  for (let i = 0; i < 256; i++) {
    let c = i;
    for (let k = 0; k < 8; k++) {
      c = (c & 1) ? (0xEDB88320 ^ (c >>> 1)) : (c >>> 1);
    }
    crcTable[i] = c >>> 0;
  }
})();

function crc32_lookup(buffer) {
  let crc = -1;
  for (let i = 0; i < buffer.length; i++) {
    crc = (crc >>> 8) ^ crcTable[(crc ^ buffer[i]) & 0xFF];
  }
  return (crc ^ -1) >>> 0;
}

function crc32_naive(buffer) {
  let crc = 0xFFFFFFFF;
  for (let i = 0; i < buffer.length; i++) {
    crc ^= buffer[i];
    for (let k = 0; k < 8; k++) {
      const mask = -(crc & 1);
      crc = (crc >>> 1) ^ (0xEDB88320 & mask);
    }
  }
  return (crc ^ 0xFFFFFFFF) >>> 0;
}

function p95(values) {
  if (!values.length) return 0;
  const s = values.slice().sort((a, b) => a - b);
  const idx = Math.max(0, Math.min(s.length - 1, Math.round(0.95 * (s.length - 1))));
  return s[idx];
}

function mean(values) {
  if (!values.length) return 0;
  return values.reduce((a, b) => a + b, 0) / values.length;
}

function median(values) {
  if (!values.length) return 0;
  const s = values.slice().sort((a, b) => a - b);
  const mid = Math.floor(s.length / 2);
  return (s.length % 2) ? s[mid] : (s[mid - 1] + s[mid]) / 2;
}

function bench(fn, buf, iters, warmup) {
  for (let i = 0; i < warmup; i++) fn(buf);
  const samplesUs = [];
  for (let i = 0; i < iters; i++) {
    const t0 = process.hrtime.bigint();
    fn(buf);
    const t1 = process.hrtime.bigint();
    samplesUs.push(Number(t1 - t0) / 1000.0);
  }
  return {
    mean_us_op: mean(samplesUs),
    median_us_op: median(samplesUs),
    p95_us_op: p95(samplesUs),
  };
}

function throughputMBps(bytes, meanUsOp) {
  if (!meanUsOp) return 0;
  const seconds = (meanUsOp / 1e6);
  return (bytes / (1024 * 1024)) / seconds;
}

function main() {
  const repoRoot = path.resolve(__dirname, "..", "..");
  const outDir = path.join(repoRoot, "Exports", "diagrams", "data");
  fs.mkdirSync(outDir, { recursive: true });

  const sizes = [1024, 4096, 16384];
  const results = [];

  for (const size of sizes) {
    const buf = Buffer.allocUnsafe(size);
    for (let i = 0; i < size; i++) buf[i] = (i * 131 + 7) & 0xFF;

    const heapBefore = process.memoryUsage().heapUsed;
    const rLookup = bench(crc32_lookup, buf, 30000, 2000);
    const heapAfterLookup = process.memoryUsage().heapUsed;

    const rNaive = bench(crc32_naive, buf, 5000, 500);
    const heapAfterNaive = process.memoryUsage().heapUsed;

    results.push({
      payload_bytes: size,
      baseline_naive: {
        ...rNaive,
        throughput_MBps: throughputMBps(size, rNaive.mean_us_op),
        heapUsed_bytes: heapAfterNaive,
      },
      current_lookup_table: {
        ...rLookup,
        throughput_MBps: throughputMBps(size, rLookup.mean_us_op),
        heapUsed_bytes: heapAfterLookup,
      },
      heapUsed_bytes_before: heapBefore,
    });
  }

  const data = {
    meta: {
      generated_at: nowIso(),
      node: process.version,
      platform: `${os.platform()} ${os.release()}`,
      cpu: os.cpus()?.[0]?.model ?? "unknown",
    },
    crc32: results,
  };

  const outJson = path.join(outDir, "perf_crc32.json");
  fs.writeFileSync(outJson, JSON.stringify(data, null, 2), "utf-8");

  const outCsv = path.join(outDir, "perf_crc32.csv");
  const rows = [];
  rows.push(["payload_bytes", "variant", "mean_us_op", "median_us_op", "p95_us_op", "throughput_MBps", "heapUsed_bytes"]);
  for (const r of results) {
    rows.push([r.payload_bytes, "baseline_naive", r.baseline_naive.mean_us_op, r.baseline_naive.median_us_op, r.baseline_naive.p95_us_op, r.baseline_naive.throughput_MBps, r.baseline_naive.heapUsed_bytes]);
    rows.push([r.payload_bytes, "current_lookup_table", r.current_lookup_table.mean_us_op, r.current_lookup_table.median_us_op, r.current_lookup_table.p95_us_op, r.current_lookup_table.throughput_MBps, r.current_lookup_table.heapUsed_bytes]);
  }
  fs.writeFileSync(outCsv, rows.map(r => r.join(",")).join("\n"), "utf-8");

  console.log(outJson);
  console.log(outCsv);
}

main();

