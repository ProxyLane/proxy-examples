import base64
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

KIT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('seo', KIT / 'evaluate-seo.py')
seo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(seo)


class FixtureProxy(BaseHTTPRequestHandler):
    def do_GET(self):
        self.server.seen.append(self.path)
        valid = self.headers.get('Proxy-Authorization') == 'Basic ' + base64.b64encode(b'fixture:fixture-secret').decode()
        code = 200 if valid else 407
        body = (KIT / 'fixture.json').read_bytes() if valid else b'proxy auth required'
        if self.path.endswith('/challenge') and valid:
            body = b'<html>Complete a challenge</html>'
        self.send_response(code)
        if not valid:
            self.send_header('Proxy-Authenticate', 'Basic realm="fixture"')
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_):
        pass


class WorkloadKitTest(unittest.TestCase):
    def setUp(self):
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), FixtureProxy)
        self.server.seen = []
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.temp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def run_client(self, secret='fixture-secret', target='http://fixture.invalid/records'):
        env = dict(os.environ, PROXY_URL=f'http://fixture:{secret}@127.0.0.1:{self.server.server_port}', NO_PROXY='*')
        output = Path(self.temp.name) / 'result.json'
        run = subprocess.run([sys.executable, str(KIT / 'collect.py'), '--target', target, '--output', str(output)], env=env, capture_output=True, text=True)
        self.assertNotIn(secret, run.stdout + run.stderr)
        return run, json.loads(output.read_text())

    def test_extracts_unique_complete_records_through_proxy_even_with_no_proxy_set(self):
        run, result = self.run_client()
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(result['accepted_records'], 2)
        self.assertEqual(result['rejected_records'], 2)
        self.assertEqual([r['id'] for r in result['records']], ['fixture-001', 'fixture-002'])
        self.assertEqual(self.server.seen, ['http://fixture.invalid/records'])
        self.assertIsNone(result['cost_usd'])

    def test_reports_auth_failure_without_fabricating_records(self):
        run, result = self.run_client(secret='wrong-private-value')
        self.assertEqual(run.returncode, 1)
        self.assertEqual(result['status'], 'proxy_auth_required')
        self.assertEqual(result['records'], [])

    def test_rejects_success_status_with_challenge_body(self):
        run, result = self.run_client(target='http://fixture.invalid/challenge')
        self.assertEqual(run.returncode, 1)
        self.assertEqual(result['status'], 'invalid_output')

    def test_seo_validator_rejects_wrong_location_and_challenge_and_accounts_for_all_costs(self):
        import csv
        with (KIT / 'seo-example.csv').open() as f:
            result = seo.evaluate(list(csv.DictReader(f)))
        self.assertEqual(result['accepted_observations'], 2)
        self.assertEqual(result['known_cost_usd'], 0.04)
        self.assertEqual(result['cost_per_accepted_usd'], 0.02)
        self.assertEqual([r['reason'] for r in result['results']], [None, 'collector_failure', 'location_mismatch', None])

    def test_seo_missing_cost_and_duplicate_do_not_inflate_acceptance(self):
        import csv
        with (KIT / 'seo-example.csv').open() as f:
            row = next(csv.DictReader(f))
        row['cost_usd'] = ''
        result = seo.evaluate([row, row])
        self.assertEqual(result['accepted_observations'], 1)
        self.assertEqual(result['results'][1]['reason'], 'duplicate')
        self.assertFalse(result['cost_complete'])
        self.assertIsNone(result['cost_per_accepted_usd'])


if __name__ == '__main__':
    unittest.main()
