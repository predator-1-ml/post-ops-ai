// Closed-loop load generator for OpenAI-style /chat/completions, streaming or not.
// Same measurement definitions as the loadgen in ENTERPILOT/ai-gateway-reproducible-benchmark:
// total latency = request start to last byte, TTFT = request start to first "data:" chunk,
// closed loop = each of C workers sends its next request as soon as the previous one finishes.
//
//   node loadgen.mjs --url http://127.0.0.1:4000/v1/chat/completions --stream --c 10 --duration 20
//
// Prints one JSON summary on stdout. Percentiles use linear interpolation. p99.9 is only
// reported when there are at least 5,000 successful samples; below that it is null.
import http from 'node:http';
import { writeFileSync } from 'node:fs';

const args = {};
for (let i = 2; i < process.argv.length; i++) {
  const k = process.argv[i];
  if (!k.startsWith('--')) continue;
  const next = process.argv[i + 1];
  if (next === undefined || next.startsWith('--')) args[k.slice(2)] = true;
  else { args[k.slice(2)] = next; i++; }
}
const url = new URL(args.url);
const stream = Boolean(args.stream);
const c = Number(args.c || 1);
const durationS = Number(args.duration || 0);
const nMax = Number(args.n || Infinity);
const warmup = Number(args.warmup || 0);
if (!durationS && !Number.isFinite(nMax)) { console.error('need --duration or --n'); process.exit(2); }

const payload = JSON.stringify({
  model: args.model || 'gpt-4o-mini', stream,
  messages: [{ role: 'user', content: 'Say hello for a benchmark test.' }],
});
const agent = new http.Agent({ keepAlive: true, maxSockets: Math.max(c, 10) * 2 });
const msSince = (t0) => Number(process.hrtime.bigint() - t0) / 1e6;

function once() {
  return new Promise((resolve) => {
    const t0 = process.hrtime.bigint();
    const req = http.request({
      host: url.hostname, port: url.port, path: url.pathname, method: 'POST', agent, timeout: 30_000,
      headers: { 'Content-Type': 'application/json', Authorization: 'Bearer sk-bench-test-key', 'Content-Length': Buffer.byteLength(payload) },
    }, (res) => {
      if (res.statusCode !== 200) { res.resume(); res.on('end', () => resolve({ err: `HTTP ${res.statusCode}` })); return; }
      let ttft = null, tail = '', done = !stream;
      res.setEncoding('utf8');
      res.on('data', (d) => {
        if (!stream) return;
        if (ttft === null && d.includes('data: ')) ttft = msSince(t0);
        tail = (tail + d).slice(-32);
        if (tail.includes('[DONE]')) done = true;
      });
      res.on('end', () => { const total = msSince(t0); resolve(done ? { ttft: ttft ?? total, total } : { err: 'stream ended without [DONE]' }); });
      res.on('error', (e) => resolve({ err: e.message }));
    });
    req.on('timeout', () => req.destroy(new Error('timeout')));
    req.on('error', (e) => resolve({ err: e.message }));
    req.end(payload);
  });
}

async function drive(workers, endAt, countLimit, sink) {
  let started = 0;
  await Promise.all(Array.from({ length: workers }, async () => {
    while ((!endAt || performance.now() < endAt) && started < countLimit) {
      started++;
      sink.push(await once());
    }
  }));
}

function pct(sorted, p) {
  if (!sorted.length) return null;
  const idx = (p / 100) * (sorted.length - 1), lo = Math.floor(idx), hi = Math.ceil(idx);
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (idx - lo);
}
const r2 = (v) => (v === null ? null : Math.round(v * 100) / 100);
function summarize(values) {
  const s = [...values].sort((a, b) => a - b);
  return {
    p50: r2(pct(s, 50)), p90: r2(pct(s, 90)), p95: r2(pct(s, 95)), p99: r2(pct(s, 99)),
    p999: s.length >= 5000 ? r2(pct(s, 99.9)) : null, max: r2(s[s.length - 1] ?? null),
    mean: r2(s.length ? s.reduce((a, b) => a + b, 0) / s.length : null),
  };
}

if (warmup) await drive(Math.min(c, 10), 0, warmup, []);

const cpu0 = process.cpuUsage();
const t0 = performance.now();
const results = [];
await drive(c, durationS ? t0 + durationS * 1000 : 0, nMax, results);
const wallS = (performance.now() - t0) / 1000;
const cpu = process.cpuUsage(cpu0);

const ok = results.filter((r) => !r.err);
const errors = {};
for (const r of results) if (r.err) errors[r.err] = (errors[r.err] || 0) + 1;
const out = {
  url: args.url, stream, mode: 'closed', concurrency: c,
  ok: ok.length, failed: results.length - ok.length, errors,
  wall_s: r2(wallS), rps: r2(ok.length / wallS),
  loadgen_cpu_cores: r2((cpu.user + cpu.system) / 1e6 / wallS),
  total_ms: summarize(ok.map((r) => r.total)),
  ttft_ms: stream ? summarize(ok.map((r) => r.ttft)) : null,
};
if (args.out) writeFileSync(args.out, JSON.stringify(out, null, 2));
console.log(JSON.stringify(out));
agent.destroy();
