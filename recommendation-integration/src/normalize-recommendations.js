'use strict';
/**
 * Normalizes either supported library shape into the adapter's internal shape.
 * - Real Floot editorial records: preserve id/category/tool/bestFor/why/caution/evidenceIds/confidence verbatim.
 * - Simulated adapter records: preserve the richer pricing/evidence structure used by the baseline.
 * Pricing is never inferred: Floot supplies none, so Floot pricing stays explicitly unknown.
 */
const CATEGORY_MAP = {
  video: 'video',
  'photos & graphics': 'graphics',
  graphics: 'graphics',
  'writing & research': 'writing',
  writing: 'writing',
  'apps & mvps': 'apps',
  apps: 'apps',
  websites: 'websites',
  website: 'websites',
};

function tokensFor(record) {
  const categoryHints = {
    video: ['video', 'visual', 'voice', 'narration', 'captions', 'promotional'],
    graphics: ['graphics', 'photos', 'image', 'design', 'layout', 'social'],
    writing: ['writing', 'research', 'draft', 'editing', 'drafting', 'assistant'],
    apps: ['app', 'mvp', 'prototype', 'full-stack', 'database', 'server', 'workflow'],
    websites: ['website', 'site', 'web', 'launch', 'business', 'organization'],
  };
  return categoryHints[record.category] || [];
}

function normalizeRecord(record) {
  if (!record || typeof record !== 'object') throw new Error('recommendation record must be an object');

  if (record.editorial && record.toolName) {
    return {
      ...record,
      sourceCategory: record.sourceCategory || record.editorial.category || record.category,
      evidenceIds: Array.isArray(record.evidenceIds) ? record.evidenceIds.slice() : [],
      alternativesFor: Array.isArray(record.alternativesFor) ? record.alternativesFor.slice() : [],
      dataStatus: record.dataStatus || 'real-floot-editorial',
    };
  }

  if (record.tool) {
    const sourceCategory = String(record.category || '');
    const category = CATEGORY_MAP[sourceCategory.toLowerCase()];
    if (!category) throw new Error(`unsupported Floot category: ${sourceCategory}`);
    const normalized = {
      id: record.id,
      sourceId: record.id,
      category,
      sourceCategory,
      toolName: record.tool,
      tool: record.tool,
      bestFor: record.bestFor || '',
      why: record.why || '',
      caution: record.caution || '',
      evidenceIds: Array.isArray(record.evidenceIds) ? record.evidenceIds.slice() : [],
      confidence: record.confidence || 'Unknown',
      alternative: record.alternative || '',
      useCases: [record.bestFor || ''],
      keywords: tokensFor({ category }),
      strengths: record.why ? [record.why] : [],
      limitations: record.caution ? [record.caution] : [],
      evidence: Array.isArray(record.evidenceIds) ? record.evidenceIds.slice() : [],
      alternativesFor: record.alternative ? [record.alternative] : [],
      pricing: {
        status: 'unknown',
        model: 'unknown',
        monthlyUsd: null,
        annualUsd: null,
        freeTier: null,
        notes: 'Pricing was not provided in the Floot source; do not infer.',
      },
      dataStatus: 'real-floot-editorial',
    };
    normalized.editorial = {
      id: record.id,
      category: sourceCategory,
      tool: record.tool,
      bestFor: record.bestFor,
      why: record.why,
      caution: record.caution,
      evidenceIds: normalized.evidenceIds,
      confidence: record.confidence,
      alternative: record.alternative,
    };
    return normalized;
  }

  if (record.toolName) {
    return {
      ...record,
      evidenceIds: Array.isArray(record.evidenceIds) ? record.evidenceIds.slice() : [],
      alternativesFor: Array.isArray(record.alternativesFor) ? record.alternativesFor.slice() : [],
      editorial: null,
      dataStatus: record.dataStatus || 'simulated',
    };
  }

  throw new Error('recommendation record has neither Floot `tool` nor adapter `toolName`');
}

function normalizeRecommendations(input) {
  if (!input || typeof input !== 'object') throw new Error('recommendation library must be an object or array');
  const records = Array.isArray(input) ? input : (input.records || input.recommendations);
  if (!Array.isArray(records)) throw new Error('recommendation library must contain `records` or `recommendations`');
  const normalized = records.map(normalizeRecord);
  return {
    source: input.source || 'recommendation library',
    sourceProjectId: input.source_project_id || input.sourceProjectId || null,
    dataStatus: input.data_status || input.dataStatus || 'unknown',
    pricingStatus: input.pricing_status || input.pricingStatus || 'not specified',
    count: normalized.length,
    records: normalized,
    recommendations: normalized,
  };
}

module.exports = { normalizeRecommendations, normalizeRecord };
