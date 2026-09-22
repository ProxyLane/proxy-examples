"""Offline synthetic protocol-v2 acceptance tests. Never reads published results.
Run: python research/playwright-bandwidth/test_analysis.py
Matplotlib is required for the successful-control chart exports.
"""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ANALYZER = Path(__file__).with_name('analyze.py')


def fixture():
    records = [dict(title=f'Synthetic book {n}', url=f'https://books.toscrape.com/catalogue/synthetic-{n}/index.html', price_gbp=10 + n, availability='In stock', rating=3) for n in range(20)]
    pages = [dict(repeat=1, page=1, arm=arm, attempt_idx=1, accepted=True, will_retry=False, started_at='2026-01-01T00:00:00Z', observed_bytes=size, completed_requests=2, failed_requests=0, intentionally_blocked_requests=0, browser_policy_blocked_requests=1, missing_sizes=0, duration_ms=100, document_status=200, validation_errors=[], request_types={'document': {'completed': 2, 'bytes': size}}, rows=copy.deepcopy(records)) for arm, size in [('full', 2000), ('lean', 1000)]]
    manifest = dict(protocol='2.0', status='complete', pages=1, repeats=1, attempt_count=2, accepted_navigation_count=2, retry_count=0, failed_attempt_count=0, started_at='2026-01-01T00:00:00Z')
    return manifest, pages, copy.deepcopy(pages)


class AnalysisValidation(unittest.TestCase):
    def analyze(self, manifest, pages, attempts):
        with tempfile.TemporaryDirectory(prefix='synthetic-proxy-analysis-') as temp:
            root = Path(temp)
            source = root / 'input'
            source.mkdir()
            (source / 'manifest.json').write_text(json.dumps(manifest))
            (source / 'pages.jsonl').write_text(''.join(json.dumps(p) + '\n' for p in pages))
            if attempts is not None:
                (source / 'attempts.jsonl').write_text(''.join(json.dumps(p) + '\n' for p in attempts))
            output = root / 'output'
            result = subprocess.run([sys.executable, str(ANALYZER), str(source), str(output)], capture_output=True, text=True, timeout=45)
            analysis = json.loads((output / 'analysis.json').read_text()) if (output / 'analysis.json').exists() else None
            artifacts = {p.name for p in output.iterdir()} if output.exists() else set()
            return result, analysis, artifacts

    def rejected(self, manifest, pages, attempts):
        result, analysis, _ = self.analyze(manifest, pages, attempts)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIsNone(analysis, 'Rejected evidence must not produce a publishable analysis')

    def test_complete_synthetic_control_and_artifacts(self):
        result, analysis, artifacts = self.analyze(*fixture())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(analysis['reduction_percent_each_repeat'], [50.0])
        self.assertEqual([t['unique_records'] for t in analysis['totals']], [20, 20])
        self.assertIsNone(analysis['actual_billed_bytes'])
        self.assertIsNone(analysis['actual_billed_cost_usd'])
        self.assertTrue({'repeat-totals.csv', 'records.csv', 'attempt-observations.csv', 'transfer-by-repeat.svg', 'resource-breakdown.png', 'SHA256SUMS'} <= artifacts)

    def test_missing_entire_attempt_file(self):
        manifest, pages, _ = fixture()
        self.rejected(manifest, pages, None)

    def test_missing_attempt(self):
        manifest, pages, attempts = fixture()
        self.rejected(manifest, pages, attempts[:-1])

    def test_duplicate_attempt(self):
        manifest, pages, attempts = fixture()
        attempts.insert(0, copy.deepcopy(attempts[0]))
        self.rejected(manifest, pages, attempts)

    def test_manifest_counts_must_reconcile(self):
        for key in ['attempt_count', 'accepted_navigation_count', 'retry_count', 'failed_attempt_count']:
            with self.subTest(key=key):
                manifest, pages, attempts = fixture()
                manifest[key] += 1
                self.rejected(manifest, pages, attempts)

    def test_cross_arm_record_mismatch(self):
        manifest, pages, _ = fixture()
        pages[1]['rows'][0]['price_gbp'] += 1
        self.rejected(manifest, pages, copy.deepcopy(pages))

    def test_byte_breakdown_must_reconcile(self):
        manifest, pages, _ = fixture()
        pages[0]['request_types']['document']['bytes'] -= 1
        self.rejected(manifest, pages, copy.deepcopy(pages))

    def test_duplicate_record_even_when_both_arms_match(self):
        manifest, pages, _ = fixture()
        for page in pages:
            page['rows'][1] = copy.deepcopy(page['rows'][0])
        self.rejected(manifest, pages, copy.deepcopy(pages))

    def test_failed_retry_bytes_contribute_without_duplicate_records(self):
        manifest, pages, _ = fixture()
        failed = copy.deepcopy(pages[0])
        failed.update(accepted=False, will_retry=True, validation_errors=['timeout'], rows=[], observed_bytes=500, failed_requests=1)
        failed['request_types']['document']['bytes'] = 500
        pages[0]['attempt_idx'] = 2
        attempts = [failed, copy.deepcopy(pages[0]), copy.deepcopy(pages[1])]
        manifest.update(attempt_count=3, retry_count=1, failed_attempt_count=1)
        result, analysis, _ = self.analyze(manifest, pages, attempts)
        self.assertEqual(result.returncode, 0, result.stderr)
        full, lean = analysis['totals']
        self.assertEqual(full['observed_bytes'], 2500)
        self.assertEqual(full['accepted_attempt_bytes'], 2000)
        self.assertEqual(full['unique_records'], 20)
        self.assertEqual(full['retry_attempts'], 1)
        self.assertEqual(full['failed_requests'], 1)
        self.assertEqual(lean['observed_bytes'], 1000)
        self.assertEqual(analysis['reduction_percent_each_repeat'], [60.0])
        self.assertEqual(analysis['failed_attempt_count'], 1)
        self.assertAlmostEqual(full['modelled_usd_at_6_50'], 2500 / 1e9 * 6.5)

    def test_failed_attempt_bad_byte_breakdown_is_rejected(self):
        manifest, pages, _ = fixture()
        failed = copy.deepcopy(pages[0])
        failed.update(accepted=False, will_retry=True, validation_errors=['timeout'], observed_bytes=500, failed_requests=1)
        pages[0]['attempt_idx'] = 2
        manifest.update(attempt_count=3, retry_count=1, failed_attempt_count=1)
        self.rejected(manifest, pages, [failed, copy.deepcopy(pages[0]), copy.deepcopy(pages[1])])


if __name__ == '__main__':
    unittest.main()
