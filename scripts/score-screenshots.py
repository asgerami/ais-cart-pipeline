#!/usr/bin/env python3
"""Score saved live screenshot responses against the frozen fixture expectations."""
import argparse, json
from pathlib import Path

parser=argparse.ArgumentParser()
parser.add_argument('run',type=Path)
args=parser.parse_args()
expected=json.loads((Path(__file__).resolve().parent.parent/'eval/journeys/screenshots/expected.json').read_text())
results=[]
for name,label in expected.items():
    path=args.run/(name+'.json')
    if not path.exists():
        continue
    data=json.loads(path.read_text())
    facts=data.get('facts',{})
    checks=[]
    def check(title,ok):
        checks.append({'check':title,'passed':bool(ok)})
    def value(key): return facts.get(key,{}).get('value')
    check('Mode is live',data.get('mode')=='live')
    check('Total due matches the screenshot',value('total_due_now')==label['total_due_now'])
    if 'renewal_price' in label:
        renewal=str(value('renewal_terms'))
        check('Renewal price and interval retained',label['renewal_price'] in renewal and label['renewal_interval'] in renewal and '14' in renewal)
    if label.get('renewal_terms','not_specified') is None:
        check('No renewal terms invented',value('renewal_terms') is None and facts.get('renewal_terms',{}).get('status')=='unknown')
    math=data.get('checks',{}).get('math',[])
    if 'math_ok' in label:
        check('Math check detects the expected condition',bool(math) and (all(c['ok'] for c in math)==label['math_ok']))
    if 'decision' in label:
        check('Decision matches expected boundary',data.get('verdict',{}).get('decision')==label['decision'])
    if name=='wrong-total':
        check('Flagged image received a second review',data.get('review',{}).get('ran') is True)
    check('Verdict guardrails pass',data.get('verdict_checks_passed') is True)
    recommendation=json.loads((args.run/(name+'-recommendation.json')).read_text())
    check('Recommendations preserve the shown verdict',recommendation.get('pipelineVerdict',{}).get('decision')==data.get('verdict',{}).get('decision'))
    results.append({'case':name,'checks':checks,'passed':all(c['passed'] for c in checks)})
    for c in checks: print(('PASS' if c['passed'] else 'FAIL'),name,c['check'])
(args.run/'scoring.json').write_text(json.dumps(results,indent=2))
assert len(results)==len(expected),'Some screenshot cases have not completed'
assert all(r['passed'] for r in results),'Screenshot validation found failures'
print(f'{len(results)} live screenshot cases passed')
