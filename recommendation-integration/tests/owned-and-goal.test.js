'use strict';
/**
 * Owned tools and goal-first recommendations (adapter 0.4.0).
 * Goal-first: the shopper has no screenshot yet, only a goal in their own words.
 * Owned tools: a tool the shopper already has comes first when it fits, and a cart that repeats one is flagged.
 * Run: node tests/owned-and-goal.test.js
 */
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { recommend } = require('../src/adapter');

const root = path.join(__dirname, '..');
const lib = JSON.parse(fs.readFileSync(path.join(root, 'data', 'recommendations.json'), 'utf8'));
const sample = (name) => JSON.parse(fs.readFileSync(path.join(root, 'samples', 'sample-mode', name), 'utf8'));
const goal = (text, ownedTools) => recommend(null, lib, { goalOnly: true, founderGoal: text, ownedTools });
const LANCE = 'I need to get more people to sign up on my website. Where do I start?';

let passed = 0;
function test(name, fn) { fn(); passed++; console.log('ok -', name); }

// ---------- goal-first ----------
test("Lance's sign-up goal: a website tool that fits the goal, despite the sentence's punctuation", () => {
  const r = goal(LANCE);
  assert.strictEqual(r.inputMode, 'goal_only');
  assert.deepStrictEqual(r.goalCategories, ['websites']);
  assert.strictEqual(r.matchQuality, 'goal_match');
  assert.strictEqual(r.recommendation.category, 'websites');
  assert.strictEqual(r.pipelineVerdict, null);
});

test('"build an app" picks an app builder, not a website builder', () => {
  const r = goal('I want to build an app for my startup');
  assert.strictEqual(r.recommendation.category, 'apps');
  assert.strictEqual(r.matchQuality, 'goal_match');
});

test('a writing goal finds the writing tools', () => {
  const r = goal('help me write a grant proposal');
  assert.strictEqual(r.recommendation.category, 'writing');
});

test('a goal the library does not cover says so plainly, without a tool', () => {
  const r = goal('plan my wedding');
  assert.strictEqual(r.recommendation, null);
  assert.strictEqual(r.matchQuality, 'no_suitable_match');
  assert.match(r.noMatchReason, /library has no tool for this goal/);
});

test('goal-first needs a goal', () => {
  assert.throws(() => goal('   '), /needs a goal/);
});

// ---------- owned tools, goal-first ----------
test('an owned tool that fits comes first; the new-tool suggestion is something else', () => {
  const r = goal('I want to make a short promo video', ['Canva']);
  assert.strictEqual(r.ownedRecommendation.toolName, 'Canva');
  assert.strictEqual(r.ownedRecommendation.owned, true);
  assert.notStrictEqual(r.recommendation.toolName, 'Canva');
  assert.strictEqual(r.recommendation.owned, false);
  assert.ok(r.otherCandidates.every((c) => c.toolName !== 'Canva'));
});

test('owned names match loosely ("ChatGPT Plus", "canva") and are deduplicated', () => {
  const r = goal('help me write a grant proposal', ['ChatGPT Plus', 'chatgpt plus', '  ', 'Notion']);
  assert.deepStrictEqual(r.ownedTools, ['ChatGPT Plus', 'Notion']);
  assert.strictEqual(r.ownedRecommendation.toolName, 'ChatGPT');
  assert.deepStrictEqual(r.ownedNotInLibrary, ['Notion']);
  assert.strictEqual(goal('make a promo video', ['canva']).ownedRecommendation.toolName, 'Canva');
});

test('an owned tool for a different job is not offered as fitting the goal', () => {
  const r = goal('help me write a grant proposal', ['Canva']);
  assert.strictEqual(r.ownedRecommendation, null);
});

test('when the owned tool is the only fit, the reason says so', () => {
  const r = goal('help me write a grant proposal', ['ChatGPT', 'Claude']);
  assert.strictEqual(r.recommendation, null);
  assert.ok(r.ownedRecommendation);
  assert.match(r.noMatchReason, /already have is the best fit/);
});

test('the list is capped at 30 names of 60 characters', () => {
  const r = goal(LANCE, Array.from({ length: 40 }, (_, i) => `Tool ${i} ${'x'.repeat(80)}`));
  assert.strictEqual(r.ownedTools.length, 30);
  assert.ok(r.ownedTools.every((n) => n.length <= 60));
});

// ---------- owned tools, checkouts (sample-mode answers, as previews send) ----------
const SAMPLES = ['checkout_01_domain.json', 'checkout_02_trial.json', 'checkout_03_cart.json'];

test('with no owned tools, checkout results are the same as without the option', () => {
  for (const name of SAMPLES) {
    for (const founderGoal of ['', 'launch a website for my startup']) {
      const a = recommend(sample(name), lib, { founderGoal });
      const b = recommend(sample(name), lib, { founderGoal, ownedTools: [] });
      assert.deepStrictEqual(b, a, name);
      assert.deepStrictEqual(a.duplicates, []);
      assert.strictEqual(a.ownedRecommendation, null);
    }
  }
});

test('Domainly, blank goal, owns Squarespace: still no match, and a domain is not a duplicate of a website builder', () => {
  const r = recommend(sample('checkout_01_domain.json'), lib, { ownedTools: ['Squarespace'] });
  assert.strictEqual(r.matchQuality, 'no_suitable_match');
  assert.strictEqual(r.ownedRecommendation, null);
  assert.deepStrictEqual(r.duplicates, []);
});

test('Domainly with a website goal, owns Squarespace: Squarespace first as owned, Floot as the new option', () => {
  const r = recommend(sample('checkout_01_domain.json'), lib, { founderGoal: 'launch a website for my startup', ownedTools: ['Squarespace'] });
  assert.strictEqual(r.ownedRecommendation.toolName, 'Squarespace');
  assert.strictEqual(r.recommendation.toolName, 'Floot');
});

test('buying a tool the shopper already has is flagged', () => {
  const r = recommend(sample('checkout_01_domain.json'), lib, { ownedTools: ['Domainly'] });
  assert.strictEqual(r.duplicates.length, 1);
  assert.strictEqual(r.duplicates[0].kind, 'same_tool');
  assert.match(r.duplicates[0].text, /already have Domainly/);
});

test('Sparkforge, owns Floot: Floot shown as owned, the new option is another tool, verdict untouched', () => {
  const base = recommend(sample('checkout_02_trial.json'), lib);
  const r = recommend(sample('checkout_02_trial.json'), lib, { ownedTools: ['Floot'] });
  assert.strictEqual(r.ownedRecommendation.toolName, 'Floot');
  assert.notStrictEqual(r.recommendation.toolName, 'Floot');
  assert.deepStrictEqual(r.pipelineVerdict, base.pipelineVerdict);
  assert.deepStrictEqual(r.risks, base.risks);
});

test('Cartwheel (office furniture), owns Canva and Floot: nothing owned fits, nothing flagged', () => {
  const r = recommend(sample('checkout_03_cart.json'), lib, { ownedTools: ['Canva', 'Floot'] });
  assert.strictEqual(r.matchQuality, 'no_suitable_match');
  assert.strictEqual(r.ownedRecommendation, null);
  assert.deepStrictEqual(r.duplicates, []);
});

console.log(`${passed} tests passed`);
