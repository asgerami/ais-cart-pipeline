'use strict';
/** Keeps the original simulated-baseline expectations executable after the active library became real Floot data. */
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { recommend, parseMoney } = require('../src/adapter');

const root = path.join(__dirname, '..');
const recs = JSON.parse(fs.readFileSync(path.join(root, 'data', 'baseline', 'recommendations.simulated.json'), 'utf8'));
const load = (name) => JSON.parse(fs.readFileSync(path.join(root, 'samples', name), 'utf8'));
let passed = 0;
function test(name, fn) { fn(); passed++; console.log('ok -', name); }

test('simulated baseline has exactly 12 records across the 5 adapter categories', () => {
  assert.strictEqual(recs.recommendations.length, 12);
  assert.deepStrictEqual([...new Set(recs.recommendations.map((record) => record.category))].sort(),
    ['apps', 'graphics', 'video', 'websites', 'writing']);
});

test('baseline checkout_01 gives a direct simulated domain recommendation and two high risks', () => {
  const result = recommend(load('checkout_01_domain.json'), recs, { founderGoal: 'launch a website for my startup' });
  assert.strictEqual(result.recommendation.id, 'rec-websites-domain');
  assert.strictEqual(result.matchQuality, 'direct_match');
  assert.ok(result.risks.filter((risk) => risk.severity === 'high').length >= 2);
  assert.strictEqual(result.recommendation.savings.amountUsd, null);
});

test('baseline checkout_02 gives Make, coherently labelled related because its editorial scope is workflow automation', () => {
  const result = recommend(load('checkout_02_trial.json'), recs, { founderGoal: 'automate my workflow' });
  assert.strictEqual(result.recommendation.id, 'rec-apps-automation-make');
  assert.strictEqual(result.matchQuality, 'related_alternative');
  assert.strictEqual(result.recommendation.savings.amountUsd, 0);
});

test('baseline checkout_03 remains no_match and bad input still fails', () => {
  const result = recommend(load('checkout_03_cart.json'), recs, { founderGoal: 'buy office equipment' });
  assert.strictEqual(result.status, 'no_match');
  assert.strictEqual(parseMoney({ status: 'observed', value: '$1,234.50' }), 1234.5);
  assert.throws(() => recommend({ hello: 'world' }, recs, {}), /unrecognised input/);
});

console.log(`\n${passed} tests passed`);
