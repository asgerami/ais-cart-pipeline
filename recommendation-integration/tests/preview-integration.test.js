'use strict';
/** Preview API contract: verdict-independent recommendation, optional goal fallback, four pinned runs. */
const assert = require('assert');
const fs = require('fs');
const path = require('path');

const root = path.join(__dirname, '..');
const recommendationRoot = path.join(root, '..', 'recommendation-integration');
const apiFile = fs.readFileSync(path.join(root, '..', 'api', 'recommend.js'), 'utf8');
const page = fs.readFileSync(path.join(root, '..', 'index.html'), 'utf8');
const { recommend } = require('../src/adapter');
const library = JSON.parse(fs.readFileSync(path.join(recommendationRoot, 'data', 'recommendations.json'), 'utf8'));
const live = (name) => JSON.parse(fs.readFileSync(path.join(recommendationRoot, 'samples', 'live', name), 'utf8'));

const question = 'Should I complete this purchase?';
const run = (name, goal) => recommend(live(name), library, { founderGoal: goal ?? question });

let passed = 0;
function test(name, fn) { fn(); passed++; console.log('ok -', name); }

test('Domainly with generic question: verdict stays WAIT, no suitable match', () => {
  const result = run('checkout_01_domain_run1.json');
  assert.strictEqual(result.pipelineVerdict.decision, live('checkout_01_domain_run1.json').verdict.decision);
  assert.strictEqual(result.pipelineVerdict.decision, 'WAIT');
  assert.strictEqual(result.matchQuality, 'no_suitable_match');
  assert.strictEqual(result.recommendation, null);
});

test('Domainly with website goal: verdict stays WAIT, Floot is related', () => {
  const result = run('checkout_01_domain_run1.json', 'launch a website for my startup');
  assert.strictEqual(result.pipelineVerdict.decision, 'WAIT');
  assert.strictEqual(result.recommendation.toolName, 'Floot');
  assert.strictEqual(result.matchQuality, 'related_alternative');
  assert.ok(result.recommendation.evidenceIds.includes('floot-app'));
});

test('Sparkforge: verdict TRIAL unchanged, Base44 remains related', () => {
  const result = run('checkout_02_trial_run1.json');
  assert.strictEqual(result.pipelineVerdict.decision, 'TRIAL');
  assert.strictEqual(result.recommendation.toolName, 'Base44');
  assert.strictEqual(result.matchQuality, 'related_alternative');
});

test('Cartwheel: verdict BUY unchanged, no suitable match', () => {
  const result = run('checkout_03_cart_run1.json');
  assert.strictEqual(result.pipelineVerdict.decision, 'BUY');
  assert.strictEqual(result.matchQuality, 'no_suitable_match');
  assert.strictEqual(result.recommendation, null);
});

test('Recommendation API omits prices, savings and commercial pricing fields', () => {
  assert.match(apiFile, /function publicRecommendation/);
  for (const forbidden of ['pricing:', 'savings:', 'monthlyUsd', 'annualUsd', 'savingsFor']) {
    assert.ok(!apiFile.includes(forbidden), `API must not expose ${forbidden}`);
  }
  assert.match(apiFile, /goalFallback/);
  assert.match(apiFile, /recommend\(pipeline, library, \{ founderGoal \}\)/);
});

test('Shopper page mounts recommendation between check list and View evidence without changing verdict', () => {
  const checkIndex = page.indexOf('Check before you pay');
  const recommendationIndex = page.indexOf('id="recommendation"');
  const evidenceIndex = page.indexOf('View evidence');
  assert.ok(checkIndex > 0 && recommendationIndex > checkIndex && evidenceIndex > recommendationIndex);
  assert.match(page, /id="shopperGoal"/);
  assert.match(page, /Optional: what are you shopping for\?/);
  assert.match(page, /match-label/);
  assert.match(page, /fetch\("\/api\/recommend"/);
  assert.match(page, /Verdict unchanged by this module/);
});

test('Amir review fixes: goal reset, punctuation, require-loaded library, goal-stale note', () => {
  assert.match(page, /\$\("shopperGoal"\)\.value = "";/);
  assert.match(page, /Goal used: \$\{esc\(data\.shopperGoal\)\}\./);
  assert.match(page, /id="goalStale"/);
  assert.match(page, /Goal changed\. Press Check before I buy to update the recommendation\./);
  assert.match(page, /checkedGoal/);
  assert.match(apiFile, /require\('\.\.\/recommendation-integration\/data\/recommendations\.json'\)/);
  assert.ok(!apiFile.includes('process.cwd()'), 'Vercel must trace the library through require()');
  assert.ok(!apiFile.includes('readFileSync'), 'library must not be loaded from a cwd-built path');
});

console.log(`\n${passed} tests passed`);
