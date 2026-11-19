#!/usr/bin/env python3
"""Score the expanded live cases. Accept WAIT on incomplete trial terms."""
import argparse,json,re
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('run',type=Path);a=p.parse_args()
expected={
 'missing-renewal':{'due':'$100.00','decisions':['WAIT']},
 'paid-after-trial':{'due':'$0.00','decisions':['TRIAL','WAIT']},
 'washer-protection':{'due':'$373.17','decisions':['WAIT']},
}
results=[]
for name,label in expected.items():
 data=json.loads((a.run/(name+'.json')).read_text());facts=data.get('facts',{})
 checks=[]
 def ck(check,ok):checks.append({'check':check,'passed':bool(ok)})
 def value(key):return facts.get(key,{}).get('value')
 ck('Live mode',data.get('mode')=='live')
 ck('Amount due retained',value('total_due_now')==label['due'])
 ck('Decision respects known or missing terms',data.get('verdict',{}).get('decision') in label['decisions'])
 ck('Verdict checks pass',data.get('verdict_checks_passed') is True)
 ck('Recorded reading and verdict efforts are low',all(c.get('reasoning_effort')=='low' for c in data.get('calls',[]) if c['step'] in ('extract','verdict')))
 if name=='missing-renewal':
  ck('No renewal price invented',not re.search(r'[$£€]\s*\d',str(value('renewal_terms'))))
  ck('Missing renewal flagged','renewal_price_not_shown' in facts.get('uncertainty_flags',[]))
 elif name=='paid-after-trial':
  ck('Trial duration and paid amount retained','7' in str(value('trial_terms')) and '$25' in str(value('trial_terms')))
  ck('Monthly renewal retained','$25' in str(value('renewal_terms')) and 'month' in str(value('renewal_terms')).lower())
  ck('Cancellation deadline retained','24' in str(value('cancellation_terms')))
 else:
  ck('Protection-plan price retained',any('$69.99' in str(item.get('line_total',{}).get('value')) and '3' in str(item.get('name',{}).get('value')) for item in facts.get('line_items',[])))
  ck('No subscription invented',value('renewal_terms') is None)
 rec=json.loads((a.run/(name+'-recommendation.json')).read_text())
 ck('Recommendation preserves verdict',rec.get('pipelineVerdict',{}).get('decision')==data.get('verdict',{}).get('decision'))
 if name=='washer-protection':ck('No unrelated AI tool offered',rec.get('recommendation') is None and rec.get('ownedRecommendation') is None)
 results.append({'case':name,'passed':all(c['passed'] for c in checks),'checks':checks})
 for c in checks:print(('PASS' if c['passed'] else 'FAIL'),name,c['check'])
(a.run/'scoring.json').write_text(json.dumps(results,indent=2))
assert all(row['passed'] for row in results),'Expanded screenshot validation found failures'
print(f"{len(results)} expanded live cases, {sum(len(r['checks']) for r in results)} checks passed")
