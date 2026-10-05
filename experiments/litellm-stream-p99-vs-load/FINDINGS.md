# Findings

LiteLLM Python proxy 1.103.0, `--num_workers 2`, streaming `/v1/chat/completions`, closed loop.
3 trials × 20 s per condition, 42 conditions, 0 failed requests. Full table: [results/summary.md](results/summary.md).
Load generator and mock never exceeded ~1 core each, so neither was the bottleneck.

## 1. The 300 ms streaming p99 reproduces in shape

Against an instant mock at concurrency 10 (the commenter's regime), streaming p99 through LiteLLM was
**417 ms** here (his run on Linux: 296 ms). The gateway was at its CPU ceiling (1.84 cores for 2 workers)
and capped at **~49 streaming req/s**.

## 2. Most of that tail is queueing, not per-request cost

| zero-latency upstream | added p50 | added p99 |
|---|--:|--:|
| c=1 | 45 ms | 82 ms |
| c=4 | 87 ms | 187 ms |
| c=10 | 263 ms | 411 ms |

At c=1 the proxy adds about 45 ms per streamed response (31 token chunks) on this machine. As concurrency
rises against an upstream that answers instantly, requests queue behind the CPU-bound workers.

## 3. With model-like latency, the overhead is small until you approach capacity

Upstream at ~300 ms to first token plus 16 ms per token (~1.2 s per call):

| concurrency | achieved req/s (direct / litellm) | added p50 | added p99 |
|---|--:|--:|--:|
| 10 | 8.2 / 8.1 | 44 ms (~4%) | 71 ms (~6%) |
| 50 | 40.5 / 32.7 | 234 ms | 895 ms |
| 100 | 80.5 / 43.4 | 1,315 ms | 2,079 ms |

At realistic load the Python proxy adds tens of milliseconds to a ~1.2 s call. Near its streaming
throughput ceiling (~45 to 49 req/s for 2 workers here) the tail grows fast, and past it throughput caps.

## What this means

- The commenter's number is real for the Python proxy when it runs near capacity. It is not a contradiction of
  the 0.66 ms figure, which is LiteLLM's early-beta Rust gateway on a route that does not stream yet.
- Below capacity, expect tens of ms per streaming request from the Python proxy, not sub-millisecond.
- Size workers and replicas for peak streaming requests per second, and watch the gateway's CPU, not just its latency.

## Limits

- Windows 11 laptop (i7-14650HX, 24 logical CPUs), no Docker, LiteLLM without uvloop. Absolute numbers are likely
  pessimistic compared with Linux. The shape is what transfers.
- Python proxy only. The Rust beta is not public and does not stream.
- Closed loop only, 2 workers, 3 trials. p99.9 is not reported: no condition reached the 5,000 samples per trial it needs.
