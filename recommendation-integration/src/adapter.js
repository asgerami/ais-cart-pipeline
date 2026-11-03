'use strict';
/**
 * AI's Cart — Recommendation Adapter (Kala's integration)
 *
 * Input : one Amir pipeline result. Accepts any of:
 *   1. full /api/analyze response  { verdict, facts, checks, ... }
 *   2. bare facts object           { merchant, line_items, ... }   (e.g. eval label / mock record)
 *   3. mock_data record            same as (2), optionally with `id`
 * Output: recommendation result (see docs/SCHEMA.md). Every number in the output
 *         is either copied from the facts, copied from a recommendation record,
 *         or computed with the arithmetic shown in `savings.basis`.
 *
 * No database, no embeddings, no external calls. Pure functions, Node >= 14.
 */

const FLAG_RISKS = {
  renewal_price_not_shown: {
    severity: 'high',
    title: 'Renewal price not shown',
    detail: 'The checkout commits you to a renewal but does not state the renewal price. Find it before paying.',
    check: 'Find the exact renewal price (screenshot or account page) before paying.',
  },
  multi_year_upfront: {
    severity: 'high',
    title: 'Multi-year payment upfront',
    detail: 'You pay several years now for something not yet validated. A shorter first term lowers the cost of changing your mind.',
    check: 'Check whether a 1-year / monthly first term exists and what it costs.',
  },
  trial_converts_to_paid: {
    severity: 'high',
    title: 'Trial converts to paid automatically',
    detail: 'The free/low-cost start becomes a paid subscription automatically. The risk is forgetting, not the trial itself.',
    check: 'Set a cancellation reminder at least 24h before the trial ends, and note the first paid amount.',
  },
  price_changes_after_intro: {
    severity: 'medium',
    title: 'Price changes after the intro period',
    detail: 'The price you see now is introductory. The ongoing price is the one that matters.',
    check: 'Find the post-intro price and judge the purchase on that number.',
  },
  text_cut_off: {
    severity: 'medium',
    title: 'Terms are cut off on screen',
    detail: 'Part of the terms could not be read from the screenshot, so something relevant may be missing.',
    check: 'Scroll / expand the full terms and re-check refund and cancellation wording.',
  },
  terms_behind_link_or_login: {
    severity: 'medium',
    title: 'Terms behind a link or login',
    detail: 'Key terms are not on this screen; they were not extracted or verified.',
    check: 'Open the linked terms before paying and confirm price, renewal and cancellation.',
  },
  totals_do_not_add_up: {
    severity: 'high',
    title: 'Totals do not add up',
    detail: 'The amounts on screen are internally inconsistent. Do not pay until the total is explained.',
    check: 'Recompute items + tax - discounts and query any difference with the merchant.',
  },
  other: {
    severity: 'low',
    title: 'Other uncertainty flagged by the pipeline',
    detail: 'The extraction flagged an uncertainty that is not categorised above.',
    check: 'Review the flagged fields in the facts before paying.',
  },
};

const { normalizeRecommendations } = require('./normalize-recommendations');

const CATEGORY_KEYWORDS = {
  video: ['video', 'edit', 'clip', 'reel', 'caption', 'subtitle', 'podcast', 'youtube', 'tiktok'],
  graphics: ['design', 'graphics', 'image', 'logo', 'figma', 'canva', 'ui', 'ux', 'mockup', 'presentation'],
  writing: ['writing', 'write', 'draft', 'document', 'docs', 'blog', 'copy', 'notes', 'notion', 'research'],
  apps: ['app', 'hosting', 'deploy', 'database', 'backend', 'auth', 'automation', 'workflow', 'builder', 'saas', 'software', 'platform', 'prototype', 'mvp'],
  websites: ['website', 'landing', 'domain', 'site', 'framer', 'wordpress', 'webflow', 'portfolio', 'squarespace'],
};

const STOPWORDS = new Set(('the a an and or for to of in on at pro plan monthly annual year years month months free trial then each until cancelled cancel settings turn off can be is are with no not shown from this that it its per via buy get started today now due total subtotal tax discount code at-cost').split(' '));

