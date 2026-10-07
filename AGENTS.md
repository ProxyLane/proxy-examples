# Repository agent guide

This public repository contains publishable ProxyLane usage examples and the
Playwright bandwidth research project.

## Working rules

- Keep every example self-contained, easy to copy, and driven by environment
  variables. Never commit proxy credentials, customer data, private endpoints,
  or workstation-specific paths.
- Do not make performance, reliability, or geographic claims that are not
  supported by the checked-in research data and methodology.
- Preserve the research scripts' refusal to overwrite existing outputs unless
  a change explicitly requires a new, reviewed output path.
- Keep language examples and their README instructions synchronized.

## Validation

Run the checks relevant to the files changed:

```text
python3 -m unittest discover -s tests -p 'test_*.py'
node --check browser.mjs
node --test research/playwright-bandwidth/core.test.mjs
node --check research/playwright-bandwidth/run.mjs
```

For analysis or plot changes, use a virtual environment, install
`research/playwright-bandwidth/requirements-plots.txt`, run the analysis tests,
and compare regenerated published outputs before committing them.
