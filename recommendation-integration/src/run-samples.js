'use strict';
/** Run the 3 pipeline samples against a recommendation file and optionally write JSON outputs. */
const fs = require('fs');
const path = require('path');
const { recommend } = require('./adapter');

const root = path.join(__dirname, '..');
const goals = {
  'checkout_01_domain.json': 'launch a website for my startup',
  'checkout_02_trial.json': 'automate my workflow',
  'checkout_03_cart.json': 'buy office equipment',
};

function runSamples(recommendations, outputDir) {
  const recs = typeof recommendations === 'string'
    ? JSON.parse(fs.readFileSync(recommendations, 'utf8'))
    : recommendations;
  const outputs = [];
  for (const file of Object.keys(goals).sort()) {
    const input = JSON.parse(fs.readFileSync(path.join(root, 'samples', file), 'utf8'));
    const result = recommend(input, recs, { founderGoal: goals[file] });
    outputs.push(result);
    if (outputDir) {
      fs.mkdirSync(outputDir, { recursive: true });
      fs.writeFileSync(path.join(outputDir, file.replace('.json', '.result.json')), JSON.stringify(result, null, 2) + '\n');
    }
  }
  return outputs;
}

if (require.main === module) {
  const recommendationsPath = process.argv[2] || path.join(root, 'data', 'recommendations.json');
  const outputDir = process.argv[3] ? path.resolve(process.argv[3]) : null;
  const outputs = runSamples(recommendationsPath, outputDir);
  for (const result of outputs) {
    console.log(JSON.stringify({
      merchant: result.checkout.merchant,
      status: result.status,
      matchQuality: result.matchQuality,
      recommendation: result.recommendation && result.recommendation.toolName,
      evidenceIds: result.recommendation && result.recommendation.evidenceIds,
      risks: result.risks.map((risk) => risk.title),
      pricing: result.recommendation && result.recommendation.pricing,
    }));
  }
}

module.exports = { runSamples, goals };
