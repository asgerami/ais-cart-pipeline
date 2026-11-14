'use strict';
/**
 * Goal-first with Muse Spark's picks (from /api/goal). Spark chooses library records; the adapter applies the
 * owned-tool step exactly as it does for keyword matching.
 * Run: node tests/spark-goal.test.js
 */
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const { recommend } = require('../src/adapter');

const lib = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'data', 'recommendations.json'), 'utf8'));
const MAILING = 'People visit my site, but hardly anyone ever joins my mailing list.';
const NEWSLETTER = 'My homepage gets visitors, but hardly anyone signs up for my newsletter.';
const websitePicks = { decision: 'match', recordIds: ['website-floot', 'website-squarespace'], question: null,
  goalSummary: 'Turn visitors into subscribers.', reason: 'The sign-up form is on the website.' };
const spark = (goal, goalPicks, ownedTools = ['Squarespace']) => recommend(null, lib, { goalOnly: true, founderGoal: goal, ownedTools, goalPicks });

let passed = 0;
function test(name, fn) { fn(); passed++; console.log('ok -', name); }

test('without picks, goal mode is keyword matching as before', () => {
  const r = recommend(null, lib, { goalOnly: true, founderGoal: MAILING, ownedTools: ['Squarespace'] });
  assert.strictEqual(r.matcher, 'keyword');
  assert.strictEqual(r.goalReading, null);
});

test("Spark's website picks put the owned Squarespace first, whatever order Spark gave", () => {
  const r = spark(MAILING, websitePicks);
  assert.strictEqual(r.matcher, 'spark');
  assert.strictEqual(r.ownedRecommendation.toolName, 'Squarespace');
  assert.match(r.ownedRecommendation.firstStep, /sign-up form/);
  assert.strictEqual(r.recommendation.toolName, 'Floot');
  assert.match(r.recommendation.match.explanation, /Muse Spark read your goal as/);
  assert.strictEqual(r.goalReading.summary, 'Turn visitors into subscribers.');
});

test('the newsletter phrasing keyword matching misses works with the same picks', () => {
  assert.strictEqual(recommend(null, lib, { goalOnly: true, founderGoal: NEWSLETTER, ownedTools: ['Squarespace'] }).ownedRecommendation, null);
  assert.strictEqual(spark(NEWSLETTER, websitePicks).ownedRecommendation.toolName, 'Squarespace');
});

test('"none" gives the plain no-match answer and no tools', () => {
  const r = spark('I need to file my small business taxes before the deadline.', { decision: 'none', recordIds: [], reason: 'No tax tool.' });
  assert.strictEqual(r.recommendation, null);
  assert.strictEqual(r.ownedRecommendation, null);
  assert.strictEqual(r.matchQuality, 'no_suitable_match');
  assert.match(r.noMatchReason, /library has no tool for this goal/);
  assert.strictEqual(r.clarifyingQuestion, null);
});

test('"ask" returns one question, no tools and no no-match message', () => {
  const r = spark('I want to grow my business.', { decision: 'ask', recordIds: ['website-floot'], question: 'What do you want more of first?' });
  assert.strictEqual(r.clarifyingQuestion, 'What do you want more of first?');
  assert.strictEqual(r.recommendation, null);
  assert.strictEqual(r.ownedRecommendation, null);
  assert.strictEqual(r.noMatchReason, null);
});

test('picks are held to the library: unknown ids dropped, at most 3, no duplicates', () => {
  const r = spark(MAILING, { decision: 'match', recordIds: ['made-up', 'website-floot', 'website-floot', 'mvp-base44', 'mvp-replit', 'writing-claude'] }, []);
  assert.deepStrictEqual([r.recommendation.id, ...r.otherCandidates.map((c) => c.id)], ['website-floot', 'mvp-base44', 'mvp-replit']);
});

test('a "match" with no valid ids, or an "ask" with no question, becomes "none"', () => {
  assert.strictEqual(spark(MAILING, { decision: 'match', recordIds: ['made-up'] }).matchQuality, 'no_suitable_match');
  const r = spark(MAILING, { decision: 'ask', question: '   ' });
  assert.strictEqual(r.clarifyingQuestion, null);
  assert.match(r.noMatchReason, /library has no tool/);
});

test('picks are ignored for screenshot checks', () => {
  const sample = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'samples', 'sample-mode', 'checkout_01_domain.json'), 'utf8'));
  const a = recommend(sample, lib, {});
  const b = recommend(sample, lib, { goalPicks: websitePicks });
  assert.deepStrictEqual(b, a);
});

console.log(`${passed} tests passed`);
