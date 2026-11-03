'use strict';
/** Regression tests on the six saved live /api/analyze responses (Nov 3, 2026): node tests/live-responses.test.js */
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { recommend } = require('../src/adapter');

const root = path.join(__dirname, '..');
const active = JSON.parse(fs.readFileSync(path.join(root, 'data', 'recommendations.json'), 'utf8'));
const live = (name) => JSON.parse(fs.readFileSync(path.join(root, 'samples', 'live', name), 'utf8'));

let passed = 0;
function test(name, fn) { fn(); passed++; console.log('ok -', name); }

for (const run of [1, 2]) {
  test(`live Sparkforge run ${run}, no founder goal: Base44 is related, never a direct substitute`, () => {
    const response = live(`checkout_02_trial_run${run}.json`);
    const result = recommend(response, active);            // the caller forwards the response as is
    assert.strictEqual(result.founderGoal, response.question);
    assert.strictEqual(result.matchQuality, 'related_alternative');
    assert.notStrictEqual(result.recommendation.match.quality, 'direct_match');
    assert.ok(result.recommendation.match.explanation.includes('does not say what this product does'));
  });
}

test('live responses: every pipeline verdict is passed through unchanged, with and without a goal', () => {
  for (const s of ['checkout_01_domain', 'checkout_02_trial', 'checkout_03_cart']) {
    for (const run of [1, 2]) {
      const response = live(`${s}_run${run}.json`);
      for (const options of [{}, { founderGoal: 'launch a website for my startup' }]) {
        assert.strictEqual(recommend(response, active, options).pipelineVerdict.decision, response.verdict.decision);
      }
    }
  }
});

test('live responses: no direct match is claimed for any of the three checkouts', () => {
  for (const s of ['checkout_01_domain', 'checkout_02_trial', 'checkout_03_cart']) {
    for (const run of [1, 2]) {
      assert.notStrictEqual(recommend(live(`${s}_run${run}.json`), active).matchQuality, 'direct_match', `${s} run ${run}`);
    }
  }
});

test('live Cartwheel (physical goods) has no suitable match', () => {
  for (const run of [1, 2]) assert.strictEqual(recommend(live(`checkout_03_cart_run${run}.json`), active).matchQuality, 'no_suitable_match');
});

console.log(`\n${passed} tests passed`);
