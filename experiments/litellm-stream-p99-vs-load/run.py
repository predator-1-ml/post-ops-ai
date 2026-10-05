#!/usr/bin/env python3
"""Does LiteLLM's streaming p99 depend on load shape?

Question from a LinkedIn comment: "litellm p99, streaming, /chat/completions was 300 ms" in a
closed-loop benchmark against a zero-latency mock. We run the same kind of load (closed loop,
streaming chat completions, same gateway config) against the LiteLLM Python proxy and vary
(a) concurrency and (b) whether the upstream has model-like latency. Each condition also runs
direct to the mock, so the gateway's added latency is the difference.

Windows host, no Docker, LiteLLM runs without uvloop: absolute numbers are NOT comparable to
Linux/Docker runs. The shape (how p99 moves with load) is what this measures.

    python run.py --trials 3 --duration 20
"""
from __future__ import annotations

import argparse
import ctypes
import datetime
import json
import os
import platform
import random
import statistics
import subprocess
import sys
import time
import urllib.request
from ctypes import wintypes
from pathlib import Path

HERE = Path(__file__).resolve().parent
LITELLM = HERE / ".venv" / "Scripts" / "litellm.exe"
RESULTS = HERE / "results"
MOCK_PORT, GW_PORT = 9999, 4000
DIRECT = f"http://127.0.0.1:{MOCK_PORT}/v1/chat/completions"
VIA_GW = f"http://127.0.0.1:{GW_PORT}/v1/chat/completions"

# (name, mock first-token ms, mock token gap ms, concurrencies)
SCENARIOS = [
    ("zero-latency upstream", 0, 0, [1, 2, 4, 10]),
    ("model-like upstream (~300 ms first token, 16 ms/token)", 300, 16, [10, 50, 100]),
]


# ---- process helpers -------------------------------------------------------------------------
def kill_tree(proc: subprocess.Popen | None) -> None:
    if proc and proc.poll() is None:
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True)


def descendants(root: int) -> list[int]:
    out = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId | ConvertTo-Json -Compress"],
        capture_output=True, text=True, check=True).stdout
    rows = json.loads(out)
    kids: dict[int, list[int]] = {}
    for r in rows:
        kids.setdefault(r["ParentProcessId"], []).append(r["ProcessId"])
    found, stack = [root], [root]
    while stack:
        for k in kids.get(stack.pop(), []):
            found.append(k)
            stack.append(k)
    return found


_k32 = ctypes.WinDLL("kernel32", use_last_error=True)
_k32.OpenProcess.restype = wintypes.HANDLE


def cpu_seconds(pids: list[int]) -> float:
    total = 0.0
    for pid in pids:
        h = _k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            continue
        ft = [wintypes.FILETIME() for _ in range(4)]
        if _k32.GetProcessTimes(h, *[ctypes.byref(f) for f in ft]):
            to_s = lambda f: ((f.dwHighDateTime << 32) | f.dwLowDateTime) / 1e7
            total += to_s(ft[2]) + to_s(ft[3])  # kernel + user
        _k32.CloseHandle(h)
    return total


