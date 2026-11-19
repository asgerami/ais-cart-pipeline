"""Connected HTTP journeys. Offline sample responses test wiring, not model accuracy.
Run: python3 tests/test_journeys.py (requires Node.js).
"""
import base64
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.request
import urllib.error

ROOT = Path(__file__).resolve().parent.parent

def run():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        port = s.getsockname()[1]
    env = {**os.environ, 'MOCK': '1', 'PORT': str(port), 'QUIET': '1',
           'SERVICE_TOKEN': 'journey-test-only', 'RATE_LIMIT_PER_HOUR': '0'}
    env.pop('MODEL_API_KEY', None)
    proc = subprocess.Popen([sys.executable, 'server.py'], cwd=ROOT, env=env, stdout=subprocess.DEVNULL)
    base = f'http://127.0.0.1:{port}'

    def request(path, data=None, auth=True):
        headers = {'Content-Type': 'application/json'}
        if auth:
            headers['Authorization'] = 'Bearer journey-test-only'
        req = urllib.request.Request(base + path, headers=headers,
                                     data=json.dumps(data).encode() if data is not None else None)
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.load(r)

    try:
        for _ in range(100):
            try:
                request('/api/health')
                break
            except OSError:
                time.sleep(.05)
        else:
            raise AssertionError('Local server did not start')
        assert 'Canva' in request('/api/recommend')['tools']
        cases = json.loads((ROOT / 'eval/journeys/cases.json').read_text())
        for case in cases:
            mode, owned = case['mode'], case['ownedTools']
            pipeline = None
            if mode == 'screenshot':
                image = base64.b64encode((ROOT / f"eval/samples/{case['sample']}.png").read_bytes()).decode()
                pipeline = request('/api/analyze', {'image': image})
                body = {'pipeline': pipeline, 'shopperGoal': case.get('goal', ''), 'ownedTools': owned}
            elif mode == 'description':
                body = {'mode': mode, 'description': case['description'], 'shopperGoal': case.get('goal', ''), 'ownedTools': owned}
            else:
                body = {'mode': 'goal', 'goal': case['goal'], 'ownedTools': owned}
                if mode == 'spark2':
                    read = request('/api/goal', {'goal': case['goal'], 'version': 2, 'ownedTools': owned})['interpretation']
                    body['picks'] = {'version': 2, 'decision': read['decision'],
                                     'ownedRecordId': read['owned_record_id'], 'ownedFirstStep': read['owned_first_step'],
                                     'newRecordId': read['new_record_id'], 'newToolAdds': read['new_tool_adds'],
                                     'question': read['question'], 'goalSummary': read['goal_summary'], 'reason': read['reason']}
            result = request('/api/recommend', body)
            exp = case['expected']
            for field, key in [('owned', 'ownedRecommendation'), ('recommendation', 'recommendation')]:
                if field in exp:
                    assert (result[key] or {}).get('toolName') == exp[field], (case['id'], key, result)
            if pipeline:
                assert result['pipelineVerdict'] == {k: pipeline['verdict'].get(k) for k in ('decision', 'headline', 'confidence')}, case['id']
                assert result['pipelineVerdict']['decision'] == exp['verdict'], case['id']
            else:
                assert result['pipelineVerdict'] is None, case['id']
            if mode == 'description':
                assert result['inputMode'] == 'description' and result['purchaseVerified'] is False
                assert result['evidenceSource'] == 'user_description'
                assert result['description'] == case['description']
            if exp.get('duplicate'):
                assert result['duplicates'], case['id']
            if 'unknown' in exp:
                assert exp['unknown'] in result['ownedNotInLibrary'], case['id']
            if 'noNewPurchase' in exp:
                assert result['noNewPurchase'] == exp['noNewPurchase'], case['id']
            print('PASS', case['id'])
        # Real auth barrier stays in place for paid model routes.
        try:
            request('/api/goal', {'goal': 'make a video'}, auth=False)
            raise AssertionError('Missing token was accepted')
        except urllib.error.HTTPError as e:
            assert e.code == 401
        for text in ['', 'x' * 2001]:
            try:
                request('/api/recommend', {'mode': 'description', 'description': text})
                raise AssertionError('Invalid description was accepted')
            except urllib.error.HTTPError as e:
                assert e.code == 400
        print(f'{len(cases)} connected journeys + authentication and validation checks passed (sample mode).')
    finally:
        proc.terminate()
        proc.wait(timeout=5)

if __name__ == '__main__':
    run()
