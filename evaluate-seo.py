#!/usr/bin/env python3
"""Validate your collector's observation log; no network requests."""
import argparse
import csv
from datetime import datetime
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path


def evaluate(rows):
    results, seen, known_cost = [], set(), Decimal('0')
    costs_complete = True
    for number, row in enumerate(rows, 1):
        row = {k: v if isinstance(v, str) else '' for k, v in row.items()}
        reason = None
        required = ['engine', 'query', 'expected_location', 'observed_location', 'device', 'observed_at', 'required_depth', 'observed_depth', 'result_count', 'status']
        if any(not row.get(k, '').strip() for k in required):
            reason = 'missing_fields'
        try:
            stamp = datetime.fromisoformat(row.get('observed_at', '').replace('Z', '+00:00'))
            required_depth, observed_depth, count = (int(row[k]) for k in ['required_depth', 'observed_depth', 'result_count'])
            if stamp.tzinfo is None or required_depth < 1 or observed_depth < 0 or count < 0:
                raise ValueError()
        except (KeyError, ValueError):
            reason = reason or 'invalid_fields'
        if not reason:
            if row['status'] != 'ok':
                reason = 'collector_failure'
            elif row['expected_location'].strip().casefold() != row['observed_location'].strip().casefold():
                reason = 'location_mismatch'
            elif count == 0 and row.get('empty_confirmed', '').lower() != 'true':
                reason = 'unconfirmed_empty'
            elif count > 0 and (observed_depth < required_depth or count < required_depth):
                reason = 'insufficient_depth'
        key = tuple(row.get(k, '') for k in ['engine', 'query', 'expected_location', 'device', 'observed_at'])
        if not reason and key in seen:
            reason = 'duplicate'
        if not reason:
            seen.add(key)
        try:
            cost = Decimal(row.get('cost_usd', ''))
            if not cost.is_finite() or cost < 0:
                raise InvalidOperation()
            known_cost += cost
        except InvalidOperation:
            costs_complete = False
        results.append({'row': number, 'accepted': reason is None, 'reason': reason})
    accepted = sum(r['accepted'] for r in results)
    return {'observations': len(rows), 'accepted_observations': accepted, 'rejected_observations': len(rows) - accepted, 'known_cost_usd': float(known_cost), 'cost_complete': costs_complete, 'cost_per_accepted_usd': float(known_cost / accepted) if accepted and costs_complete else None, 'results': results, 'scope': 'Validates your supplied fields, not engine accuracy, geography or invoices independently'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input')
    parser.add_argument('--output', default='seo-result.json')
    args = parser.parse_args()
    try:
        path = Path(args.input)
        if path.stat().st_size > 1024 * 1024:
            raise ValueError()
        with path.open(newline='') as f:
            rows = list(csv.DictReader(f))
        if not rows or len(rows) > 1000:
            raise ValueError()
        result = evaluate(rows)
        with Path(args.output).open('x') as f:
            import os
            os.chmod(args.output, 0o600)
            json.dump(result, f, indent=2)
            f.write('\n')
    except (OSError, ValueError, csv.Error):
        parser.exit(2, 'Provide a CSV of 1–1000 observations (up to 1 MiB) and an unused output path.\n')
    print(json.dumps({'accepted': result['accepted_observations'], 'rejected': result['rejected_observations']}))


if __name__ == '__main__':
    main()
