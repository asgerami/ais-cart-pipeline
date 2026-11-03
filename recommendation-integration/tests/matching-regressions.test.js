'use strict';
/** Regression tests for Amir's substring-matching findings: node tests/matching-regressions.test.js */
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
  test(`live Sparkforge run ${run}: whole-word matching keeps it apps-only and removes Canva backup`, () => {
    const result = recommend(live(`checkout_02_trial_run${run}.json`), active);
    assert.deepStrictEqual(result.checkout.inferredCategories, ['apps']);
    assert.strictEqual(result.recommendation.toolName, 'Base44');
    assert.ok(!result.otherCandidates.some((candidate) => candidate.toolName === 'Canva'));
    assert.strictEqual(result.matchQuality, 'related_alternative');
  });

  test(`live Sparkforge run ${run}: generic-plan wording replaces the app/MVP claim`, () => {
    const result = recommend(live(`checkout_02_trial_run${run}.json`), active);
    assert.ok(result.recommendation.match.explanation.includes('only names a generic plan'));
    assert.ok(!result.recommendation.match.explanation.includes('checkout concerns building an app/MVP'));
  });
}

test('substring bait does not create categories or overlaps by itself', () => {
  const response = live('checkout_02_trial_run1.json');
  response.facts.other_conditions = { status: 'observed', value: 'Your card is required before the day starts', evidence: 'synthetic regression' };
  const result = recommend(response, active);
  assert.ok(!result.checkout.inferredCategories.includes('graphics'));
  assert.ok(!result.otherCandidates.some((candidate) => candidate.toolName === 'Canva'));
});

console.log(`\n${passed} tests passed`);
