'use strict';
/**
 * The public demo and Vercel previews run in sample mode (MOCK=1), so they send the pipeline's sample-mode
 * answers, not the saved live ones. Those answers can word the checkout differently (sample-mode Domainly says
 * "acme-robotics.com domain registration"; the live runs say "acme-robotics.com"), so both sets are tested.
 * Run: node tests/sample-mode.test.js
 */
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { recommend } = require('../src/adapter');

const root = path.join(__dirname, '..');
const active = JSON.parse(fs.readFileSync(path.join(root, 'data', 'recommendations.json'), 'utf8'));
const load = (dir, name) => JSON.parse(fs.readFileSync(path.join(root, 'samples', dir, name), 'utf8'));
const WEBSITE_GOAL = 'launch a website for my startup';

let passed = 0;
function test(name, fn) { fn(); passed++; console.log('ok -', name); }

const domainly = [
  ['sample mode', load('sample-mode', 'checkout_01_domain.json')],
  ['live run 1', load('live', 'checkout_01_domain_run1.json')],
  ['live run 2', load('live', 'checkout_01_domain_run2.json')],
];

for (const [label, response] of domainly) {
  test(`Domainly (${label}), blank goal: WAIT and no suitable match`, () => {
    const result = recommend(response, active);
    assert.strictEqual(result.pipelineVerdict.decision, 'WAIT');
    assert.strictEqual(result.matchQuality, 'no_suitable_match');
    assert.strictEqual(result.recommendation, null);
  });
  test(`Domainly (${label}), website goal: WAIT and Floot as a related alternative`, () => {
    const result = recommend(response, active, { founderGoal: WEBSITE_GOAL });
    assert.strictEqual(result.pipelineVerdict.decision, 'WAIT');
    assert.strictEqual(result.matchQuality, 'related_alternative');
    assert.strictEqual(result.recommendation.toolName, 'Floot');   // ties with Squarespace at this goal; name order decides
  });
}

test('sample-mode Sparkforge: Base44 related, verdict unchanged', () => {
  const response = load('sample-mode', 'checkout_02_trial.json');
  const result = recommend(response, active);
  assert.strictEqual(result.pipelineVerdict.decision, response.verdict.decision);
  assert.strictEqual(result.matchQuality, 'related_alternative');
  assert.strictEqual(result.recommendation.toolName, 'Base44');
});

test('sample-mode Cartwheel: no suitable match, verdict unchanged', () => {
  const response = load('sample-mode', 'checkout_03_cart.json');
  const result = recommend(response, active);
  assert.strictEqual(result.pipelineVerdict.decision, response.verdict.decision);
  assert.strictEqual(result.matchQuality, 'no_suitable_match');
});

console.log(`\n${passed} tests passed`);
