'use strict';
// Local Python development server bridge; calls the same handler Vercel runs.
const handler = require('../api/recommend');
let input = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', chunk => { input += chunk; });
process.stdin.on('end', async () => {
  const req = JSON.parse(input);
  const headers = {};
  const res = {
    setHeader(k, v) { headers[k] = v; },
    status(code) { this.code = code; return this; },
    json(body) { process.stdout.write(JSON.stringify({status: this.code, headers, body})); },
    end() { this.json(null); },
  };
  await handler(req, res);
});
