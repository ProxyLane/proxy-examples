export function parseArgs(args) {
  const out = { pages: 50, repeats: 3 };
  const seen = new Set();
  for (let i = 0; i < args.length; i += 2) {
    const key = args[i]; const value = args[i + 1];
    if (!['--output', '--pages', '--repeats'].includes(key) || value === undefined) throw new Error('InvalidArguments');
    const name = key.slice(2);
    if (seen.has(name)) throw new Error('DuplicateArgument');
    seen.add(name);
    out[name] = name === 'output' ? value : Number(value);
  }
  if (!out.output || !Number.isInteger(out.pages) || out.pages < 1 || out.pages > 50 || !Number.isInteger(out.repeats) || out.repeats < 1 || out.repeats > 3) throw new Error('InvalidArguments');
  return out;
}
export function validateRows(rows, expected = 20) {
  const errors = [];
  if (rows.length !== expected) errors.push('record_count');
  if (new Set(rows.map(r => r.url)).size !== rows.length) errors.push('duplicate_url');
  for (const row of rows) {
    let url; try { url = new URL(row.url); } catch {}
    if (!row.title?.trim() || !url || url.origin !== 'https://books.toscrape.com' || !/^\/catalogue\/.+\/index\.html$/.test(url.pathname) || !Number.isFinite(row.price_gbp) || row.price_gbp <= 0 || !row.availability?.trim() || !Number.isInteger(row.rating) || row.rating < 1 || row.rating > 5) errors.push('invalid_record');
  }
  return [...new Set(errors)];
}
export function sameRows(a, b) {
  const sort = rows => [...rows].sort((x, y) => x.url.localeCompare(y.url));
  return JSON.stringify(sort(a)) === JSON.stringify(sort(b));
}
export function aggregate(pages, attempts = pages) {
  const arms = {};
  for (const p of attempts) {
    const a = arms[p.arm] ??= { navigations: 0, valid_navigations: 0, records: 0, observed_bytes: 0, completed_requests: 0, failed_requests: 0, browser_policy_blocked_requests: 0, intentionally_blocked_requests: 0, missing_sizes: 0, duration_ms: 0 };
    a.navigations++; a.valid_navigations += p.validation_errors.length === 0 && p.accepted !== false ? 1 : 0;
    a.records += p.validation_errors.length === 0 && p.accepted !== false ? p.rows.length : 0;
    for (const k of ['observed_bytes', 'completed_requests', 'failed_requests', 'browser_policy_blocked_requests', 'intentionally_blocked_requests', 'missing_sizes', 'duration_ms']) a[k] += p[k] ?? 0;
  }
  for (const a of Object.values(arms)) a.observed_bytes_per_1000_valid_records = a.records ? a.observed_bytes / a.records * 1000 : null;
  return { arms, billed_bytes: null, billed_cost: null, byte_measurement: 'Playwright request.sizes: request/response headers + bodies, completed requests only; failed transfers and transport overhead excluded' };
}

export function isKnownBrowserPolicyBlock(url, failure) {
  return url === 'http://ajax.googleapis.com/ajax/libs/jquery/1.9.1/jquery.min.js' && failure === 'mixed-content';
}

export function safeNetworkReason(message) {
  return String(message ?? '').match(/\bnet::[A-Z_]+\b/)?.[0] ?? null;
}
export function retryableTransport(stat) {
  const allowed = new Set(['timeout', 'unfinished_requests', 'unexpected_request_failure', 'incomplete_full_resources', 'navigation_or_extraction_error']);
  const transport = stat.failed_requests > 0 || stat.validation_errors.includes('timeout') || stat.validation_errors.includes('unfinished_requests') || stat.network_failure_reasons?.length > 0;
  return transport && stat.validation_errors.length > 0 && stat.validation_errors.every(error => allowed.has(error));
}
