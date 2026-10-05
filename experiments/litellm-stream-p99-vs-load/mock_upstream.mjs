// Mock OpenAI-compatible upstream. Same payload shape as the mock in
// ENTERPILOT/ai-gateway-reproducible-benchmark (role chunk, 31 token chunks, finish chunk, [DONE]),
// reimplemented here in Node so it runs without Docker or Go.
//
// MOCK_FIRST_TOKEN_MS / MOCK_TOKEN_GAP_MS add model-like latency. Both default to 0, which is
// the zero-latency regime that closed-loop gateway benchmarks usually run in.
import http from 'node:http';

const port = Number(process.env.MOCK_PORT || 9999);
const firstMs = Number(process.env.MOCK_FIRST_TOKEN_MS || 0);
const gapMs = Number(process.env.MOCK_TOKEN_GAP_MS || 0);

const TOKENS = [
  'This ', 'is ', 'a ', 'benchmark ', 'response ', 'from ', 'the ', 'mock ', 'backend ', 'server. ',
  'It ', 'contains ', 'enough ', 'text ', 'to ', 'be ', 'representative ', 'of ', 'a ', 'typical ',
  'short ', 'AI ', 'response ', 'that ', 'would ', 'be ', 'returned ', 'in ', 'production ', 'use ', 'cases.',
];
const FULL_TEXT = TOKENS.join('');
const USAGE = { prompt_tokens: 25, completion_tokens: 35, total_tokens: 60 };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

let seq = 0;
const chunk = (id, created, delta, finish, usage) => JSON.stringify({
  id, object: 'chat.completion.chunk', created, model: 'gpt-4o-mini',
  choices: [{ index: 0, delta, finish_reason: finish }], ...(usage ? { usage } : {}),
});

const server = http.createServer((req, res) => {
  if (req.url === '/health') { res.writeHead(200, { 'Content-Type': 'application/json' }); res.end('{"status":"ok"}'); return; }
  if (req.method !== 'POST' || !/\/chat\/completions$/.test(req.url)) { res.writeHead(404).end(); return; }
  const parts = [];
  req.on('data', (c) => parts.push(c));
  req.on('end', async () => {
    let body;
    try { body = JSON.parse(Buffer.concat(parts).toString()); } catch { res.writeHead(400).end('invalid body'); return; }
    const id = `chatcmpl-bench-${++seq}`;
    const created = Math.floor(Date.now() / 1000);

    if (!body.stream) {
      if (firstMs || gapMs) await sleep(firstMs + gapMs * TOKENS.length);
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({
        id, object: 'chat.completion', created, model: 'gpt-4o-mini',
        choices: [{ index: 0, message: { role: 'assistant', content: FULL_TEXT }, finish_reason: 'stop' }],
        usage: USAGE,
      }));
      return;
    }

    res.writeHead(200, { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache', Connection: 'keep-alive' });
    const send = (data) => res.write(`data: ${data}\n\n`);
    if (firstMs) await sleep(firstMs);
    send(chunk(id, created, { role: 'assistant', content: '' }, null));
    for (const t of TOKENS) {
      if (gapMs) await sleep(gapMs);
      send(chunk(id, created, { content: t }, null));
    }
    send(chunk(id, created, {}, 'stop', USAGE));
    send('[DONE]');
    res.end();
  });
});
server.keepAliveTimeout = 65_000;
server.listen(port, '127.0.0.1', () => console.error(`mock listening on :${port} first=${firstMs}ms gap=${gapMs}ms`));
