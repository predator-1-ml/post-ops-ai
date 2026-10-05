# Does LiteLLM's streaming p99 depend on load shape?

Prompted by a comment on a LinkedIn post about LiteLLM's 0.66 ms gateway overhead:
"litellm, p99 latency, streaming, /chat/completions was 300 ms", measured with
[ENTERPILOT/ai-gateway-reproducible-benchmark](https://github.com/ENTERPILOT/ai-gateway-reproducible-benchmark)
(closed loop, concurrency 10, zero-latency mock, 2 vCPU box shared by mock, load generator and gateway).

The 0.66 ms in the post comes from LiteLLM's own benchmark of its early-beta **Rust** gateway, which
does not stream yet. Streaming goes through the **Python** proxy, which that same LiteLLM page lists at
257.7 ms p99 added latency. So the two numbers describe different code paths. This experiment asks the
next question: for the Python proxy, how much of a streaming p99 like that is load shape rather than
per-request cost?

## Method

- Gateway: LiteLLM Python proxy 1.103.0 (the version in the commenter's latest run), `--num_workers 2`,
  same config as his harness (no auth, no retries, spend logs off). Wheel sha256 checked against PyPI
  before install (`setup_venv.sh`).
- Upstream: `mock_upstream.mjs`, the same payload shape as his mock (role chunk, 31 token chunks, finish
  chunk, `[DONE]`). Optional model-like latency: 300 ms to first token, then 16 ms per token.
- Load: `loadgen.mjs`, closed loop, streaming `/v1/chat/completions`, same latency definitions as his
  loadgen (total = start to last byte, TTFT = start to first `data:` chunk).
- Every condition runs both **direct** to the mock and **through LiteLLM**, so added latency is the difference.
- Scenarios:
  1. zero-latency upstream at concurrency 1, 2, 4, 10 (his regime is c=10)
  2. model-like upstream at concurrency 10, 50, 100
- Several trials, conditions shuffled per trial; we report the median across trials and the p99 range.
  CPU of the gateway, mock and load generator is recorded so a saturated load generator would be visible.

## Limits

- Windows 11 laptop, no Docker. LiteLLM runs without uvloop here, so absolute numbers are not comparable
  with Linux runs (his or LiteLLM's). The shape, how p99 moves with load, is what transfers.
- Python proxy only. The Rust beta is not public and does not stream, so it is not tested.
- Closed loop at a fixed concurrency, like his harness. Open-loop arrival patterns are not tested.

## Run

```bash
bash setup_venv.sh                         # venv with pinned, digest-checked litellm[proxy]
.venv/Scripts/python run.py --smoke        # 1 short trial to check the setup
.venv/Scripts/python run.py --trials 3 --duration 20
```

Results land in `results/` (`summary.md`, `rows.json`, per-condition JSON in `results/raw/`).
Conclusions are in [FINDINGS.md](FINDINGS.md).
