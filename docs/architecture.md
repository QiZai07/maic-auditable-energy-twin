# Technical Architecture

**Team:** EnerGen AI
**Project:** Irene
**Track:** T1 — AI for Clean Energy

Validated on a Ningbo reference case; designed for configurable deployment in Malaysia, pending local pilot validation.

## System flow

```mermaid
flowchart LR
    K["Client files or read-only system exports"] --> L["Session intake and schema mapping"]
    L --> M["Quality, unit and readiness checks"]
    M --> N["Human confirmation gate"]
    N --> P["Client project consolidation"]
    P --> Q["Cost, carbon and EUI results"]
    Q --> R["Audit-ready delivery pack"]
    N --> D
    K -. "Authorised PDF/image only" .-> O["Optional document recognition"]
    O --> N
    A["Private source evidence"] --> B["Normalization and quality checks"]
    B --> C["Public processed snapshot"]
    C --> D["Monthly-constrained hourly model"]
    D --> E["Efficiency, PV and storage engines"]
    E --> F["Audited result files"]
    F --> G["Streamlit application"]
    F --> H["Next.js application on Vercel"]
    I["Deterministic domain tools"] --> G
    I --> H
    J["Optional server-side Responses API"] --> G
    J --> H
```

## Components

| Layer | Implementation | Responsibility |
| --- | --- | --- |
| Data preparation | Python, pandas | Normalize evidence, detect meter anomalies and assign evidence classes |
| Temporal model | scikit-learn candidate plus transparent calendar baseline | Select a normalized reference shape through a time-based holdout gate |
| Reconciliation | Python | Constrain public hourly estimates to approved aggregate monthly building and PV totals |
| Efficiency screening | Deterministic engineering rules | Calculate HVAC, lighting, operations and combined P10/P50/P90 cases |
| Storage dispatch | SciPy linear programming | Compare future loss-aware dispatch with the rule-based comparator |
| Analysis tools | Python and TypeScript implementations | Answer project questions with traceable inputs and recalculations |
| Local interface | Streamlit | Explore evidence, scenarios, charts and the analysis engine |
| Hosted interface | Next.js on Vercel | Provide the public competition experience and server API route |
| Optional orchestration | OpenAI Responses API | Select project tools and compose an answer; never supplies project values |
| Client intake | Python and browser TypeScript | Parse structured data, documents and BIM/CAD without persisting raw uploads |
| Admission control | Mapping record and reviewer confirmation | Keep unreviewed fields and facts outside the client-specific model |
| Client project analysis | Deterministic Python and TypeScript implementations | Consolidate confirmed tables, resolve register deltas, label inputs and calculate reporting-period energy, cost, carbon and EUI |
| Client delivery pack | In-memory ZIP export | Provide mappings, quality, results, source fingerprints and audit events without raw uploads |
| Optional document recognition | Server-side Responses API | Extract strict PDF/image facts after per-file consent with `store: false` |

The model is a language and orchestration layer rather than the project calculation engine. Irene supplies approved evidence, deterministic tools, evidence classes, approval gates, local fallback and the auditable output chain. This is the practical difference from a general-purpose ChatGPT conversation.

## Compatibility and migration

Irene acts as a governed analytics layer beside the client's BMS, EMS, metering, ERP, PV and document systems. The public prototype implements file intake and read-only export onboarding. It maps source fields, units, time zones and meter hierarchies into a canonical data contract while retaining the original source fingerprint and confirmation record.

Production connectivity is configured per client through a read-only API, database view, SFTP transfer or on-site gateway. A controlled migration uses six gates: inventory → mapping → historical backfill → reconciliation → shadow run → approved cutover. Incremental synchronisation and rollback checkpoints allow Irene and the original system to run in parallel until the client accepts the results. The repository does not claim that every vendor protocol is already implemented.

## Model-selection gate

The gradient-boosting candidate is evaluated against a weekday/weekend-hour calendar prior on a time-based holdout set. The candidate is rejected when it does not improve the transparent baseline. In the included run, the calendar prior is selected with a normalized shape MAE of 14.36%.

This validation concerns reference-profile shape only. It is not evidence of case-building hourly accuracy.

## Runtime boundaries

- Streamlit can run entirely offline from the files in this repository.
- The web client also includes the same deterministic local analysis engine.
- Optional model calls occur only from server code. The deployment secret is never bundled into client JavaScript or returned by the status route.
- Agent mode sends questions, recent user questions and deterministic tool summaries; raw client files and unconfirmed rows are not attached.
- OpenAI API data is not used for training by default. Standard abuse-monitoring logs may be retained for up to 30 days; `store: false` is not the same as Zero Data Retention.
- If provider access is unavailable, the interface automatically returns to local analysis.
- Client-file parsing is session-only by default; optional recognition accepts authorised PDF/image content only.
- Only confirmed files and included tables reach client-project calculations; short coverage is not silently annualised.
- Client delivery packs exclude raw uploads and raw table rows.
- Native DWG requires a verified conversion route and is never presented as parsed when that route is unavailable.
- Neither interface connects to or controls a building management system.
- File intake and read-only exports are implemented; live API, SQL, SFTP and gateway connectors are client-specific integration work.

## Deployment and commercial layers

| Layer | Customer outcome | Commercial form |
| --- | --- | --- |
| File-based diagnosis | Confirmed baseline, auditable report and action shortlist | One-off diagnosis fee |
| Calibrated pilot | Temporary metering, model calibration and savings verification | Implementation and M&V service fee |
| Portfolio service | Governed multi-site analytics and benchmarking | Annual subscription |

Target customers are commercial buildings, campuses, industrial parks and energy service companies (ESCOs). The pilot sequence is file audit → temporary metering → calibration → savings verification → multi-site scale.
