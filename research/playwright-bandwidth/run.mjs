import { chromium } from 'playwright';
import { mkdir, writeFile, appendFile, readFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { createHash } from 'node:crypto';
import { performance } from 'node:perf_hooks';
import { parseArgs, validateRows, sameRows, aggregate, isKnownBrowserPolicyBlock, safeNetworkReason, retryableTransport } from './core.mjs';
const require = createRequire(import.meta.url);
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
let browser; let directory; let manifest;
const pages = [];
const attempts = [];
const seen = new Map();
async function save(name, value) { await writeFile(`${directory}/${name}`, JSON.stringify(value, null, 2) + '\n'); }
try {
  const args = parseArgs(process.argv.slice(2));
  if (!process.env.PROXY_URL) throw new Error('ProxyRequired');
  const proxyUrl = new URL(process.env.PROXY_URL);
  if (!['http:', 'https:'].includes(proxyUrl.protocol)) throw new Error('UnsupportedProxyProtocol');
  const proxy = { server: `${proxyUrl.protocol}//${proxyUrl.hostname}:${proxyUrl.port || (proxyUrl.protocol === 'https:' ? 443 : 80)}`, username: decodeURIComponent(proxyUrl.username), password: decodeURIComponent(proxyUrl.password) };
  if (proxyUrl.pathname !== '/' || proxyUrl.search || proxyUrl.hash) throw new Error('InvalidProxyURL');
  directory = args.output;
  await mkdir(directory); // Deliberately refuses an existing directory.
  const pkg = JSON.parse(await readFile(require.resolve('playwright/package.json'), 'utf8'));
  manifest = { protocol: '2.0', started_at: new Date().toISOString(), status: 'running', node_version: process.version, playwright_version: pkg.version, browser_channel: process.env.BROWSER_CHANNEL || 'bundled-chromium', platform: process.platform, architecture: process.arch, target: 'https://books.toscrape.com', pages: args.pages, repeats: args.repeats, expected_records_per_page: 20, concurrency: 1, gap_ms: 300, timeout_ms: 60000, retries: 1, retry_policy: 'one retry only for transport failure; retain all attempt bytes and evidence', fresh_context_per_navigation: true, service_workers: 'block', routing_disables_cache_in_both_arms: true, lean_blocked_types: ['image', 'font', 'media'], known_browser_policy_block: { url: 'http://ajax.googleapis.com/ajax/libs/jquery/1.9.1/jquery.min.js', failure: 'mixed-content', handling: 'excluded from unexpected failures; browser security unchanged in both arms; no transfer bytes recorded' }, order: 'full/lean on even pair index; lean/full on odd pair index; index continues across repetitions', proxy_used: true, proxy_identity: 'omitted', viewport: { width: 1440, height: 900 }, locale: 'en-GB', timezone: 'UTC', billed_bytes: null };
  manifest.proxy_configuration = { mode: ['sticky', 'rotating'].includes(process.env.PROXY_MODE) ? process.env.PROXY_MODE : 'unspecified', gateway_region: /^[A-Z]{2}$/.test(process.env.PROXY_GATEWAY_REGION || '') ? process.env.PROXY_GATEWAY_REGION : 'unspecified', ttl_seconds: /^\d{1,5}$/.test(process.env.PROXY_TTL_SECONDS || '') ? Number(process.env.PROXY_TTL_SECONDS) : null, provenance: 'operator-supplied configuration; not independent verification' };
  manifest.source_sha256 = {};
  for (const file of ['run.mjs', 'core.mjs']) manifest.source_sha256[file] = createHash('sha256').update(await readFile(new URL(file, import.meta.url))).digest('hex');
  await save('manifest.json', manifest);
  browser = await chromium.launch({ headless: true, proxy, ...(process.env.BROWSER_CHANNEL ? { channel: process.env.BROWSER_CHANNEL } : {}) });
  manifest.browser_version = browser.version();
  await save('manifest.json', manifest);
  for (let repeat = 1; repeat <= args.repeats; repeat++) {
    for (let number = 1; number <= args.pages; number++) {
      const pair = [];
      const index = (repeat - 1) * args.pages + number - 1;
      for (const arm of index % 2 === 0 ? ['full', 'lean'] : ['lean', 'full']) {
       for (let attempt_idx = 1; attempt_idx <= 2; attempt_idx++) {
        const context = await browser.newContext({ serviceWorkers: 'block', viewport: manifest.viewport, locale: 'en-GB', timezoneId: 'UTC' });
        const page = await context.newPage();
        const stat = { repeat, page: number, arm, attempt_idx, accepted: false, network_failure_reasons: [], started_at: new Date().toISOString(), observed_bytes: 0, completed_requests: 0, failed_requests: 0, browser_policy_blocked_requests: 0, browser_policy_block_reasons: {}, intentionally_blocked_requests: 0, missing_sizes: 0, request_types: {}, statuses: {}, rows: [], validation_errors: [] };
        const blocked = new WeakSet(); const pending = []; const active = new Set(); let denied = false; let badStatus = false;
        page.on('request', request => active.add(request));
        await context.route('**/*', async route => {
          const request = route.request();
          if (arm === 'lean' && manifest.lean_blocked_types.includes(request.resourceType())) { blocked.add(request); stat.intentionally_blocked_requests++; await route.abort('blockedbyclient'); }
          else await route.continue();
        });
        page.on('requestfinished', request => {
          active.delete(request);
          pending.push((async () => {
            stat.completed_requests++;
            const type = request.resourceType(); stat.request_types[type] ??= { completed: 0, bytes: 0 }; stat.request_types[type].completed++;
            try {
              const s = await request.sizes();
              const bytes = s.requestBodySize + s.requestHeadersSize + s.responseBodySize + s.responseHeadersSize;
              if (!Number.isFinite(bytes) || bytes < 0) throw new Error('InvalidSizes');
              stat.observed_bytes += bytes; stat.request_types[type].bytes += bytes;
            } catch { stat.missing_sizes++; }
          })());
        });
        page.on('requestfailed', request => {
          active.delete(request);
          if (blocked.has(request)) return;
          if (isKnownBrowserPolicyBlock(request.url(), request.failure()?.errorText)) {
            stat.browser_policy_blocked_requests++;
            stat.browser_policy_block_reasons['mixed-content: legacy HTTP jQuery script'] = (stat.browser_policy_block_reasons['mixed-content: legacy HTTP jQuery script'] || 0) + 1;
          } else {
            stat.failed_requests++;
            const reason = safeNetworkReason(request.failure()?.errorText);
            if (reason) stat.network_failure_reasons.push(reason);
          }
        });
        page.on('response', response => { const status = response.status(); stat.statuses[status] = (stat.statuses[status] || 0) + 1; if ([403, 429].includes(status)) denied = true; if (status >= 400) badStatus = true; });
        const start = performance.now();
        try {
          const response = await page.goto(`https://books.toscrape.com/catalogue/page-${number}.html`, { waitUntil: 'load', timeout: 60000 });
          stat.document_status = response?.status() ?? null;
          await page.evaluate(() => Promise.race([document.fonts.ready, new Promise((_, reject) => setTimeout(() => reject(new Error('FontTimeout')), 5000))]));
          const drainUntil = performance.now() + 5000;
          while (active.size && performance.now() < drainUntil) await sleep(50);
          if (active.size) stat.validation_errors.push('unfinished_requests');
          await Promise.all(pending);
          if (arm === 'full') {
            const incomplete = await page.evaluate(() => ({ images: [...document.images].filter(image => !image.complete || image.naturalWidth === 0).length, fonts: [...document.fonts].filter(font => font.status === 'error').length }));
            stat.incomplete_resources = incomplete;
            if (incomplete.images || incomplete.fonts) stat.validation_errors.push('incomplete_full_resources');
          }
          const body = await page.locator('body').innerText({ timeout: 5000 });
          if (denied || /verify you are human|checking your browser|access denied|captcha|just a moment/i.test(body)) { stat.validation_errors.push('challenge_or_rate_limit'); }
          if (stat.document_status !== 200) stat.validation_errors.push('document_status');
          stat.rows = await page.locator('article.product_pod').evaluateAll(cards => cards.map(card => {
            const link = card.querySelector('h3 a');
            const price = card.querySelector('.price_color')?.textContent || '';
            const rating = ['One', 'Two', 'Three', 'Four', 'Five'].findIndex(word => card.querySelector('.star-rating')?.classList.contains(word)) + 1;
            return { title: link?.getAttribute('title') || '', url: link ? new URL(link.getAttribute('href'), document.baseURI).href : '', price_gbp: Number(price.replace(/[^0-9.]/g, '')), availability: (card.querySelector('.availability')?.textContent || '').replace(/\s+/g, ' ').trim(), rating };
          }));
          stat.validation_errors.push(...validateRows(stat.rows));
        } catch (error) {
          stat.validation_errors.push(error.name === 'TimeoutError' ? 'timeout' : 'navigation_or_extraction_error');
          const reason = safeNetworkReason(error.message);
          if (reason) stat.network_failure_reasons.push(reason);
        }
        stat.duration_ms = Math.round(performance.now() - start);
        await Promise.all(pending);
        await context.close();
        await Promise.all(pending);
        if (stat.failed_requests) stat.validation_errors.push('unexpected_request_failure');
        if (stat.missing_sizes) stat.validation_errors.push('missing_request_sizes');
        if (badStatus) stat.validation_errors.push('resource_http_error');
        const key = `${repeat}:${arm}`;
        const urls = seen.get(key) ?? new Set();
        for (const row of stat.rows) {
          if (urls.has(row.url)) stat.validation_errors.push('cross_page_duplicate');

        }

        if (denied && !stat.validation_errors.includes('challenge_or_rate_limit')) stat.validation_errors.push('challenge_or_rate_limit');
        stat.validation_errors = [...new Set(stat.validation_errors)];
        stat.network_failure_reasons = [...new Set(stat.network_failure_reasons)];
        stat.accepted = stat.validation_errors.length === 0;
        stat.will_retry = !stat.accepted && attempt_idx === 1 && retryableTransport(stat);
        attempts.push(stat);
        await appendFile(`${directory}/attempts.jsonl`, JSON.stringify(stat) + '\n');
        console.log(JSON.stringify({ repeat, page: number, arm, attempt_idx, accepted: stat.accepted, will_retry: stat.will_retry, records: stat.rows.length, bytes: stat.observed_bytes, errors: stat.validation_errors }));
        if (stat.will_retry) { await sleep(300); continue; }
        pages.push(stat); pair.push(stat);
        await appendFile(`${directory}/pages.jsonl`, JSON.stringify(stat) + '\n');

        if (stat.validation_errors.length) throw new Error('InvalidNavigation');
        for (const row of stat.rows) urls.add(row.url);
        seen.set(key, urls);
        await sleep(300);
        break;
       }
      }
      if (!sameRows(pair[0].rows, pair[1].rows)) {
        await appendFile(`${directory}/pairs.jsonl`, JSON.stringify({ repeat, page: number, equal: false }) + '\n');
        throw new Error('PairMismatch');
      }
      await appendFile(`${directory}/pairs.jsonl`, JSON.stringify({ repeat, page: number, equal: true }) + '\n');
    }
  }
  for (const urls of seen.values()) if (urls.size !== args.pages * 20) throw new Error('IncompletePopulation');
  manifest.status = 'complete';
} catch (error) {
  if (manifest) { manifest.status = 'failed'; manifest.error_class = error.name; }
  console.error(JSON.stringify({ status: 'failed', error_class: error.name }));
  process.exitCode = 1;
} finally {
  if (browser) await browser.close().catch(() => {});
  if (manifest) {
    manifest.finished_at = new Date().toISOString();
    manifest.attempt_count = attempts.length;
    manifest.accepted_navigation_count = attempts.filter(a => a.accepted).length;
    manifest.retry_count = attempts.filter(a => a.attempt_idx > 1).length;
    manifest.failed_attempt_count = attempts.filter(a => !a.accepted).length;
    await save('manifest.json', manifest);
    await save('summary.json', aggregate(pages, attempts));
    await save('rows.json', pages.map(({ repeat, page, arm, rows }) => ({ repeat, page, arm, rows })));
  }
}
