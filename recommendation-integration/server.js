'use strict';
/** Zero-dependency local server.
 *  GET  /              demo page
 *  GET  /api/health    status
 *  GET  /api/recommendations   the active recommendation library (real Floot editorial export by default)
 *  GET  /api/samples   the 3 pipeline sample inputs
 *  POST /api/recommend { pipeline: <analyze-response|facts>, founderGoal?: string }
 */
const fs = require('fs');
const http = require('http');
const path = require('path');
const { recommend } = require('./src/adapter');

const ROOT = __dirname;
const recs = JSON.parse(fs.readFileSync(path.join(ROOT, 'data', 'recommendations.json'), 'utf8'));
const samples = fs.readdirSync(path.join(ROOT, 'samples')).filter((f) => f.endsWith('.json')).sort()
  .map((f) => ({ id: f.replace(/\.json$/, ''), input: JSON.parse(fs.readFileSync(path.join(ROOT, 'samples', f), 'utf8')) }));

function send(res, code, obj, type = 'application/json; charset=utf-8') {
  const body = typeof obj === 'string' ? obj : JSON.stringify(obj, null, 2);
  res.writeHead(code, { 'Content-Type': type, 'Access-Control-Allow-Origin': '*' });
  res.end(body);
}

const server = http.createServer((req, res) => {
  const url = new URL(req.url, 'http://localhost');
  if (req.method === 'OPTIONS') { res.writeHead(204, { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': 'Content-Type', 'Access-Control-Allow-Methods': 'GET,POST,OPTIONS' }); return res.end(); }
  if (url.pathname === '/') return send(res, 200, fs.readFileSync(path.join(ROOT, 'public', 'index.html'), 'utf8'), 'text/html; charset=utf-8');
  if (url.pathname === '/api/health') return send(res, 200, { ok: true, adapter: 'ais-cart-recommendation-adapter 0.3.2', recommendations: recs.recommendations.length, recommendationsStatus: recs.status, dataStatus: recs.dataStatus, pricingStatus: recs.pricingStatus, samples: samples.map((s) => s.id) });
  if (url.pathname === '/api/recommendations') return send(res, 200, recs);
  if (url.pathname === '/api/samples') return send(res, 200, { samples });
  if (url.pathname === '/api/recommend' && req.method === 'POST') {
    let body = '';
    req.on('data', (c) => { body += c; if (body.length > 2_000_000) req.destroy(); });
    req.on('end', () => {
      try {
        const parsed = JSON.parse(body || '{}');
        const pipeline = parsed.pipeline || parsed.facts || parsed;
        if (!pipeline || typeof pipeline !== 'object') throw new Error('send { "pipeline": <pipeline response or facts>, "founderGoal": "..." }');
        return send(res, 200, recommend(pipeline, recs, { founderGoal: parsed.founderGoal || '' }));
      } catch (e) { return send(res, 400, { error: { code: 'bad_request', message: String(e.message || e) } }); }
    });
    return;
  }
  return send(res, 404, { error: { code: 'not_found', message: url.pathname } });
});

const port = Number(process.env.PORT || 4173);
if (require.main === module) server.listen(port, () => console.log(`AI's Cart recommendation demo: http://localhost:${port}`));
module.exports = server;
