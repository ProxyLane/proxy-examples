# Independent methodology review

Review date: 2026-09-22. Reviewer: independent methodology subagent. Scope: frozen protocol v2 source, completed raw observations, numerical publication outputs and rendered charts. This is an internal independent-agent check commissioned by ProxyLane, not an external laboratory certification.

## Verdict

**Scientific and numerical checks: PASS.** The experiment supports the narrowly scoped claim of a 68.45% median reduction in browser-observed completed HTTP transfer, preserving the same 1,000 catalogue records in each arm across three repetitions on Books to Scrape, with fresh contexts and HTTP cache disabled in both arms.

**Presentation checks: PASS.** The initial transfer-by-repeat legend overlap was corrected and the regenerated PNG was independently inspected. Its legend, all six bar values, axes, date and measurement caveat are now readable. The resource-type breakdown is also readable. No unresolved numerical or presentation blocker remains within this review scope.

## Verified evidence

- Acquisition interval: 2026-09-22T12:46:41.869Z to 2026-09-22T13:17:48.114Z.
- Completed manifest: protocol 2.0; frozen run.mjs and core.mjs SHA-256 values match the current collection sources.
- 301 attempt rows, 300 accepted page navigations, 150 full/lean page pairs.
- Each repetition contains exactly 50 accepted pages and 1,000 unique product URLs per arm. Every accepted page contains 20 records.
- Independently compared all 150 full/lean pairs field for field after URL sorting: identical.
- 6,000 exported record observations represent the same 1,000 distinct catalogue products repeated across two arms and three repetitions. They are not 6,000 unique products or independent samples.
- Accepted navigations have HTTP 200 documents, no validation errors, no missing request-size measurements, and no unexpected failed requests.
- Resource-type byte sums reconcile to recorded observed totals, including the rejected attempt. Per-repetition published totals reconcile to raw attempt rows.
- Published price multiplication uses decimal GB and the stated tariff correctly. Provider-billed bytes and invoice cost remain unmeasured.
- Existing SHA256SUMS entries verified before this review file was added. The publication owner should regenerate the inventory after all presentation and review artifacts are finalized.

| Repeat | Default loading bytes | Blocked-resource bytes | Reduction |
|---|---:|---:|---:|
| 1 | 18,379,947 | 5,798,633 | 68.4513072861% |
| 2 | 18,380,066 | 5,799,086 | 68.4490469185% |
| 3 | 18,379,705 | 5,798,734 | 68.4503423749% |

Median reduction: **68.4503423749%**. Observed range: 68.4490469185% to 68.4513072861% across these three consecutive repetitions.

## Retry and missing measurement scope

The only rejected v2 attempt was lean arm, repetition 3, catalogue page 37, attempt 1. Its sanitized reason is **net::ERR_NETWORK_CHANGED**. It lasted 31,196 ms, reported one failed request and zero completed requests, and recorded zero completed-request bytes. The predeclared single retry completed successfully.

Zero captured completed-request bytes does not establish zero transferred bytes or zero cost. Partial failed transfers, transport overhead and provider accounting remain outside this browser measurement. The experiment therefore does not prove an exact invoice reduction or end-to-end acquisition cost. Earlier interrupted protocol v1 executions remain separate history and must not be spliced into the completed v2 comparison.

## Claim boundaries

- Static, fictional practice catalogue; not evidence for production anti-bot performance, geography accuracy, proxy reliability, or competitor superiority.
- Bundle intervention blocks images, fonts and media. The observed target provides evidence for the resource types actually requested, not an isolated causal estimate for every blocked type.
- Identical routing disables HTTP caching in both arms. Cold-context repeated resource loading is part of the protocol; do not describe this as the cost of a warm-cache browser session.
- Sticky mode, gateway region and TTL are operator-supplied configuration. This review does not independently certify geographic exit location or unchanged residential IP identity.
- Three consecutive repetitions are descriptive replication on one target and route, not broad network or market replication.
- Known mixed-content blocking is disclosed separately from unexpected failures. Default loading does not mean overriding browser security to load every referenced URL.
- Modelled dollar figures are tariff-scaled captured transfer, with purchase minimums disclosed. Compute, engineering time, partial failed transfers and provider billing are not measured.

## Independent verification history

Local runner suite: 10 passing tests. Analysis regression checks reject duplicate records, mismatched pairs, missing byte observations, inconsistent resource-byte totals, invalid page IDs, swapped page pairs, missing/duplicated attempt rows, mismatched manifest counters, and a missing protocol v2 attempts file. A private synthetic failed-retry fixture verified that captured retry bytes enter cost while accepted record count remains unchanged. Synthetic fixtures are not included as experimental observations.