function textOf(field) {
  if (!field || typeof field !== 'object') return '';
  if (field.status === 'unknown' || field.value == null) return '';
  return String(field.value);
}
function norm(s) { return String(s || '').toLowerCase(); }
function tokens(s) {
  return norm(s).split(/[^a-z0-9.]+/).filter((t) => t.length >= 3 && !STOPWORDS.has(t) && !/^\$?[\d.,]+$/.test(t));
}
function parseMoney(fieldOrString) {
  const s = typeof fieldOrString === 'string' ? fieldOrString : textOf(fieldOrString);
  if (!s) return null;
  const m = s.replace(/,/g, '').match(/\$?\s*(\d+(?:\.\d{1,2})?)/);
  return m ? Math.round(parseFloat(m[1]) * 100) / 100 : null;
}
function money(n) { return n == null ? null : '$' + n.toFixed(2); }

/** Accept full analyze-response, bare facts, or mock record. Throws on unrecognisable input. */
function normalizeFacts(input) {
  if (!input || typeof input !== 'object') throw new Error('input must be a pipeline result object');
  const facts = input.facts && typeof input.facts === 'object' ? input.facts : input;
  if (!facts.merchant && !Array.isArray(facts.line_items)) {
    throw new Error('unrecognised input: expected a pipeline response with `facts`, or a facts object with merchant/line_items');
  }
  return {
    facts,
    verdict: input.verdict || null,
    pipelineChecks: (input.checks && input.checks.math) || null,
    sourceMode: input.mode || (input.facts ? 'unknown' : 'bare-facts'),
  };
}

function describeCheckout(facts) {
  const items = (facts.line_items || []).map((it) => ({
    name: textOf(it.name),
    term: textOf(it.term),
    lineTotal: parseMoney(it.line_total),
  }));
  const searchable = [
    textOf(facts.merchant),
    ...items.flatMap((i) => [i.name, i.term]),
    textOf(facts.other_conditions),
  ].join(' ');
  return {
    merchant: textOf(facts.merchant) || null,
    currency: textOf(facts.currency) || null,
    items,
    totalDueNow: parseMoney(facts.total_due_now),
    flags: Array.isArray(facts.uncertainty_flags) ? facts.uncertainty_flags.slice() : [],
    searchableTokens: new Set(tokens(searchable)),
    searchableText: norm(searchable),
  };
}

function inferCategories(checkout) {
  const scores = {};
  for (const [cat, words] of Object.entries(CATEGORY_KEYWORDS)) {
    scores[cat] = words.reduce((n, w) => n + (checkout.searchableText.includes(w) ? 1 : 0), 0);
  }
  return Object.entries(scores).filter(([, n]) => n > 0).sort((a, b) => b[1] - a[1]).map(([c]) => c);
}

// Directness is a coverage judgement, not just a score. A direct match must name the
// same kind of purchase in both the checkout and the recommendation's own editorial
// scope; sharing only a broad category makes it a related alternative instead.
const JOB_PATTERNS = [
  { job: 'domain_registration', label: 'domain registration', patterns: [/\bdomain\b/i, /\bregistrar\b/i, /whois/i, /\.com\b/i, /\.io\b/i, /\.ai\b/i] },
  { job: 'automation', label: 'workflow automation', patterns: [/\bautomation\b/i, /\bautomate\b/i, /\bworkflow\b/i, /\bintegration(s)?\b/i, /\bzapier\b/i, /\bzap(s)?\b/i] },
  { job: 'video_editing', label: 'video creation/editing', patterns: [/\bvideo\b/i, /\bpremiere\b/i, /\bclip\b/i, /\bediting\b/i] },
  { job: 'graphics_design', label: 'graphics/design work', patterns: [/\bgraphics?\b/i, /\bdesign\b/i, /\bphotoshop\b/i, /\bimage\b/i] },
  { job: 'writing', label: 'writing/research assistance', patterns: [/\bwriting\b/i, /\bgrammar/i, /\bcopywriting\b/i, /\bwriter\b/i] },
  // Specific: the text says the product builds MVPs or prototypes. Generic: words like "builder" or "app" alone.
  { job: 'mvp_building', label: 'building an MVP or prototype', patterns: [/\bmvps?\b/i, /\bprototypes?\b/i, /\bapp builder\b/i, /\bno-code\b/i] },
  { job: 'app_building', label: 'building an app', patterns: [/\bbuilder\b/i, /\bapps?\b/i, /\bplatform\b/i, /\bsoftware\b/i] },
  { job: 'website_building', label: 'building/launching a website', patterns: [/\bwebsite\b/i, /\blanding page\b/i, /\bweb builder\b/i, /\bsite builder\b/i] },
];

