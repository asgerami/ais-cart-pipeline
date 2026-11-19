'use strict';
const assert = require('node:assert/strict');
const handler = require('../../api/recommend');
async function description(goal) {
  return new Promise(resolve => handler({method: 'POST', body: {
    mode: 'description', description: 'Canva video editing subscription.', shopperGoal: goal, ownedTools: ['Canva'],
  }}, {setHeader() {}, status(code) { this.code = code; return this; }, json(body) { assert.equal(this.code, 200); resolve(body); }}));
}
(async () => {
  for (const goal of ['make a short promo video', 'make a short promo video without narration']) {
    const result = await description(goal);
    assert.equal(result.ownedRecommendation.toolName, 'Canva');
    assert.equal(result.ownedRecommendation.match.quality, 'direct_match');
    assert.match(result.ownedRecommendation.match.explanation, /purchase description/);
    assert.equal(result.recommendation.toolName, 'ElevenLabs');
    assert.equal(result.recommendation.match.quality, 'related_alternative');
    assert.equal(result.recommendation.match.optionalCondition, 'Only if you need AI narration');
    assert.doesNotMatch(result.recommendation.match.explanation, /checkout/);
    const names = result.otherCandidates.map(r => r.toolName.toLowerCase());
    assert.equal(names.length, new Set(names).size);
    assert.ok(!names.includes('canva') && !names.includes('elevenlabs'));
    assert.equal(result.pipelineVerdict, null);
  }
  const requested = await description('make a short promo video with AI narration');
  assert.equal(requested.recommendation.match.optionalCondition, null);
  assert.match(requested.recommendation.match.explanation, /goal asks for narration/);
  assert.equal(requested.recommendation.match.quality, 'related_alternative');
  const domain = await new Promise(resolve => handler({method:'POST',body:{mode:'description',description:'Domainly domain registration'}},
    {setHeader(){},status(){return this;},json:resolve}));
  assert.match(domain.noMatchReason, /purchase description/);
  assert.doesNotMatch(domain.noMatchReason, /checkout/);
  console.log('PASS narration is conditional, requested speech is adjacent, description provenance, unique related tools');
})().catch(err => { console.error(err); process.exitCode = 1; });