def wait_for(url: str, timeout: float, proc: subprocess.Popen | None = None) -> None:
    body = json.dumps({"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "ping"}]}).encode()
    end = time.time() + timeout
    while time.time() < end:
        if proc and proc.poll() is not None:
            raise RuntimeError(f"process exited early with code {proc.returncode}")
        try:
            req = urllib.request.Request(url, body, {"Content-Type": "application/json", "Authorization": "Bearer sk-bench-test-key"})
            if urllib.request.urlopen(req, timeout=5).status == 200:
                return
        except Exception:
            time.sleep(1)
    raise RuntimeError(f"{url} not ready after {timeout}s")


def start_mock(first_ms: int, gap_ms: int) -> subprocess.Popen:
    env = {**os.environ, "MOCK_PORT": str(MOCK_PORT), "MOCK_FIRST_TOKEN_MS": str(first_ms), "MOCK_TOKEN_GAP_MS": str(gap_ms)}
    p = subprocess.Popen(["node", str(HERE / "mock_upstream.mjs")], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    wait_for(DIRECT, 20, p)
    return p


def start_litellm(workers: int) -> subprocess.Popen:
    RESULTS.mkdir(exist_ok=True)
    log = open(RESULTS / "litellm.log", "w", encoding="utf-8")
    p = subprocess.Popen(
        [str(LITELLM), "--config", str(HERE / "config.yaml"), "--port", str(GW_PORT), "--num_workers", str(workers)],
        stdout=log, stderr=subprocess.STDOUT, env={**os.environ, "PYTHONUTF8": "1"})
    try:
        wait_for(VIA_GW, 240, p)  # a real request through the gateway, so the mock must already be up
    except Exception:
        kill_tree(p)
        raise
    return p


def run_load(url: str, c: int, duration: int, warmup: int, out: Path) -> dict:
    cmd = ["node", str(HERE / "loadgen.mjs"), "--url", url, "--stream", "--c", str(c),
           "--duration", str(duration), "--warmup", str(warmup), "--out", str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=duration + 180)
    if r.returncode != 0:
        raise RuntimeError(f"loadgen failed: {r.stderr[:400]}")
    return json.loads(r.stdout)


# ---- orchestration ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=3)
    ap.add_argument("--duration", type=int, default=20, help="seconds per condition")
    ap.add_argument("--warmup", type=int, default=50)
    ap.add_argument("--workers", type=int, default=2, help="litellm --num_workers (Jakub's run used 2)")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--smoke", action="store_true", help="1 trial, 4 s per condition, c<=10 only")
    args = ap.parse_args()
    if args.smoke:
        args.trials, args.duration, args.warmup = 1, 4, 10
    rng = random.Random(args.seed)
    raw_dir = RESULTS / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []
    mock, gw = start_mock(*SCENARIOS[0][1:3]), None
    try:
        gw = start_litellm(args.workers)
        print(f"litellm up, {len(descendants(gw.pid))} processes", flush=True)
        for trial in range(1, args.trials + 1):
            for s_idx, (name, first, gap, concs) in enumerate(SCENARIOS):
                if args.smoke:
                    concs = [c for c in concs if c <= 10][:2]
                kill_tree(mock)
                mock = start_mock(first, gap)
                conds = [(c, t) for c in concs for t in ("direct", "litellm")]
                rng.shuffle(conds)
                for c, target in conds:
                    out = raw_dir / f"t{trial}_s{s_idx}_c{c}_{target}.json"
                    pids = descendants(gw.pid) if target == "litellm" else []
                    cpu0, mcpu0, t0 = cpu_seconds(pids), cpu_seconds([mock.pid]), time.time()
                    res = run_load(VIA_GW if target == "litellm" else DIRECT, c, args.duration, args.warmup, out)
                    wall = time.time() - t0  # includes warmup, so CPU cores below are a lower bound
                    rows.append({
                        "trial": trial, "scenario": name, "c": c, "target": target, **{
                            "ok": res["ok"], "failed": res["failed"], "rps": res["rps"],
                            "p50": res["total_ms"]["p50"], "p90": res["total_ms"]["p90"], "p99": res["total_ms"]["p99"],
                            "max": res["total_ms"]["max"], "ttft_p50": res["ttft_ms"]["p50"], "ttft_p99": res["ttft_ms"]["p99"],
                            "loadgen_cores": res["loadgen_cpu_cores"],
                            "gateway_cores": round((cpu_seconds(pids) - cpu0) / wall, 2) if pids else None,
                            "mock_cores": round((cpu_seconds([mock.pid]) - mcpu0) / wall, 2),
                        }})
                    r = rows[-1]
                    print(f"t{trial} {name[:12]:<12} c={c:<3} {target:<7} ok={r['ok']:<6} fail={r['failed']:<3} rps={r['rps']:<7} "
                          f"p50={r['p50']:<8} p99={r['p99']:<8} gw_cores={r['gateway_cores']}", flush=True)
    finally:
        kill_tree(mock)
        kill_tree(gw)

    meta = {
        "date": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "host": f"{platform.system()} {platform.release()} {platform.machine()}",
        "cpu": os.environ.get("PROCESSOR_IDENTIFIER", "?"), "logical_cpus": os.cpu_count(),
        "python": platform.python_version(), "node": subprocess.run(["node", "--version"], capture_output=True, text=True).stdout.strip(),
        "litellm": subprocess.run([str(HERE / ".venv/Scripts/python.exe"), "-m", "pip", "show", "litellm"], capture_output=True, text=True).stdout.split("Version:")[1].split()[0],
        "litellm_workers": args.workers, "trials": args.trials, "seconds_per_condition": args.duration, "warmup_requests": args.warmup,
    }
    (RESULTS / "rows.json").write_text(json.dumps({"meta": meta, "rows": rows}, indent=2), encoding="utf-8")
    write_summary(meta, rows)
    return 0


def write_summary(meta: dict, rows: list[dict]) -> None:
    def med(vals):
        vals = [v for v in vals if v is not None]
        return statistics.median(vals) if vals else None

    lines = [
        "# Results", "",
        f"{meta['date']} · {meta['host']} · {meta['cpu']} ({meta['logical_cpus']} logical CPUs) · litellm {meta['litellm']} "
        f"(workers={meta['litellm_workers']}) · node {meta['node']}",
        f"{meta['trials']} trial(s) × {meta['seconds_per_condition']} s per condition, closed loop, streaming. "
        "Values are the median across trials; p99 range is min to max across trials.", "",
        "| scenario | c | target | ok (all trials) | req/s | p50 ms | p99 ms | p99 range | gw cores | loadgen cores | mock cores |",
        "|---|--:|---|--:|--:|--:|--:|---|--:|--:|--:|",
    ]
    keys = sorted({(r["scenario"], r["c"]) for r in rows}, key=lambda k: ([s[0] for s in SCENARIOS].index(k[0]), k[1]))
    overhead = []
    for sc, c in keys:
        per = {}
        for tgt in ("direct", "litellm"):
            g = [r for r in rows if r["scenario"] == sc and r["c"] == c and r["target"] == tgt]
            if not g:
                continue
            p99s = [r["p99"] for r in g]
            per[tgt] = {"p50": med([r["p50"] for r in g]), "p99": med(p99s)}
            lines.append(f"| {sc[:22]} | {c} | {tgt} | {sum(r['ok'] for r in g)} | {med([r['rps'] for r in g])} | {per[tgt]['p50']} | "
                         f"{per[tgt]['p99']} | {min(p99s)} to {max(p99s)} | {med([r['gateway_cores'] for r in g]) or ''} | "
                         f"{med([r['loadgen_cores'] for r in g])} | {med([r['mock_cores'] for r in g])} |")
        if len(per) == 2:
            overhead.append((sc, c, round(per["litellm"]["p50"] - per["direct"]["p50"], 1), round(per["litellm"]["p99"] - per["direct"]["p99"], 1),
                             per["direct"]["p50"]))
    lines += ["", "## Added latency (litellm minus direct, medians across trials)", "",
              "| scenario | c | added p50 ms | added p99 ms | direct p50 ms |", "|---|--:|--:|--:|--:|"]
    lines += [f"| {sc[:22]} | {c} | {a} | {b} | {d} |" for sc, c, a, b, d in overhead]
    (RESULTS / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    sys.exit(main())