function detectJob(text) {
  const value = String(text || '');
  return JOB_PATTERNS.filter(({ patterns }) => patterns.some((pattern) => pattern.test(value)));
}

function classifyMatch(rec, checkout, founderGoal = '') {
  const checkoutJobText = checkout.searchableText;
  const goalJobs = detectJob(founderGoal);
  const purchaseJobs = detectJob(checkoutJobText);
  const genericPurchaseJobs = new Set(['app_building']);
  const specificPurchaseJobs = purchaseJobs.filter((entry) => !genericPurchaseJobs.has(entry.job));
  const goalSpecificJobs = goalJobs.filter((entry) => !genericPurchaseJobs.has(entry.job));
  const goalJobsOutsidePurchase = goalSpecificJobs.filter((entry) => !specificPurchaseJobs.some((purchase) => purchase.job === entry.job));
  // Specific purchase facts win over the goal: buying a domain to launch a website
  // remains domain registration. If the checkout only names a generic product and
  // the goal states a specific job (for example automation), that goal identifies
  // the coverage question, so an app builder is related rather than direct.
  const checkoutJobs = specificPurchaseJobs.length
    ? specificPurchaseJobs
    : (goalJobsOutsidePurchase.length ? goalJobsOutsidePurchase : purchaseJobs);
  const recJobs = detectJob([rec.toolName, rec.bestFor, rec.why, ...(rec.useCases || []), ...(rec.keywords || [])].join(' '));
  const checkoutJobIds = checkoutJobs.map((entry) => entry.job);
  const sharedJobs = recJobs.filter((entry) => checkoutJobIds.includes(entry.job));
  const sameCategory = checkout.categories.includes(rec.category);
  const missingDirect = checkoutJobs.filter((entry) => !recJobs.some((recEntry) => recEntry.job === entry.job));

  const weakGoalOnly = !specificPurchaseJobs.length && goalSpecificJobs.some((entry) => !purchaseJobs.some((purchase) => purchase.job === entry.job)) && sharedJobs.length;
  // A generic job (a word like "builder" or "app") says what kind of product it is, not what it does, so it can
  // never establish functional equivalence on its own. A direct match needs a shared specific job.
  const sharedSpecificJobs = sharedJobs.filter((entry) => !genericPurchaseJobs.has(entry.job));
  if (sharedSpecificJobs.length && sameCategory && !weakGoalOnly) {
    return {
      quality: 'direct_match',
      label: 'Direct match',
      explanation: `The checkout itself and this Floot record both concern ${sharedJobs.map((entry) => entry.label).join(', ')}.`,
      checkoutJobs: checkoutJobs.map((entry) => entry.job),
      sharedJobs: sharedJobs.map((entry) => entry.job),
      missingDirectJobs: [],
    };
  }

  if (sharedJobs.length && !sharedSpecificJobs.length && !weakGoalOnly) {
    return {
      quality: 'related_alternative',
      label: 'Related alternative — not a direct substitute',
      explanation: `Both concern ${sharedJobs.map((entry) => entry.label).join(', ')}, but the checkout does not say what this product does, so it is not claimed as a direct substitute.`,
      checkoutJobs: checkoutJobs.map((entry) => entry.job),
      sharedJobs: sharedJobs.map((entry) => entry.job),
      missingDirectJobs: [],
    };
  }

  if (weakGoalOnly) {
    return {
      quality: 'related_alternative',
      label: 'Related alternative — not a direct substitute',
      explanation: `Related through the stated goal (${goalJobs.map((entry) => entry.label).join(', ')}), but the checkout item itself does not directly identify that kind of purchase.`,
      checkoutJobs: checkoutJobs.map((entry) => entry.job),
      sharedJobs: sharedJobs.map((entry) => entry.job),
      missingDirectJobs: [],
    };
  }

  return {
    quality: 'related_alternative',
    label: 'Related alternative — not a direct substitute',
    explanation: missingDirect.length
      ? `Related guidance only: the checkout concerns ${missingDirect.map((entry) => entry.label).join(', ')}, while this record covers a neighbouring use case.`
      : 'Related guidance only: this record shares a broad category or goal with the checkout, but does not directly cover the same kind of purchase.',
    checkoutJobs: checkoutJobs.map((entry) => entry.job),
    sharedJobs: sharedJobs.map((entry) => entry.job),
    missingDirectJobs: missingDirect.map((entry) => entry.job),
  };
}

