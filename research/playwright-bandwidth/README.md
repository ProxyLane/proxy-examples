# Browser resource blocking: paired bandwidth experiment

This protocol measures browser-observed transfer on **Books to Scrape**, a public practice catalog. It is not a production anti-bot benchmark, a provider comparison, or a measurement of provider billing. Publisher: ProxyLane.

## Question and design

How much observed browser transfer changes when image, font and media requests are blocked, while the same 1,000 listing records remain intact?

- 50 catalog listing pages × 20 records, repeated three times in each arm.
- Pair arms on every page. Alternate full/lean and lean/full continuously across repetitions. Sequential execution, 300 ms after each attempt. Protocol v2 permits at most one retry per navigation, only for transport failures.
- Both arms use fresh browser contexts, block service workers, and install catch-all routing (disables browser HTTP cache in both). CSS, JavaScript and document requests remain enabled.
- Lean aborts `image`, `font` and `media` resource types. Full continues them. This is a bundle intervention; no isolated attribution to one type.
- Require 20 unique records per page with nonempty title, canonical Books to Scrape product URL, positive GBP price, availability and a rating from 1–5. Each paired result must match exactly after URL sorting.
- After load, await font readiness (maximum 5 seconds) and drain active requests (maximum 5 seconds) in both arms. Full-arm images must have loaded; fonts must not have an error status. `document.fonts.ready` waits for used fonts; declared but unused font faces may remain unloaded. Stop on invalid page, timeout, challenge, any HTTP 4xx/5xx resource, unexpected request failure, missing byte sizes or paired mismatch. Reject duplicate product URLs across pages within an arm/repetition. Partial terminal output remains marked failed. One attempt has a 60-second timeout. Transport timeouts/unexpected request failures may receive one retry; target HTTP errors, challenges, malformed/missing records, mismatches and missing byte sizes never trigger retries.
- Extract listing fields only; do not call this full product-detail enrichment. Repetitions contain the same 1,000 products and are not 3,000 independent products.

## Run

Requires Node 20+, repository `npm ci`, and installed Chromium or Google Chrome. Load the authenticated HTTP(S) proxy URL privately into `PROXY_URL`; never place its value in command arguments or checked-in files. Authenticated SOCKS is unsupported. The runner refuses execution without a proxy and has no direct fallback.

```sh
node --test research/playwright-bandwidth/core.test.mjs
# Optional: use installed Chrome
export BROWSER_CHANNEL=chrome
# Supply PROXY_URL securely in the environment before running.
node research/playwright-bandwidth/run.mjs --output /absolute/path/new-pilot --pages 1 --repeats 1
node research/playwright-bandwidth/run.mjs --output /absolute/path/new-full-run
```

Output directory must not exist (its parent must exist). Each run is independent. Do not mix pilot output with full-run evidence. A browser launch error prints only its error class, because error messages can include private proxy arguments. No proxy address, credentials, raw headers or IP records are saved.

## Outputs and measurement

- `manifest.json`: UTC times, runtime/browser versions, source SHA-256 hashes, fixed knobs, completion status.
- `attempts.jsonl`: every attempt, including failed/retried attempts, one-based `attempt_idx`, accepted status, retry decision and sanitized `net::[A-Z_]+` network reasons.
- `pages.jsonl`: final accepted or terminal page-level records, observed bytes, completed and failed request counts, intentionally blocked requests, status histogram, per-resource-type completed bytes, missing byte observations, duration and validation failures.
- `pairs.jsonl`: paired equality evidence.
- `rows.json`: all extracted records by arm, page and repetition.
- `summary.json`: arm totals across ALL attempts and observed bytes per 1,000 valid records. An accepted retry contributes its records once; failed attempts still contribute completed-request bytes.

Transfer is the sum of Playwright `request.sizes()` request/response header and body sizes **for completed requests**. It excludes unfinished/failed transfers and transport, connection, proxy and TLS overhead. Missing request sizes are counted. Intentional aborts are tracked separately from failed requests. Provider-billed bytes and cost remain null. A tariff multiplication is a modeled estimate, not a billed cost. Inspect failures and missing sizes before interpreting savings.

Report per-repetition results alongside the aggregate. Three consecutive repetitions on one site are a small descriptive sample, not proof of general performance or independent geography/network replication. Price and inventory snapshots can change; preserve timestamps and paired equality checks. Resource blocking may break richer production sites. This experiment does not test geography, proxy rotation, CAPTCHA bypass, account bans or browser-session continuity.

The static practice site is deliberately controlled and image-heavy. Results cannot be generalized to production e-commerce or used to claim that ProxyLane outperforms another provider.

## Observed target-specific browser policy

The practice target includes an HTTP jQuery script at `http://ajax.googleapis.com/ajax/libs/jquery/1.9.1/jquery.min.js` on its HTTPS page. A pilot observed Chromium blocking this exact request as `mixed-content`. Both arms preserve normal browser security: no URL rewrite, insecure-content bypass or script replacement. Only this exact URL plus exact failure reason is classified separately as `browser_policy_blocked_requests`, with the public reason stored per navigation. It is not an unexpected network failure and contributes no completed-request bytes. Other URLs or failure reasons still reject the navigation. This is part of the real page behavior measured in both arms, not proof that all declared resources executed.

## Rebuild the publication tables and charts

The analyzer checks per-page pairing, uniqueness, measurement completeness and resource-byte reconciliation before producing a result. It does not recover missing observations. Use Python 3.12 and an isolated plotting environment:

```sh
python3 -m venv .venv-plots
.venv-plots/bin/pip install -r research/playwright-bandwidth/requirements-plots.txt
.venv-plots/bin/python research/playwright-bandwidth/analyze.py \
  research/playwright-bandwidth/results/2026-09-22-v2 /absolute/path/new-analysis
```

`analysis.json`, per-repeat totals, page observations, all records, PNG/SVG charts and SHA-256 checksums are written to the new directory. Published prices are scenarios, not collected invoices. The measured HTTP-byte basis excludes browser/proxy transport overhead and compute costs. Catalogue observations come from Books to Scrape's fictional products; the repository's MIT license covers our code, not third-party trademarks or underlying catalogue content.

## Protocol v2 revision

Exploratory v1 runs stopped on transport failures and remain outside final data. Before the next dedicated run, v2 fixes a maximum of one transport retry per page/arm; no unbounded retry or success-only filtering. The optional nonsecret environment variables `PROXY_MODE` (`sticky` or `rotating`), `PROXY_GATEWAY_REGION` (two uppercase letters), and `PROXY_TTL_SECONDS` (integer up to five digits) describe operator-supplied configuration in the manifest. They do not independently verify exit location or actual session continuity.

All observed completed-request bytes from failed attempts remain in the numerator. Unfinished requests may already have transferred bytes, but their partial transfer is not measurable by this method and remains excluded. Therefore even retry-inclusive observed totals are not provider-billed traffic and can undercount real traffic. Report retry counts and failed-attempt counts next to outcomes; retain unsuccessful exploratory data separately rather than merging protocols.
