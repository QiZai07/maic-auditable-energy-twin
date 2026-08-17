# Data Contract

The checked-in application reads the deterministic public demonstration files under `data/processed/`. Rebuilding the public snapshot never requires or reads private source material:

```bash
python -m scripts.build_public_demo_data
```

Private ingestion is a deployment concern, not a public-repository build step. Module 08 accepts client-owned data in a session-only confirmation workflow and keeps those uploads outside the checked-in dataset.

## Public output contracts

- `monthly_meter_clean.csv`: one generated row per generic meter and month.
- `db_hourly_estimated.csv`: 8,760 deterministic synthetic hourly rows.
- `hourly_monthly_reconciliation.csv`: monthly conservation checks.
- `scenario_summary.csv`: screening energy, cost, CAPEX and payback results.
- `loss_aware_metrics.csv`: dispatch comparison and battery-use indicators.
- `project_summary.json`: stable aggregate facts consumed by the applications and reports.

The regression suite fails if aggregate conservation, solver status, public model loading or the privacy boundary moves outside its accepted conditions.

## Client onboarding contract

Module 08 uses the `irene-client-data-v1` mapping record. Each table retains its source name, source field, proposed target field, source unit and confirmation status. The record remains `approvedForModel: false` until a reviewer confirms the mappings, units, quality findings and extracted facts.

Safe starting templates are provided under `data/examples/`. Client uploads are not repository inputs and are not written into the public processed snapshot.

## Client project result contract

Confirmed inputs produce the `irene-client-project-v1` contract. The record contains the client project profile, confirmation counts, coverage, reporting-period results, monthly consolidation, source-table quality and warnings. Cost, tariff, floor area and grid factor remain nullable until supported by confirmed evidence or explicit client input.

The ZIP export uses this record alongside mapping, quality, source-fingerprint and audit registers. It deliberately excludes the in-session full table rows used for calculation.
