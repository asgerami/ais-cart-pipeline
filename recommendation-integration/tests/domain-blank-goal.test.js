'use strict';
/** Published-preview regression: Domainly mock/sample blank goal must not surface Floot. */
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { recommend } = require('../src/adapter');

const root = path.join(__dirname, '..');
const library = JSON.parse(fs.readFileSync(path.join(root, 'data', 'recommendations.json'), 'utf8'));
const mockData = JSON.parse(fs.readFileSync(path.join(root, '..', 'aiscart', 'mock_data.json'), 'utf8'));
const domainLabel = Object.values(mockData).find((record) => record.id === 'checkout_01_domain');
const sampleFacts = JSON.parse(fs.readFileSync(path.join(root, 'samples', 'checkout_01_domain.json'), 'utf8'));

let passed = 0;
function test(name, fn) { fn(); passed++; console.log('ok -', name); }

for (const [name, facts] of [['saved Domainly mock record', domainLabel], ['saved Domainly sample facts', sampleFacts]]) {
  test(`${name}: blank/default goal gives no suitable match`, () => {
    for (const goal of ['', 'Should I complete this purchase?']) {
      const result = recommend(facts, library, { founderGoal: goal });
      assert.strictEqual(result.matchQuality, 'no_suitable_match');
      assert.strictEqual(result.recommendation, null);
      assert.ok(result.checkout.uncertaintyFlags.includes('renewal_price_not_shown'));
    }
  });

  test(`${name}: website goal still gives related Floot`, () => {
    const result = recommend(facts, library, { founderGoal: 'launch a website for my startup' });
    assert.strictEqual(result.matchQuality, 'related_alternative');
    assert.strictEqual(result.recommendation.toolName, 'Floot');
  });
}

console.log(`\n${passed} tests passed`);
