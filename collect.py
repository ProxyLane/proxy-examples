#!/usr/bin/env python3
"""One bounded HTTP request through your proxy, with JSON record validation."""
import argparse
import csv
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

spec = importlib.util.spec_from_file_location('checker', Path(__file__).with_name('proxylane-check.py'))
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


def records_from_body(body):
    try:
        data = json.loads(body)
    except (ValueError, UnicodeError):
        return [], 0
    source = data.get('records') if isinstance(data, dict) else None
    if not isinstance(source, list):
        return [], 0
    accepted = []
    seen = set()
    for row in source:
        if not isinstance(row, dict) or not all(isinstance(row.get(k), str) and row[k].strip() for k in ('id', 'title')):
            continue
        if row['id'] in seen:
            continue
        seen.add(row['id'])
        accepted.append({'id': row['id'], 'title': row['title']})
    return accepted, len(source) - len(accepted)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', required=True, help='Permitted JSON endpoint with records containing id and title')
    parser.add_argument('--output', default='result.json')
    args = parser.parse_args()
    try:
        target = checker.validate_url(args.target, {'http', 'https'}, 'target')
        proxy = checker.load_proxies(None)[0]
        checker.require_curl()
        with tempfile.TemporaryDirectory(prefix='proxylane-workload-') as tmp:
            body_path = Path(tmp) / 'body'
            command = ['curl', '--disable', '--silent', '--globoff', '--noproxy', '', '--proto', '=http,https', '--connect-timeout', '5', '--max-time', '15', '--max-filesize', '65536', '--output', str(body_path), '--write-out', checker.WRITE_OUT, '--config', '-']
            env = {k: v for k, v in os.environ.items() if k.upper() not in {'PROXY_URL', 'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'NO_PROXY'}}
            run = subprocess.run(command, input=checker.curl_config(proxy, target), text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=17, env=env, check=False)
            values = run.stdout.strip().split('\t')
            code, tunnel = int(values[0]), int(values[1])
            elapsed = round(float(values[3]) * 1000, 1)
            body = body_path.read_bytes()[:65537] if body_path.exists() else b''
            status = checker.classify(run.returncode, code, tunnel, None)
            records, rejected = records_from_body(body) if status == 'ok' and len(body) <= 65536 else ([], 0)
            if status == 'ok' and not records:
                status = 'invalid_output'
            result = {'schema_version': 1, 'client': 'curl', 'checked_at': datetime.now(timezone.utc).isoformat(), 'status': status, 'http_status': code, 'attempts': 1, 'retries': 0, 'response_body_bytes': len(body), 'elapsed_ms': elapsed, 'accepted_records': len(records), 'rejected_records': rejected, 'records': records, 'cost_usd': None, 'scope': 'One JSON response; body bytes are not provider billable traffic; no geo or residential-origin proof'}
    except (checker.InputError, ValueError, IndexError, OSError, subprocess.TimeoutExpired):
        print('Cannot complete request: check inputs, curl availability and timeout. Credentials withheld.', file=sys.stderr)
        return 2
    try:
        path = Path(args.output)
        if path.suffix != '.json' or path.exists() or path.with_suffix('.csv').exists():
            raise OSError()
        with path.open('x') as out:
            os.chmod(path, 0o600)
            json.dump(result, out, indent=2)
            out.write('\n')
        with path.with_suffix('.csv').open('x', newline='') as out:
            os.chmod(path.with_suffix('.csv'), 0o600)
            writer = csv.DictWriter(out, fieldnames=['id', 'title'])
            writer.writeheader()
            for row in records:
                writer.writerow({k: "'" + v if v.lstrip().startswith(('=', '+', '-', '@')) else v for k, v in row.items()})
    except OSError:
        print('Choose unused writable .json and .csv output paths.', file=sys.stderr)
        return 2
    print(json.dumps({'status': status, 'accepted_records': len(records)}))
    return 0 if status == 'ok' else 1


if __name__ == '__main__':
    raise SystemExit(main())
