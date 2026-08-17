# Auditable Building Energy Digital Twin

**Team:** EnerGen AI
**Project:** Irene
**Track:** T1 — AI for Clean Energy

Competition repository for the MAIC Nexus Challenge 2026. The project turns limited building evidence—monthly meters, weather, PV records and design information—into a traceable decision model for efficiency, cost, carbon and future storage screening.

Validated on a Ningbo reference case; designed for configurable deployment in Malaysia, pending local pilot validation.

Live web application: **[Irene on Vercel](https://irene-flax.vercel.app/)**

Technical architecture: **[View the final PDF](docs/MAIC_Technical_Architecture.pdf)**

## Results at a glance

| Metric | Audited value |
| --- | ---: |
| Annual electricity | 345,676.69 kWh |
| HVAC electricity share | 29.01% |
| Energy-use intensity | 55.47 kWh/m²/year |
| Installed PV | 106.14 kWp |
| Approved aggregate PV generation | 126,233.50 kWh |
| Combined P50 screening saving | 41,581.69 kWh/year (12.03%) |
| Combined P50 simple payback | 2.77 years |
| Current battery storage | None |
| Reference-case tariff | CNY 0.538/kWh (Ningbo case) |

The battery analysis is a future 300 kWh / 120 kW technical sandbox. It is not presented as an installed system or an achieved saving.

The 30.77 tCO₂e combined-case value is a parameterized Malaysia carbon scenario assumption, not a Malaysia field result.

## Commercial pathway

- **Target customers:** commercial buildings, campuses, industrial parks and energy service companies (ESCOs).
- **First paid product:** a file-based energy diagnosis with a confirmed baseline, auditable report and action shortlist.
- **Revenue model:** one-off diagnosis fee, annual subscription, and implementation plus measurement-and-verification (M&V) service fees.
- **Differentiation:** client-data intake, a human confirmation gate, evidence lineage, deterministic calculations and privacy-safe delivery packs.
- **Pilot sequence:** file audit → temporary metering → calibration → savings verification → multi-site scale.

Malaysia's Energy Efficiency and Conservation Act 2024 has been in force since 1 January 2025. The National Energy Transition Roadmap also identifies energy audits, building performance and ESCO delivery as transition priorities. These are policy signals, not a claim of completed local validation. Sources: [Energy Commission Malaysia — EECA 2024](https://www.st.gov.my/stakeholders/energy-efficiency/energy-efficiency-and-conservation-act-eeca-2024) and [Ministry of Economy — National Energy Transition Roadmap](https://ekonomi.gov.my/sites/default/files/2023-09/National%20Energy%20Transition%20Roadmap_0.pdf).

## Run the Streamlit application

Python 3.11 or 3.12 is recommended.

```bash
python -m venv .venv
```

Activate the environment, then install and run:

```bash
python -m pip install -r requirements.txt
streamlit run streamlit_app.py
```

All files needed for the public demonstration are included. The application starts in an auditable local mode with no external service. Module 08 accepts client-owned CSV, Excel, PDF, Word, image, DXF, IFC and DWG inputs in a session-only review flow. Confirmed tables can then be consolidated into a client reporting-period baseline with cost, operational-emissions and EUI calculations. Its downloadable delivery pack contains mappings, quality records, source fingerprints and an audit log, but not the raw client uploads. To use the optional model-enhanced analysis and document-recognition modes, set `OPENAI_API_KEY` in the local environment or Streamlit secrets; never place the key in source control.

## Run the verification suite

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

The tests cover data conservation, model boundaries, tariff calculations, scenario ordering, loss-aware dispatch, client-file mapping, cross-file client baselines, delivery-pack privacy, BIM/CAD gates, document-recognition request safety and the local analysis engine. No live API call is required.

## Web application

The Vercel application is a separate Next.js interface over the same audited case facts and deterministic analysis tools.

```bash
cd web
npm install
npm run dev
```

See [`web/README.md`](web/README.md) for deployment and optional server-side model configuration.

## Repository map

```text
streamlit_app.py          Streamlit competition application
src/                      Data, optimisation and analysis modules
tests/                    Python regression tests
data/processed/           Deterministic synthetic public demo dataset
data/config/              Assumptions, lineage and evidence registers
data/models/              Validated temporal-shape model artifact
results/                  Scenario and dispatch outputs
charts/                   Publication-ready figures
reports/                  Engineering findings and data-gap reports
docs/                     Method, architecture, competition summary and verification notes
web/                      Next.js application deployed on Vercel
```

## Public data and evidence boundary

This repository does not contain original institutional meter rows, private weather records, donor-building records, drawings, client uploads, source filenames or private-source fingerprints. The checked-in row-level meter, weather, hourly load, PV and comfort records are deterministic synthetic demonstration data constrained to the approved aggregate case-study outputs shown above.

Approved aggregates, synthetic public demo records, derived calculations, assumptions, sandbox outputs and missing evidence are kept separate throughout the project. Hourly load and PV series reconcile to the public aggregate monthly anchors, but they are not site measurements and must be replaced with authorized client data for deployment calibration.

The lineage register hashes only public artifacts in this repository. See [`docs/public-data-disclosure.md`](docs/public-data-disclosure.md) for the release boundary and [`docs/model-card.md`](docs/model-card.md) for the public model artifact.

For the full method and system flow, read [`docs/methodology.md`](docs/methodology.md), [`docs/architecture.md`](docs/architecture.md) and [`docs/client-data-onboarding.md`](docs/client-data-onboarding.md). Safe example inputs are available in [`data/examples`](data/examples).

## Copyright and evaluation access

Copyright © 2026 EnerGen AI. All rights reserved. Evaluation access only. See [`LICENSE`](LICENSE).
