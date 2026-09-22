import test from 'node:test';
import assert from 'node:assert/strict';
import { parseArgs, validateRows, sameRows, aggregate, isKnownBrowserPolicyBlock, retryableTransport, safeNetworkReason } from './core.mjs';
const row = n => ({ title: `Book ${n}`, url: `https://books.toscrape.com/catalogue/book-${n}/index.html`, price_gbp: 12.5, availability: 'In stock', rating: 3 });
test('bounded pilot arguments and required fresh output', () => {
  assert.deepEqual(parseArgs(['--output', 'new-run', '--pages', '1', '--repeats', '1']), { output: 'new-run', pages: 1, repeats: 1 });
  for (const args of [[], ['--output', 'x', '--pages', '51'], ['--output', 'x', '--repeats', '4'], ['--output', 'x', '--pages', '0'], ['--output', 'x', '--pages', '1.5'], ['--output', 'x', '--target', 'http://example.com']]) assert.throws(() => parseArgs(args));
});
test('validity requires twenty unique complete product records', () => {
  const rows = Array.from({ length: 20 }, (_, n) => row(n));
  assert.deepEqual(validateRows(rows), []);
  assert.ok(validateRows(rows.slice(1)).includes('record_count'));
  assert.ok(validateRows([...rows.slice(1), rows[1]]).includes('duplicate_url'));
  for (const change of [{ rating: 0 }, { price_gbp: NaN }, { title: '' }, { availability: '' }, { url: 'https://other.example/catalogue/a/index.html' }]) assert.ok(validateRows([{ ...row(0), ...change }], 1).includes('invalid_record'));
});
test('pair equality tolerates order only, rejects missing or changed content', () => {
  assert.ok(sameRows([row(1), row(2)], [row(2), row(1)]));
  assert.equal(sameRows([row(1)], [{ ...row(1), price_gbp: 13 }]), false);
  assert.equal(sameRows([row(1)], []), false);
});
test('aggregation separates browser observation from billing, invalid denominator and blocked requests', () => {
  const page = { arm: 'full', validation_errors: [], rows: Array.from({ length: 20 }, (_, n) => row(n)), observed_bytes: 100, completed_requests: 3, failed_requests: 0, intentionally_blocked_requests: 0, missing_sizes: 0, duration_ms: 10 };
  const a = aggregate([page, { ...page, validation_errors: ['timeout'], failed_requests: 1 }]);
  assert.equal(a.arms.full.records, 20);
  assert.equal(a.arms.full.observed_bytes, 200);
  assert.equal(a.arms.full.observed_bytes_per_1000_valid_records, 10000);
  assert.equal(a.arms.full.failed_requests, 1);
  assert.equal(a.billed_bytes, null);
  assert.equal(a.billed_cost, null);
});
test('repeated argument keys are rejected rather than silently changing protocol', () => {
  assert.throws(() => parseArgs(['--output', 'x', '--pages', '1', '--pages', '2']));
  assert.throws(() => parseArgs(['--output', 'x', '--repeats', '1', '--repeats', '2']));
});
test('missing-size and incomplete-resource pages never inflate the valid-record denominator', () => {
  const base = { arm: 'full', rows: [row(1)], observed_bytes: 100, completed_requests: 1, failed_requests: 0, intentionally_blocked_requests: 0, missing_sizes: 0, duration_ms: 10 };
  const result = aggregate([
    { ...base, missing_sizes: 1, validation_errors: ['missing_request_sizes'] },
    { ...base, failed_requests: 1, validation_errors: ['unexpected_request_failure'] },
    { ...base, validation_errors: ['cross_page_duplicate'] },
  ]);
  assert.equal(result.arms.full.records, 0);
  assert.equal(result.arms.full.valid_navigations, 0);
  assert.equal(result.arms.full.observed_bytes_per_1000_valid_records, null);
  assert.equal(result.arms.full.missing_sizes, 1);
});

test('known mixed-content exception is exact and never masks network errors', () => {
  const url = 'http://ajax.googleapis.com/ajax/libs/jquery/1.9.1/jquery.min.js';
  assert.equal(isKnownBrowserPolicyBlock(url, 'mixed-content'), true);
  assert.equal(isKnownBrowserPolicyBlock(url, 'net::ERR_PROXY_CONNECTION_FAILED'), false);
  assert.equal(isKnownBrowserPolicyBlock(url.replace('http:', 'https:'), 'mixed-content'), false);
  assert.equal(isKnownBrowserPolicyBlock('http://other.example/script.js', 'mixed-content'), false);
  assert.equal(isKnownBrowserPolicyBlock(url, undefined), false);
});

test('transport retry excludes target rejection, incomplete data and missing measurements', () => {
  const base = { failed_requests: 1, network_failure_reasons: ['net::ERR_CONNECTION_RESET'], validation_errors: ['unexpected_request_failure', 'incomplete_full_resources'] };
  assert.equal(retryableTransport(base), true);
  assert.equal(retryableTransport({ ...base, failed_requests: 0, network_failure_reasons: [], validation_errors: ['timeout'] }), true);
  for (const error of ['challenge_or_rate_limit', 'resource_http_error', 'missing_request_sizes', 'record_count', 'invalid_record', 'cross_page_duplicate']) assert.equal(retryableTransport({ ...base, validation_errors: [...base.validation_errors, error] }), false);
  assert.equal(retryableTransport({ failed_requests: 0, validation_errors: ['navigation_or_extraction_error'] }), false);
});
test('sanitized transport reason retains no URL or credentials', () => {
  assert.equal(safeNetworkReason('page.goto net::ERR_CONNECTION_RESET at https://secret:password@host'), 'net::ERR_CONNECTION_RESET');
  assert.equal(safeNetworkReason('password at http://example.com'), null);
});
test('all attempt bytes count while successful retried page enters denominator once', () => {
  const base = { arm: 'full', rows: Array.from({ length: 20 }, (_, n) => row(n)), observed_bytes: 100, completed_requests: 1, failed_requests: 0, intentionally_blocked_requests: 0, missing_sizes: 0, duration_ms: 10 };
  const failed = { ...base, accepted: false, validation_errors: ['timeout'], attempt_idx: 1 };
  const accepted = { ...base, accepted: true, validation_errors: [], attempt_idx: 2 };
  const result = aggregate([accepted], [failed, accepted]);
  assert.equal(result.arms.full.observed_bytes, 200);
  assert.equal(result.arms.full.records, 20);
  assert.equal(result.arms.full.valid_navigations, 1);
  assert.equal(result.arms.full.navigations, 2);
});
