#!/usr/bin/env python3
"""Run fresh screenshots against deployed live mode. Credentials are read hidden, never saved.
Results under eval/runs/ are untracked; publish only reviewed, non-sensitive findings.
"""
import argparse, base64, datetime, getpass, http.cookiejar, json, time
from pathlib import Path
import urllib.request, urllib.error

root=Path(__file__).resolve().parent.parent
args=argparse.ArgumentParser()
args.add_argument('--url',required=True)
args.add_argument('--ad-image',type=Path)
args.add_argument('--expanded', action='store_true', help='Use the domain and trial samples instead of generated fixtures')
args.add_argument('--washer-image',type=Path,help='Optional private protection-plan screenshot')
opt=args.parse_args()
credentials=json.loads(getpass.getpass('Validation credentials (JSON, hidden): '))
token,share=credentials['token'],credentials.get('share','')
base=opt.url.rstrip('/')
opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
if share:
    with opener.open(base+'/?_vercel_share='+share,timeout=30) as r: r.read()

def request(path,body=None):
    headers={'Content-Type':'application/json','Authorization':'Bearer '+token}
    req=urllib.request.Request(base+path,headers=headers,data=json.dumps(body).encode() if body is not None else None)
    try:
        with opener.open(req,timeout=290) as r:
            return r.status,json.load(r)
    except urllib.error.HTTPError as e:
        try: value=json.load(e)
        except Exception: value={'error':{'message':'Non-JSON error'}}
        return e.code,value

code,health=request('/api/health')
assert code==200 and health.get('mode')=='live', 'Live health check failed'
out=root/'eval/runs'/('screenshots_'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
out.mkdir(parents=True)
(out/'health.json').write_text(json.dumps(health,indent=2))
cases=[('clear-renewal',root/'eval/journeys/screenshots/clear-renewal.png'),('wrong-total',root/'eval/journeys/screenshots/wrong-total.png')]
if opt.expanded:
    cases=[('missing-renewal',root/'eval/samples/checkout_01_domain.png'),('paid-after-trial',root/'eval/samples/checkout_02_trial.png')]
if opt.ad_image: cases.append(('heycatch-ad',opt.ad_image))
if opt.washer_image: cases.append(('washer-protection',opt.washer_image))
summary=[]
for name,path in cases:
    started=time.monotonic()
    code,data=request('/api/analyze',{'image':base64.b64encode(path.read_bytes()).decode(),'question':'Should I complete this purchase?','review':'auto'})
    (out/(name+'.json')).write_text(json.dumps(data,indent=2))
    facts=data.get('facts',{})
    row={'case':name,'http':code,'seconds':round(time.monotonic()-started,1),'mode':data.get('mode'),
         'decision':data.get('verdict',{}).get('decision'),'headline':data.get('verdict',{}).get('headline'),
         'due':facts.get('total_due_now'),'renewal':facts.get('renewal_terms'),
         'checks_passed':data.get('verdict_checks_passed'),'review_ran':data.get('review',{}).get('ran'),
         'math':data.get('checks',{}).get('math'),'calls':data.get('calls'), 'error':data.get('error')}
    print(json.dumps(row),flush=True)
    summary.append(row)
    if code==200:
        rec_code,rec=request('/api/recommend',{'pipeline':data,'shopperGoal':('Wash small clothes loads using a sink connection' if name=='washer-protection' else ''),'ownedTools':['Canva','ElevenLabs']})
        (out/(name+'-recommendation.json')).write_text(json.dumps(rec,indent=2))
        assert rec_code==200
        assert rec.get('pipelineVerdict',{}).get('decision')==data.get('verdict',{}).get('decision')
(out/'summary.json').write_text(json.dumps(summary,indent=2))
print('RESULTS '+str(out),flush=True)
