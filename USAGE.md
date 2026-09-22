# One request, useful records

Use Python 3.10+ and curl 8.4+ for `collect.py`, or Node 20+ and Playwright 1.62.1 for `browser.mjs`. The two clients accept the same JSON document: `{"records":[{"id":"unique-id","title":"Required value"}]}`. They keep unique non-empty string IDs/titles, reject incomplete rows and do not count a challenge page as success. Adapt the acceptance rule to your real parser before evaluating a different dataset.

1. Copy `fixture.json` to an HTTPS endpoint you control, or use a permitted endpoint with that schema. The bundled fixture contains two useful rows, one duplicate and one empty title: expected output is 2 accepted, 2 rejected. It contains synthetic demonstration records, not customer data.
2. Load connection details from your provider into your existing private environment. `.env.example` lists the names; it is not loaded automatically. Never put secrets on the command line or in a target URL.
3. For the HTTP client, set `PROXY_URL` privately and run:

```sh
python3 collect.py --target https://YOUR_PERMITTED_TARGET/fixture.json --output result.json
```

4. For the browser client, set `PROXY_SERVER` (scheme, host and explicit port without credentials), `PROXY_USERNAME`, `PROXY_PASSWORD`, and `TARGET_URL` privately, then:

```sh
npm install
npx playwright install chromium
npm run collect
```

If Google Chrome is already installed, set `BROWSER_CHANNEL=chrome` and skip the browser download. This is the locally verified browser option.

For IP-allowlist authentication, omit both username/password variables. Browser example supports HTTP(S) proxy authentication, not authenticated SOCKS. Python/curl also accepts the protocols supported by the included checker. No automatic direct fallback. TLS verification stays enabled. The browser fixture permits only its one JSON navigation, blocks subresources/redirects and closes its context; this is deliberately not a general website crawler. Use a small trusted document: browser bodies are checked after download, so its 64 KiB acceptance limit is not a hard network-transfer cap.

The scripts write private result files and refuse to overwrite existing ones. HTTP also writes a CSV of accepted records. Exit 0 means useful records; 1 means the response failed acceptance or transport; 2 means invalid input or a file/runtime problem. Zero accepted records is a failed fixture, not a zero-result SERP.

`response_body_bytes` is the response body, not the provider's billable transfer. `cost_usd` is null until reconciled with actual billing. Retries are disabled. The result proves this fixture only; it does not verify location, residential origin or reliability across targets. Review exported records before sharing. `sample-result.json` is a real run through a local authenticated test proxy, not a ProxyLane network benchmark.

For a migration, use the same target and acceptance rule with each provider, with separate output files. Compare accepted records and billed transfer; record tier, date, region and session policy separately. Stop on a target restriction and follow its permitted access method.

## Evaluate an SEO collector

Fill `seo-observations.csv` from your collector: named engine, query, expected and observed location, device, timezone-qualified time, required depth, observed depth, organic result count, status, explicit empty-result confirmation and per-attempt cost. Use exact matching location labels. `observed_depth` is the number of organic ranks inspected, not HTML size. Record a challenge as `status=challenge`. Confirm an empty result only from an explicit result page. A missing cost remains unknown, not zero.

```sh
python3 evaluate-seo.py seo-example.csv --output seo-demo.json
python3 evaluate-seo.py seo-observations.csv --output seo-result.json
```

The first command exercises four synthetic observations: 2 accepted, 2 rejected, $0.04 input cost, $0.02 per accepted observation. These costs are invented fixture inputs, not provider prices or a real search-engine test. The second requires you to fill at least one data row. All attempts contribute to cost, including rejected/duplicate observations; missing costs make the overall cost ratio unknown. The validator cannot independently prove location or collector honesty.
