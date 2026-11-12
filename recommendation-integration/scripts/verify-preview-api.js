'use strict';
/** Local proof: run api/recommend.js as the serverless handler without deploying. */
const fs = require('fs');
const path = require('path');

const recommendationRoot = path.join(__dirname, '..');
const repoRoot = path.join(recommendationRoot, '..');
const handlerFile = path.join(repoRoot, 'api', 'recommend.js');
const fourCases = [
  ['checkout_01_domain_run1.json', '', 'Domainly / generic question'],
  ['checkout_01_domain_run1.json', 'launch a website for my startup', 'Domainly / website goal'],
  ['checkout_02_trial_run1.json', '', 'Sparkforge / generic question'],
  ['checkout_03_cart_run1.json', '', 'Cartwheel / generic question'],
];

async function invoke(handler, body) {
  const request = { method: 'POST', body, headers: {} };
  const headers = {};
  let statusCode = 200;
  let output;
  const response = {
    setHeader(name, value) { headers[name] = value; },
    status(code) { statusCode = code; return this; },
    json(payload) { output = payload; return payload; },
    end(payload) { output = payload; return payload; },
  };
  await handler(request, response);
  return { statusCode, headers, output };
}

(async () => {
  process.chdir(repoRoot);
  delete require.cache[handlerFile];
  const handler = require(handlerFile);
  const rows = [];
  for (const [sample, shopperGoal, label] of fourCases) {
    const live = JSON.parse(fs.readFileSync(path.join(recommendationRoot, 'samples', 'live', sample), 'utf8'));
    const verdictBefore = live.verdict.decision;
    const response = await invoke(handler, { pipeline: live, shopperGoal });
    if (response.statusCode !== 200) throw new Error(`${label}: HTTP ${response.statusCode} ${JSON.stringify(response.output)}`);
    const output = response.output;
    if (Object.hasOwn(output, 'pricing') || Object.hasOwn(output, 'savings') ||
        (output.recommendation && (Object.hasOwn(output.recommendation, 'pricing') || Object.hasOwn(output.recommendation, 'savings')))) {
      throw new Error(`${label}: public response leaked pricing/savings`);
    }
    rows.push({
      label,
      question: live.question,
      shopperGoal: shopperGoal || null,
      goalFallback: output.goalFallback,
      pipelineVerdict: verdictBefore,
      adapterVerdictEcho: output.pipelineVerdict && output.pipelineVerdict.decision,
      verdictUnchanged: verdictBefore === (output.pipelineVerdict && output.pipelineVerdict.decision),
      status: output.status,
      matchQuality: output.matchQuality,
      matchQualityLabel: output.matchQualityLabel,
      tool: output.recommendation && output.recommendation.toolName,
      explanation: output.recommendation ? output.recommendation.match.explanation : null,
    });
  }
  const outPath = process.argv[2];
  if (outPath) { fs.mkdirSync(path.dirname(path.resolve(outPath)), { recursive: true }); fs.writeFileSync(outPath, JSON.stringify({ checkedAt: new Date().toISOString(), api: 'api/recommend.js (local serverless invocation)', rows }, null, 2) + '\n'); }
  for (const row of rows) console.log(JSON.stringify(row));
})();
