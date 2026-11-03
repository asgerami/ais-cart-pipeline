'use strict';
/** Offline regression tests for the real Floot integration: node tests/floot-adapter.test.js */
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { recommend } = require('../src/adapter');
const { normalizeRecommendations } = require('../src/normalize-recommendations');

const root = path.join(__dirname, '..');
const active = JSON.parse(fs.readFileSync(path.join(root, 'data', 'recommendations.json'), 'utf8'));
const original = JSON.parse(fs.readFileSync(path.join(root, 'data', 'floot', 'aiscart_floot_recommendations.original.json'), 'utf8'));
const baseline = JSON.parse(fs.readFileSync(path.join(root, 'data', 'baseline', 'recommendations.simulated.json'), 'utf8'));
const load = (name) => JSON.parse(fs.readFileSync(path.join(root, 'samples', name), 'utf8'));

let passed = 0;
function test(name, fn) { fn(); passed++; console.log('ok -', name); }

test('real Floot export preserves all 12 editorial records and IDs', () => {
  assert.strictEqual(active.status, 'real-floot-editorial');
  assert.strictEqual(active.recommendations.length, 12);
  assert.deepStrictEqual(active.recommendations.map((record) => record.id), original.records.map((record) => record.id));
  for (let i = 0; i < original.records.length; i++) {
    const source = original.records[i];
    const record = active.recommendations[i];
    assert.strictEqual(record.editorial.id, source.id);
    assert.strictEqual(record.editorial.why, source.why);
    assert.strictEqual(record.editorial.caution, source.caution);
    assert.strictEqual(record.confidence, source.confidence);
    assert.deepStrictEqual(record.evidenceIds, source.evidenceIds);
  }
});

test('Floot categories map to adapter categories without losing source labels', () => {
  assert.deepStrictEqual([...new Set(active.recommendations.map((record) => record.category))].sort(),
    ['apps', 'graphics', 'video', 'websites', 'writing']);
  assert.strictEqual(active.recommendations.find((record) => record.id === 'photos-canva').sourceCategory, 'Photos & graphics');
  assert.strictEqual(active.recommendations.find((record) => record.id === 'mvp-floot').sourceCategory, 'Apps & MVPs');
});

test('pricing stays unknown for every real Floot record', () => {
  assert.strictEqual(original.pricing_status, 'not provided in source; do not infer');
  for (const record of active.recommendations) {
    assert.strictEqual(record.pricing.status, 'unknown');
    assert.strictEqual(record.pricing.monthlyUsd, null);
    assert.strictEqual(record.pricing.annualUsd, null);
    assert.strictEqual(record.pricing.freeTier, null);
  }
});

test('checkout_01: Domainly has no direct Floot substitute, only a related website alternative', () => {
  const result = recommend(load('checkout_01_domain.json'), active, { founderGoal: 'launch a website for my startup' });
  assert.ok(['website-floot', 'website-squarespace'].includes(result.recommendation.id));
  const sourceRecord = original.records.find((record) => record.id === result.recommendation.id);
  assert.strictEqual(result.recommendation.sourceCategory, sourceRecord.category);
  assert.strictEqual(result.recommendation.category, 'websites');
  assert.strictEqual(result.matchQuality, 'related_alternative');
  assert.strictEqual(result.recommendation.match.quality, 'related_alternative');
  assert.ok(result.recommendation.match.missingDirectJobs.includes('domain_registration'));
  assert.deepStrictEqual(result.recommendation.pricing.status, 'unknown');
  assert.strictEqual(result.recommendation.savings.amountUsd, null);
  assert.ok(result.risks.some((risk) => risk.flag === 'renewal_price_not_shown'));
  assert.ok(result.risks.some((risk) => risk.flag === 'multi_year_upfront'));
});

test('checkout_02: Sparkforge automation goal makes Base44 related, not a direct substitute', () => {
  const result = recommend(load('checkout_02_trial.json'), original, { founderGoal: 'automate my workflow' });
  assert.ok(result.recommendation);
  assert.strictEqual(result.recommendation.category, 'apps');
  assert.strictEqual(result.matchQuality, 'related_alternative');
  assert.ok(result.recommendation.evidenceIds.length > 0);
  assert.ok(result.recommendation.caution.length > 0);
  assert.strictEqual(result.recommendation.savings.amountUsd, null);
  assert.strictEqual(result.recommendation.savings.kind, 'pricing_unknown');
  assert.ok(result.risks.some((risk) => risk.flag === 'trial_converts_to_paid'));
  assert.ok(result.risks.some((risk) => risk.flag === 'text_cut_off'));
});

test('checkout_02 with the generic purchase question stays related (Lance regression)', () => {
  for (const question of ['', 'Should I complete this purchase?', 'Should I buy this?']) {
    const wrapped = { mode: 'live', question, verdict: { decision: 'TRIAL', headline: 'Trial first', confidence: 'medium' }, facts: load('checkout_02_trial.json') };
    const result = recommend(wrapped, active, {});
    assert.ok(result.recommendation, `expected a related candidate for question: ${question}`);
    assert.strictEqual(result.matchQuality, 'related_alternative', `generic question must not be direct: ${question}`);
    assert.strictEqual(result.recommendation.category, 'apps');
    assert.strictEqual(result.pipelineVerdict.decision, 'TRIAL');
  }
});

test('a direct Floot match is still labelled direct when checkout explicitly seeks an MVP builder', () => {
  const facts = load('checkout_02_trial.json');
  facts.line_items[0].name.value = 'App builder platform for MVP prototype';
  const result = recommend(facts, active, { founderGoal: 'build an MVP prototype' });
  assert.strictEqual(result.matchQuality, 'direct_match');
  assert.strictEqual(result.recommendation.category, 'apps');
});

test('checkout_03: physical cart remains no suitable match', () => {
  const result = recommend(load('checkout_03_cart.json'), active, { founderGoal: 'buy office equipment' });
  assert.strictEqual(result.status, 'no_match');
  assert.strictEqual(result.matchQuality, 'no_suitable_match');
  assert.strictEqual(result.recommendation, null);
  assert.strictEqual(result.risks.length, 0);
});

test('preserved simulated baseline remains reproducible and distinct from real results', () => {
  assert.strictEqual(baseline.recommendations.length, 12);
  const result = recommend(load('checkout_01_domain.json'), baseline, { founderGoal: 'launch a website for my startup' });
  assert.strictEqual(result.recommendation.id, 'rec-websites-domain');
  assert.strictEqual(result.dataSource.status, 'simulated-or-unspecified');
});

test('invalid recommendation library fails explicitly', () => {
  assert.throws(() => normalizeRecommendations({ records: [{ id: 'x', category: 'Nope', tool: 'X' }] }), /unsupported Floot category/);
  assert.throws(() => recommend(load('checkout_01_domain.json'), { records: [{}] }, {}), /recommendation record/);
});

console.log(`\n${passed} tests passed`);
