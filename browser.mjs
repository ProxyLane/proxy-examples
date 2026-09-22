import { chromium } from 'playwright';
import { writeFile } from 'node:fs/promises';

let browser, context;
const result = { schema_version: 1, client: 'playwright', checked_at: new Date().toISOString(), status: 'input_error', http_status: null, attempts: 0, retries: 0, response_body_bytes: null, accepted_records: 0, rejected_records: 0, records: [], cost_usd: null, scope: 'One JSON document through a browser context; no geo or residential-origin proof' };
let output = process.env.OUTPUT_FILE || 'browser-result.json';
try {
    const proxy = new URL(process.env.PROXY_SERVER);
    const target = new URL(process.env.TARGET_URL);
    if (!['http:', 'https:'].includes(proxy.protocol) || !proxy.port || proxy.username || proxy.password || proxy.pathname !== '/' || proxy.search || proxy.hash) throw new Error('invalid_input');
    if (!['http:', 'https:'].includes(target.protocol) || target.username || target.password || target.hash) throw new Error('invalid_input');
    if (Boolean(process.env.PROXY_USERNAME) !== Boolean(process.env.PROXY_PASSWORD)) throw new Error('invalid_input');
    if (process.env.BROWSER_CHANNEL && process.env.BROWSER_CHANNEL !== 'chrome') throw new Error('invalid_input');
    browser = await chromium.launch({ channel: process.env.BROWSER_CHANNEL || undefined, proxy: { server: proxy.origin, username: process.env.PROXY_USERNAME, password: process.env.PROXY_PASSWORD }, args: ['--proxy-bypass-list=<-loopback>'], timeout: 15000 });
    context = await browser.newContext({ serviceWorkers: 'block', acceptDownloads: false });
    // This JSON fixture needs one document only; block subresources and redirects.
    await context.route('**/*', route => route.request().url() === target.href && route.request().isNavigationRequest() ? route.continue() : route.abort());
    const page = await context.newPage();
    result.attempts = 1;
    const response = await page.goto(target.href, { timeout: 15000, waitUntil: 'domcontentloaded' });
    result.http_status = response?.status() ?? null;
    if (result.http_status === 407) result.status = 'proxy_auth_required';
    else if (!response?.ok()) result.status = 'http_error';
    else {
        const body = await response.body();
        result.response_body_bytes = body.length;
        if (body.length > 65536) result.status = 'body_limit';
        else {
            let data;
            try { data = JSON.parse(body.toString('utf8')); } catch { data = null; }
            const rows = Array.isArray(data?.records) ? data.records : [];
            const seen = new Set();
            for (const row of rows) {
                if (!row || !['id', 'title'].every(k => typeof row[k] === 'string' && row[k].trim()) || seen.has(row.id)) continue;
                seen.add(row.id);
                result.records.push({ id: row.id, title: row.title });
            }
            result.accepted_records = result.records.length;
            result.rejected_records = rows.length - result.records.length;
            result.status = result.accepted_records ? 'ok' : 'invalid_output';
        }
    }
} catch (error) {
    // Classify locally; never print the exception, URL or credentials.
    const message = String(error?.message || '');
    result.status = /ERR_INVALID_AUTH_CREDENTIALS|ERR_PROXY_AUTH|407/.test(message) ? 'proxy_auth_required' : /Timeout/.test(error?.name || '') ? 'timeout' : result.attempts ? 'transport_failed' : 'input_or_browser_error';
} finally {
    await context?.close().catch(() => {});
    await browser?.close().catch(() => {});
}
try {
    await writeFile(output, JSON.stringify(result, null, 2) + '\n', { flag: 'wx', mode: 0o600 });
    console.log(JSON.stringify({ status: result.status, accepted_records: result.accepted_records }));
    process.exitCode = result.status === 'ok' ? 0 : 1;
} catch {
    console.error('Choose an unused writable OUTPUT_FILE.');
    process.exitCode = 2;
}
