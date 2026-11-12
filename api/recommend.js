'use strict';
const fs = require('fs');
const path = require('path');
const { recommend } = require('../recommendation-integration/src/adapter');

const libraryPath = path.join(process.cwd(), 'recommendation-integration', 'data', 'recommendations.json');
const library = JSON.parse(fs.readFileSync(libraryPath, 'utf8'));

function publicRecommendation(result) {
  const recommendation = result.recommendation
    ? {
        id: result.recommendation.id,
        toolName: result.recommendation.toolName,
        category: result.recommendation.category,
        sourceCategory: result.recommendation.sourceCategory,
        bestFor: result.recommendation.bestFor,
        why: result.recommendation.why,
        caution: result.recommendation.caution,
        confidence: result.recommendation.confidence,
        evidenceIds: result.recommendation.evidenceIds,
        alternative: result.recommendation.alternative,
        match: result.recommendation.match,
      }
    : null;

  return {
    adapter: result.adapter,
    dataSource: {
      source: result.dataSource.source,
      status: result.dataSource.status,
      dataStatus: result.dataSource.dataStatus,
      recordCount: result.dataSource.recordCount,
    },
    status: result.status,
    matchQuality: result.matchQuality,
    matchQualityLabel: result.matchQualityLabel,
    recommendation,
    otherCandidates: result.otherCandidates.map((candidate) => ({
      id: candidate.id,
      toolName: candidate.toolName,
      category: candidate.category,
      matchQuality: candidate.matchQuality,
      matchQualityLabel: candidate.matchQualityLabel,
    })),
    risks: result.risks,
    checkBeforeBuying: result.checkBeforeBuying,
    pipelineVerdict: result.pipelineVerdict,
  };
}

module.exports = async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', process.env.ALLOW_ORIGIN || '*');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-Service-Token');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');

  if (req.method === 'OPTIONS') return res.status(204).end();
  if (req.method !== 'POST') {
    return res.status(405).json({ error: { code: 'method_not_allowed', message: 'Use POST /api/recommend.' } });
  }

  try {
    const body = typeof req.body === 'string' ? JSON.parse(req.body || '{}') : (req.body || {});
    const pipeline = body.pipeline || body.analysis || body;
    const shopperGoal = typeof body.shopperGoal === 'string'
      ? body.shopperGoal
      : (typeof body.founderGoal === 'string' ? body.founderGoal : '');
    const question = (typeof pipeline.question === 'string' && pipeline.question.trim())
      ? pipeline.question
      : 'Should I complete this purchase?';
    const founderGoal = shopperGoal.trim() || question;
    const result = recommend(pipeline, library, { founderGoal });
    return res.status(200).json({
      ...publicRecommendation(result),
      shopperGoal: shopperGoal.trim() || null,
      goalFallback: shopperGoal.trim() ? 'shopper_goal' : 'existing_question',
      analysisQuestion: question,
    });
  } catch (error) {
    return res.status(400).json({ error: { code: 'bad_request', message: String(error.message || error) } });
  }
};
