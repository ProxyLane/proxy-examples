<p align="center">
  <a href="https://proxylane.dev"><img src="assets/proxylane.png" alt="ProxyLane — Your next request, on the right route" width="680"></a>
</p>

<h1 align="center">ProxyLane examples</h1>

<p align="center">Python, curl and Playwright examples for turning a proxy request into useful records</p>

<p align="center">
  <a href="https://github.com/ProxyLane/proxy-examples/actions/workflows/tests.yml"><img src="https://github.com/ProxyLane/proxy-examples/actions/workflows/tests.yml/badge.svg" alt="Example tests"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-28705b" alt="MIT license"></a>
</p>

<p align="center">
  <a href="https://proxylane.dev/register?utm_source=github&amp;utm_medium=repository&amp;utm_campaign=proxy-examples"><strong>Get started with ProxyLane</strong></a> ·
  <a href="https://proxylane.dev/pricing">Pricing</a> ·
  <a href="https://github.com/ProxyLane/skills">Agent setup skill</a>
</p>

## Inspect it, run it, verify it

- **Published by [ProxyLane](https://github.com/ProxyLane).** Source code and setup instructions live together in this public repository.
- **[Automated tests](https://github.com/ProxyLane/proxy-examples/actions/workflows/tests.yml).** Authentication, rejected responses and SEO validation run against local fixtures on every push. No paid proxy traffic is needed.
- **Credentials stay out of the repository.** Examples use environment variables and keep credentials out of command-line arguments and logs.
- **Reproducible sample results.** The included fixture has four rows: two accepted and two rejected. These demonstrate the code, not network performance.

Use your ProxyLane connection details with these examples. Keep the same scripts and acceptance rules when comparing providers. The examples also work with compatible proxy services.

## Pick an example

| Goal | Start here | Result |
| --- | --- | --- |
| Collect a JSON document through a proxy | [Python + curl](#python--curl) | Accepted records in JSON and CSV |
| Use a proxy in a browser | [Playwright](#playwright) | Validated records in JSON |
| Check your SEO collector output | [SEO observations](#seo-observations) | Accepted observations and cost summary |
| Compare providers on the same job | [Migration worksheet](#migration-worksheet) | A CSV for your own measurements |

## Try the validator without a proxy

Requires Python 3.10+. No account or network requests needed.

```sh
git clone https://github.com/ProxyLane/proxy-examples.git
cd proxy-examples
python3 evaluate-seo.py seo-example.csv --output seo-demo.json
```

Expected: **4 observations, 2 accepted, 2 rejected**. The fixture contains invented costs to demonstrate the calculation. It is not a provider benchmark.

## Connect ProxyLane

1. [Create your ProxyLane account](https://proxylane.dev/register?utm_source=github&utm_medium=repository&utm_campaign=proxy-examples).
2. Obtain an active proxy connection and copy its server, port and credentials from your dashboard. Registration alone does not supply traffic.
3. Use the prompts below to load credentials into your shell. They are not saved in this repository. `.env.example` documents the variable names; scripts do not load it automatically.

Use Bash for these prompts. Paste credentials only at the hidden prompts, not into commands or Git files.

## Python + curl

Requires Python 3.10+ and curl 8.4+. From the repository directory:

```bash
read -r -s -p 'Proxy URL (scheme://user:password@host:port): ' PROXY_URL; printf '\n'
export PROXY_URL
python3 collect.py \
  --target https://raw.githubusercontent.com/ProxyLane/proxy-examples/main/fixture.json \
  --output result.json
unset PROXY_URL
```

Percent-encode special characters in the proxy URL username and password. The script sends credentials to curl through stdin, not command-line arguments.

The included JSON fixture has four rows: **2 accepted and 2 rejected**. Inspect `result.json` and `result.csv`. Replace the target with your own permitted JSON endpoint and adapt the acceptance rule to its schema.

[Read the scraping guide](https://proxylane.dev/proxies-for-web-scraping) · [View Python source](collect.py)

## Playwright

Requires Node 20+ and the pinned Playwright dependency.

```bash
npm ci
npx playwright install chromium
read -r -p 'Proxy server (scheme://host:port): ' PROXY_SERVER
read -r -s -p 'Proxy username: ' PROXY_USERNAME; printf '\n'
read -r -s -p 'Proxy password: ' PROXY_PASSWORD; printf '\n'
export PROXY_SERVER PROXY_USERNAME PROXY_PASSWORD
export TARGET_URL=https://raw.githubusercontent.com/ProxyLane/proxy-examples/main/fixture.json
npm run collect
unset PROXY_SERVER PROXY_USERNAME PROXY_PASSWORD TARGET_URL
```

Inspect `browser-result.json`: expected **2 accepted, 2 rejected**. For an installed Google Chrome, set `BROWSER_CHANNEL=chrome` and skip the browser download. For IP allowlisting, leave both credential prompts empty.

This example reads one JSON document through a browser. It does not scrape arbitrary websites; it blocks redirects and subresources. HTTP(S) proxy authentication is supported; authenticated SOCKS is not.

[Read the Playwright guide](https://proxylane.dev/blog/playwright-proxy) · [View browser source](browser.mjs)

## SEO observations

Fill [seo-observations.csv](seo-observations.csv) with observations from your collector, then run:

```sh
python3 evaluate-seo.py seo-observations.csv --output seo-result.json
```

Checks include location matching, search depth, challenges and duplicates. A missing cost stays unknown. The validator checks supplied observations; it does not fetch search results or independently verify geography.

[Read the SEO monitoring guide](https://proxylane.dev/blog/proxies-for-seo-monitoring) · [View validator](evaluate-seo.py)

## Migration worksheet

Use [migration-sheet.csv](migration-sheet.csv) to compare providers with the same target, region, session policy and acceptance rule. Record accepted records and actual billed traffic. Run the collector separately with each provider and use different output filenames.

[Compare Bright Data alternatives](https://proxylane.dev/alternatives/bright-data)

## What a successful example proves

A successful run proves that this fixture passed your proxy connection and acceptance rule. Response bytes are not provider-billed traffic. Samples were produced with a local test proxy, not the ProxyLane network. No benchmark, geographic coverage or reliability claim is implied.

Outputs refuse overwrites. Choose a new filename for another run. Use permitted targets and keep credentials and real records private. See [usage details and exit codes](USAGE.md).

## Tests

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
```

Tests use a local authenticated proxy and synthetic records; no paid proxy traffic is required.

## License

MIT. Built by [ProxyLane](https://proxylane.dev).