function scoreRecord(rec, checkout, founderGoal) {
  const reasons = [];
  let score = 0;
  const recText = norm([rec.toolName, rec.category, rec.bestFor, rec.why, rec.caution, rec.alternative, ...(rec.useCases || []), ...(rec.keywords || []), ...(rec.alternativesFor || [])].join(' '));
  if (checkout.categories.includes(rec.category)) {
    score += 40;
    reasons.push(`Same category as this checkout (${rec.category}).`);
  }
  const overlap = [...checkout.searchableTokens].filter((t) => recText.includes(t));
  if (overlap.length) {
    score += Math.min(30, overlap.length * 6);
    reasons.push(`Matches checkout terms: ${overlap.slice(0, 6).join(', ')}.`);
  }
  const goalTokens = tokens(founderGoal || '');
  const goalOverlap = goalTokens.filter((t) => recText.includes(t) || (rec.useCases || []).some((u) => norm(u).includes(t)));
  if (goalOverlap.length) {
    score += Math.min(20, goalOverlap.length * 5);
    reasons.push(`Fits the stated goal (${[...new Set(goalOverlap)].slice(0, 5).join(', ')}).`);
  }
  const merchant = norm(checkout.merchant);
  if (merchant && norm(rec.toolName).includes(merchant)) {
    score -= 50; // never "recommend" the tool already in the cart as its own alternative
    reasons.push('This is the tool already in the cart, so it is not an alternative.');
  }
  const matched = checkout.categories.includes(rec.category) || overlap.length > 0 || goalOverlap.length > 0;
  if (matched && rec.pricing && rec.pricing.freeTier) { score += 5; reasons.push('Has a free tier, so it can be tested before paying.'); }
  return { score, reasons, matched };
}

function buildRisks(facts, checkout, pipelineChecks) {
  const risks = [];
  for (const flag of checkout.flags) {
    const r = FLAG_RISKS[flag];
    if (r) risks.push({ source: 'pipeline_flag', flag, severity: r.severity, title: r.title, detail: r.detail, check: r.check });
  }
  const renewal = textOf(facts.renewal_terms);
  if (renewal && !/\$\s*\d/.test(renewal) && !checkout.flags.includes('renewal_price_not_shown')) {
    risks.push({ source: 'adapter_rule', flag: null, severity: 'high', title: 'Renewal mentioned without a price',
      detail: `Renewal terms say "${renewal}" but state no amount.`, check: FLAG_RISKS.renewal_price_not_shown.check });
  }
  const trial = textOf(facts.trial_terms);
  if (trial && /trial/i.test(trial) && !checkout.flags.includes('trial_converts_to_paid')) {
    risks.push({ source: 'adapter_rule', flag: null, severity: 'medium', title: 'Trial present — confirm conversion terms',
      detail: `Trial terms: "${trial}".`, check: 'Confirm the first paid amount, the conversion date, and how to cancel.' });
  }
  const cancel = facts.cancellation_terms || {};
  if ((!textOf(cancel) || cancel.status === 'unknown') && (renewal || trial)) {
    risks.push({ source: 'adapter_rule', flag: null, severity: 'medium', title: 'Cancellation terms not shown',
      detail: 'This is a recurring/trial purchase but no cancellation terms were extracted.',
      check: 'Find how to cancel and any deadline before paying.' });
  }
  if (Array.isArray(pipelineChecks)) {
    for (const c of pipelineChecks.filter((x) => x && x.ok === false)) {
      risks.push({ source: 'pipeline_math_check', flag: null, severity: 'high', title: 'Pipeline math check failed: ' + c.check,
        detail: c.detail || 'The pipeline reported this check as failed.', check: 'Resolve this discrepancy before paying.' });
    }
  }
  const order = { high: 0, medium: 1, low: 2 };
  return risks.sort((a, b) => order[a.severity] - order[b.severity]);
}

