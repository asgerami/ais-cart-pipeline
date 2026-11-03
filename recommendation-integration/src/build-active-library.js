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

const active = {
  source: source.source,
  sourceProjectId: source.source_project_id,
  recordCount: source.record_count,
  status: 'real-floot-editorial',
  dataStatus: source.data_status,
  pricingStatus: source.pricing_status,
  note: 'Active library generated from data/floot/aiscart_floot_recommendations.original.json. Editorial text, evidence IDs, confidence and cautions are preserved; pricing remains unknown because Floot did not provide it.',
  recommendations: normalized.records,
};

if (active.recommendations.length !== 12) throw new Error(`expected 12 records, got ${active.recommendations.length}`);
fs.writeFileSync(outputPath, JSON.stringify(active, null, 2) + '\n');
console.log(`Wrote ${active.recommendations.length} real Floot records to ${outputPath}`);
