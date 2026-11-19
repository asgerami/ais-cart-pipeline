'use strict';
const { recommend } = require('../recommendation-integration/src/adapter');
const library = require('../recommendation-integration/data/recommendations.json');

const TOOL_NAMES = [...new Set((library.recommendations || []).map((rec) => rec.toolName || rec.tool).filter(Boolean))].sort();

function publicRec(rec) {
  return rec
    ? {
        id: rec.id,
        toolName: rec.toolName,
        category: rec.category,
        sourceCategory: rec.sourceCategory,
        bestFor: rec.bestFor,
        why: rec.why,
        caution: rec.caution,
        firstStep: rec.firstStep || null,
        sparkFirstStep: rec.sparkFirstStep || null,
        sparkAdds: rec.sparkAdds || null,
        confidence: rec.confidence,
        evidenceIds: rec.evidenceIds,
        alternative: rec.alternative,
        match: rec.match,
        owned: Boolean(rec.owned),
      }
    : null;
}

function publicRecommendation(result) {
  const recommendation = publicRec(result.recommendation);

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
    noMatchReason: result.noMatchReason || null,
    inputMode: result.inputMode,
    recommendation,
    ownedTools: result.ownedTools,
    ownedRecommendation: publicRec(result.ownedRecommendation),
    ownedNotInLibrary: result.ownedNotInLibrary,
    duplicates: result.duplicates,
    goalCategories: result.goalCategories,
    matcher: result.matcher,
    noNewPurchase: result.noNewPurchase,
    clarifyingQuestion: result.clarifyingQuestion,
    goalReading: result.goalReading,
    otherCandidates: result.otherCandidates.map((candidate) => ({
      id: candidate.id,
      toolName: candidate.toolName,
      category: candidate.category,
      matchQuality: candidate.matchQuality,
      matchQualityLabel: candidate.matchQualityLabel,
      owned: Boolean(candidate.owned),
    })),
    risks: result.risks,
    checkBeforeBuying: result.checkBeforeBuying,
    pipelineVerdict: result.pipelineVerdict,
  };
}

module.exports = async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', process.env.ALLOW_ORIGIN || '*');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-Service-Token');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');

  if (req.method === 'OPTIONS') return res.status(204).end();
  // GET lists the tools in the library, for the page's "tools you already have" suggestions.
  if (req.method === 'GET') return res.status(200).json({ tools: TOOL_NAMES });
  if (req.method !== 'POST') {
    return res.status(405).json({ error: { code: 'method_not_allowed', message: 'Use POST /api/recommend.' } });
  }

  try {
    const body = typeof req.body === 'string' ? JSON.parse(req.body || '{}') : (req.body || {});
    const ownedTools = Array.isArray(body.ownedTools) ? body.ownedTools : [];
    // A description is shopper testimony, never an extracted checkout or a purchase approval.
    if (body.mode === 'description') {
      const description = typeof body.description === 'string' ? body.description.trim() : '';
      const goal = typeof body.shopperGoal === 'string' ? body.shopperGoal.trim() : '';
      if (!description || description.length > 2000 || goal.length > 500) {
        return res.status(400).json({ error: { code: 'bad_request', message: 'Describe the purchase in 1–2000 characters; keep the goal under 500.' } });
      }
      const field = { status: 'inferred', value: description, evidence: 'User-supplied description; not verified against a checkout.' };
      const result = recommend({ mode: 'description', facts: {
        merchant: { status: 'unknown', value: null, evidence: '' },
        line_items: [{ name: field }], uncertainty_flags: [],
      } }, library, { founderGoal: goal, ownedTools });
      return res.status(200).json({ ...publicRecommendation(result), inputMode: 'description',
        description, shopperGoal: goal || null, evidenceSource: 'user_description',
        purchaseVerified: false, pipelineVerdict: null,
        verificationNote: 'Based on what you typed. Price, renewal, cancellation and advertised results are unverified. Add a checkout screenshot before deciding to pay.' });
    }
    // Goal-first: no screenshot yet, only what the shopper is trying to do.
    if (body.mode === 'goal') {
      const goal = typeof body.goal === 'string' ? body.goal.trim() : '';
      if (!goal) {
        return res.status(400).json({ error: { code: 'bad_request', message: 'Say what you are trying to do first.' } });
      }
      const goalPicks = body.picks && typeof body.picks === 'object' ? body.picks : null;
      const result = recommend(null, library, { goalOnly: true, founderGoal: goal.slice(0, 500), ownedTools, goalPicks });
      return res.status(200).json({ ...publicRecommendation(result), shopperGoal: goal.slice(0, 500), goalFallback: 'shopper_goal' });
    }
    const pipeline = body.pipeline || body.analysis || body;
    const shopperGoal = typeof body.shopperGoal === 'string'
      ? body.shopperGoal
      : (typeof body.founderGoal === 'string' ? body.founderGoal : '');
    const question = (typeof pipeline.question === 'string' && pipeline.question.trim())
      ? pipeline.question
      : 'Should I complete this purchase?';
    const founderGoal = shopperGoal.trim() || question;
    const result = recommend(pipeline, library, { founderGoal, ownedTools });
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