function savingsFor(rec, checkout) {
  if (!rec.pricing || rec.pricing.status === 'unknown' || (rec.pricing.monthlyUsd == null && rec.pricing.annualUsd == null)) {
    return { kind: 'pricing_unknown', amountUsd: null, basis: 'Pricing unknown: Floot did not provide pricing for this recommendation, so no price, saving, or placeholder amount is shown.' };
  }
  if (!(checkout.categories || []).includes(rec.category)) {
    return { kind: 'none_computed', amountUsd: null, basis: 'No saving computed: this alternative matched on keywords/goal, not the checkout category, so prices are not like-for-like.' };
  }
  const altAnnual = rec.pricing && typeof rec.pricing.annualUsd === 'number' ? rec.pricing.annualUsd : null;
  const altMonthly = rec.pricing && typeof rec.pricing.monthlyUsd === 'number' ? rec.pricing.monthlyUsd : null;
  const dueNow = checkout.totalDueNow;
  if (altAnnual != null && dueNow != null && altAnnual > 0 && dueNow > altAnnual && (checkout.categories || []).includes(rec.category)) {
    return { kind: 'upfront_vs_alternative_annual', amountUsd: Math.round((dueNow - altAnnual) * 100) / 100,
      basis: `${money(dueNow)} due now on this checkout vs ${money(altAnnual)}/year for ${rec.toolName} (recommendation record). Difference only — not a like-for-like total-cost claim.` };
  }
  if (altMonthly != null && altMonthly === 0) {
    return { kind: 'free_alternative', amountUsd: dueNow,
      basis: dueNow != null ? `${rec.toolName} can be tested at $0.00 before committing the ${money(dueNow)} due now here.` : `${rec.toolName} can be tested at $0.00 before committing to this purchase.` };
  }
  if (altAnnual != null && altAnnual === 0) {
    return { kind: 'free_alternative', amountUsd: dueNow,
      basis: dueNow != null ? `${rec.toolName} can be tested at $0.00 before committing the ${money(dueNow)} due now here.` : `${rec.toolName} can be tested at $0.00 before committing to this purchase.` };
  }
  return { kind: 'none_computed', amountUsd: null, basis: 'No honest saving computed: the recommendation record has no comparable price, or this checkout has no comparable amount due. No numbers were invented.' };
}

