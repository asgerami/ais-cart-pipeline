'use strict';
/** Build data/recommendations.json from Lance's untouched Floot export. */
const fs = require('fs');
const path = require('path');
const { normalizeRecommendations } = require('./normalize-recommendations');

const root = path.join(__dirname, '..');
const sourcePath = path.join(root, 'data', 'floot', 'aiscart_floot_recommendations.original.json');
const outputPath = path.join(root, 'data', 'recommendations.json');
const source = JSON.parse(fs.readFileSync(sourcePath, 'utf8'));
const normalized = normalizeRecommendations(source);
// Lance's first-step lines live in their own file, so the export above stays untouched.
const firstStepsPath = path.join(root, 'data', 'floot', 'first-steps.json');
const { firstSteps } = JSON.parse(fs.readFileSync(firstStepsPath, 'utf8'));
for (const id of Object.keys(firstSteps)) {
  if (!normalized.records.some((rec) => rec.id === id)) throw new Error(`first step for unknown record ${id}`);
}
for (const rec of normalized.records) {
  if (!firstSteps[rec.id]) throw new Error(`no first step for ${rec.id}`);
  rec.firstStep = firstSteps[rec.id];
}

const active = {
  source: source.source,
  sourceProjectId: source.source_project_id,
  recordCount: source.record_count,
  status: 'real-floot-editorial',
  dataStatus: source.data_status,
  pricingStatus: source.pricing_status,
  note: 'Active library generated from data/floot/aiscart_floot_recommendations.original.json. Editorial text, evidence IDs, confidence and cautions are preserved, and each record gets its first step from data/floot/first-steps.json; pricing remains unknown because Floot did not provide it.',
  recommendations: normalized.records,
};

if (active.recommendations.length !== 12) throw new Error(`expected 12 records, got ${active.recommendations.length}`);
fs.writeFileSync(outputPath, JSON.stringify(active, null, 2) + '\n');
console.log(`Wrote ${active.recommendations.length} real Floot records to ${outputPath}`);
