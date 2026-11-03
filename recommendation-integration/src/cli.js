'use strict';
/** CLI: node src/cli.js <pipeline-json> [--goal "..."] [--recs data/recommendations.json] [--pretty] */
const fs = require('fs');
const path = require('path');
const { recommend } = require('./adapter');

function arg(name, fallback) {
  const i = process.argv.indexOf(name);
  return i >= 0 ? process.argv[i + 1] : fallback;
}
const file = process.argv[2];
if (!file || file.startsWith('--')) {
  console.error('Usage: node src/cli.js <pipeline-json> [--goal "founder goal"] [--recs data/recommendations.json] [--pretty]');
  process.exit(2);
}
const input = JSON.parse(fs.readFileSync(file, 'utf8'));
const recPath = arg('--recs', path.join(__dirname, '..', 'data', 'recommendations.json'));
const recs = JSON.parse(fs.readFileSync(recPath, 'utf8'));
const result = recommend(input, recs, { founderGoal: arg('--goal', '') });
console.log(JSON.stringify(result, null, process.argv.includes('--pretty') ? 2 : 2));
