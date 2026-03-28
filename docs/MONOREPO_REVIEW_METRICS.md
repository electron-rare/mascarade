# Monorepo Review Metrics (3-6 Months)

## Objective

Verify periodically if monorepo remains the best model for core/api/web.

## Review Cadence

- Monthly quick review.
- Formal decision review every 3 to 6 months.

## Metrics

1. CI lead time
- Median CI duration on PRs.
- P95 CI duration on PRs.

2. Cross-stack frequency
- Percentage of PRs touching 2+ zones among core, api, web.
- Percentage of hotfixes requiring synchronized cross-zone changes.

3. Compatibility incidents
- Number of incidents caused by API/UI mismatch.
- Number of rollbacks caused by cross-zone integration regressions.

4. Delivery friction
- Median PR open-to-merge time.
- Median review cycles per PR.

## Decision Heuristics

Keep monorepo if most are true:
- Cross-stack ratio remains meaningful.
- Compatibility incidents remain low or decrease.
- CI durations remain acceptable with path-based optimization.

Re-evaluate split if most are true:
- Teams work independently with decoupled release cadence.
- Cross-stack ratio remains low over time.
- Access/compliance constraints require repo-level separation.

## Data Sources

- GitHub Actions runtimes.
- Pull request history (changed files, merge timing).
- Incident log and postmortems.