function recommend(input, recommendationLibrary, options = {}) {
  const founderGoal = options.founderGoal || input.question || '';
  const { facts, verdict, pipelineChecks, sourceMode } = normalizeFacts(input);
  const checkout = describeCheckout(facts);
  checkout.categories = inferCategories(checkout);
  const library = normalizeRecommendations(recommendationLibrary);
  const recs = library.records;

  const ranked = recs
    .map((rec) => ({ rec, ...scoreRecord(rec, checkout, founderGoal) }))
    .filter((r) => r.matched && r.score > 0)
    .map((entry) => ({ ...entry, match: classifyMatch(entry.rec, checkout, founderGoal) }))
    .sort((a, b) => {
      const rank = { direct_match: 0, related_alternative: 1 };
      return rank[a.match.quality] - rank[b.match.quality] || b.score - a.score || String(a.rec.toolName).localeCompare(String(b.rec.toolName));
    });

  const risks = buildRisks(facts, checkout, pipelineChecks);
  const top = ranked[0] || null;
  const matchQuality = top ? top.match.quality : 'no_suitable_match';
  const status = !top ? 'no_match'
    : matchQuality === 'direct_match'
      ? (risks.some((r) => r.severity === 'high') ? 'direct_match_with_risks' : 'direct_match')
      : (risks.some((r) => r.severity === 'high') ? 'related_alternative_with_risks' : 'related_alternative');

  const why = top ? [
    `${top.match.label}: ${top.match.explanation}`,
    ...top.reasons,
    ...(top.rec.why ? [`Floot editorial why: ${top.rec.why}`] : []),
    ...((top.rec.strengths || []).length && !top.rec.why ? [`Strengths: ${(top.rec.strengths || []).join('; ')}.`] : []),
    ...(top.rec.caution ? [`Floot caution: ${top.rec.caution}`] : []),
    ...((top.rec.limitations || []).length && !top.rec.caution ? [`Limitations to check: ${(top.rec.limitations || []).join('; ')}.`] : []),
  ] : ['No record in the recommendation library matched this checkout. That is a library-coverage result, not a claim that no alternative exists.'];

  const isRealFloot = library.dataStatus !== 'unknown' || recs.some((rec) => rec.dataStatus === 'real-floot-editorial');
  return {
    adapter: { name: 'ais-cart-recommendation-adapter', version: '0.3.1' },
    dataSource: {
      recommendations: options.recommendationsPath || 'provided recommendation library',
      source: library.source,
      sourceProjectId: library.sourceProjectId,
      status: isRealFloot ? 'real-floot-editorial' : 'simulated-or-unspecified',
      dataStatus: library.dataStatus,
      pricingStatus: library.pricingStatus,
      recordCount: recs.length,
    },
    inputMode: sourceMode,
    checkout: {
      merchant: checkout.merchant, currency: checkout.currency, items: checkout.items,
      totalDueNow: checkout.totalDueNow, totalDueNowText: money(checkout.totalDueNow),
      inferredCategories: checkout.categories, uncertaintyFlags: checkout.flags,
    },
    pipelineVerdict: verdict ? { decision: verdict.decision, headline: verdict.headline, confidence: verdict.confidence } : null,
    founderGoal: founderGoal || null,
    status,
    matchQuality,
    matchQualityLabel: top ? top.match.label : 'No suitable match',
    recommendation: top ? {
      id: top.rec.id, toolName: top.rec.toolName, tool: top.rec.toolName, category: top.rec.category,
      sourceCategory: top.rec.editorial ? top.rec.editorial.category : (top.rec.sourceCategory || top.rec.category),
      bestFor: top.rec.bestFor || null, why: top.rec.why || null, caution: top.rec.caution || null,
      confidence: top.rec.confidence, evidenceIds: top.rec.evidenceIds || [],
      alternative: top.rec.alternative || null, pricing: top.rec.pricing,
      strengths: top.rec.strengths, limitations: top.rec.limitations, evidence: top.rec.evidence,
      editorial: top.rec.editorial || null,
      match: top.match,
      matchScore: top.score, whyItFits: why,
      savings: savingsFor(top.rec, checkout),
    } : null,
    otherCandidates: ranked.slice(1, 4).map((r) => ({ id: r.rec.id, toolName: r.rec.toolName, category: r.rec.category, matchScore: r.score, matchQuality: r.match.quality, matchQualityLabel: r.match.label })),
    risks,
    checkBeforeBuying: [...new Set(risks.map((r) => r.check))],
    honesty: {
      simulated: isRealFloot ? [] : ['Recommendation records use the preserved simulated baseline library.'],
      unverified: [
        ...(isRealFloot ? ['Floot records are founder editorial assessments, not controlled rankings or verified live prices.'] : ['Recommendation prices are unverified snapshots.']),
        'Pricing is unknown for Floot records because the source did not provide it; no placeholder prices are used.',
        'Founder-goal fit uses explainable keyword overlap, not user research or embeddings.',
      ],
      notClaimed: ['No saving is claimed unless savings.basis shows the arithmetic.', 'A no_match result means no library record matched — not that no alternative exists anywhere.'],
    },
  };
}

module.exports = { recommend, normalizeFacts, describeCheckout, inferCategories, classifyMatch, parseMoney, FLAG_RISKS, CATEGORY_KEYWORDS };
