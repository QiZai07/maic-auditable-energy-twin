# Client Data Onboarding

Irene supports a controlled route from client-owned evidence to a client-specific energy model. The anonymized Ningbo reference case remains a demonstration case; a client upload never inherits its absolute energy values, equipment capacities or operating assumptions.

## Operating principle

The onboarding layer separates four actions:

1. **Inspect** the file in the current session.
2. **Map** source fields and units to the Irene data contract.
3. **Check** quality, coverage and decision readiness.
4. **Confirm** the reviewed mapping before the file can enter a model pipeline.
5. **Consolidate** only approved tables into a client reporting-period analysis.
6. **Deliver** a compact audit pack without copying raw client rows.

No automatic mapping is treated as final. A downloaded mapping record remains unapproved until the reviewer passes the control gate.

## Client project analysis

After confirmation, the Streamlit and Vercel applications apply the same deterministic rules:

- direct consumption is preferred, followed by grid import and then positive deltas from cumulative meter registers;
- duplicate files are excluded using SHA-256 fingerprints;
- cover sheets, lookup tabs and duplicate summary tables can be removed from consolidation;
- confirmed units are converted for recognised Wh/MWh, W/MW and ft² cases;
- monthly results are consolidated across included tables and files;
- reporting-period energy cost uses measured bill amount when present, otherwise confirmed energy × tariff;
- operational emissions require an explicit grid-emission factor for the client's reporting boundary;
- reporting-period EUI requires confirmed gross floor area;
- coverage shorter than 330 days is never silently annualised.

Tariff, grid-emission factor and gross floor area can be entered as client project inputs. The result records whether tariff and area came from client input or confirmed file evidence. No jurisdictional factor is inserted automatically.

## Audit-ready deliverable

The downloadable ZIP contains:

- `project_summary.json` — project profile, consolidated results, warnings and evidence boundary;
- `monthly_baseline.csv` — reporting-period monthly energy, cost and emissions where supportable;
- `mapping_register.csv` — confirmed source-to-model field mapping and units;
- `quality_register.csv` — row counts, quality scores and issue counts;
- `source_manifest.json` — file fingerprints and reviewed table metadata;
- `audit_log.json` — ordered control-gate and calculation events;
- `README.txt` — review and interpretation instructions.

Raw source files and raw table rows are deliberately excluded. The file fingerprint allows the client-controlled source to be reconciled later without publishing it.

## Existing-system compatibility and migration

Irene does not require a rip-and-replace deployment. A client can begin with files or read-only exports from its BMS, EMS, meter platform, ERP, inverter portal or document store. Irene maps source fields, units, time zones and meter hierarchies to its canonical data contract, while the source system remains the system of record during the pilot.

The production migration path is:

1. inventory systems, owners, formats, history and access rules;
2. map fields and units, then obtain reviewer approval;
3. backfill the agreed historical period;
4. reconcile energy, cost and asset totals against the source system;
5. run in shadow mode with incremental synchronisation and exception logs;
6. cut over only after client approval, retaining rollback checkpoints and the original source archive.

Current public functionality covers file intake, mapping, quality control, confirmation and the audit pack. Read-only API, SQL-view, SFTP and site-gateway connectors are configured and validated per client; universal vendor-protocol support is not claimed.

## Phase 1 — structured operational data

Accepted inputs: CSV, XLSX and XLSM.

The parser identifies common energy, demand, tariff, weather, PV, equipment and building fields; exposes its match score; keeps source units visible; and checks missing values, duplicates, invalid numeric values, negative readings, extreme values and temporal granularity. Workbook macros are not executed.

Monthly data can support baseline and investment screening. It is not labelled sufficient for operational calibration, anomaly diagnosis or control optimisation unless suitable interval data are present.

## Phase 2 — documents and scans

Accepted inputs: PDF, DOCX, PNG, JPEG and TIFF in Streamlit; the Vercel recognition endpoint accepts PDF, PNG and JPEG.

Embedded PDF and Word text is extracted locally first. Images and low-text PDFs are offered an optional recognition step with three safeguards:

- the reviewer must explicitly confirm that they have permission to send the selected file;
- the API key remains on the server and is never returned to the browser;
- the provider request uses `store: false` and returns a strict structured result with source locations and review items.

CSV, Excel, DXF, IFC and DWG are never sent by this recognition control.

## Phase 3 — BIM and CAD

Accepted inputs: IFC, DXF and DWG.

- **IFC:** validates the STEP header, counts IFC entities and reports buildings, storeys, spaces and equipment-related objects. The lightweight intake does not recompute procurement geometry.
- **DXF:** extracts entities, layers, block references and text labels. Drawing units must be confirmed before dimensions are used.
- **DWG:** validates the file signature and checks for a local converter. Native DWG is not presented as parsed when a converter is absent. The portable route is client export to DXF; the workstation route can use a configured ODA File Converter or LibreDWG adapter.

## Privacy and file limits

The parsers operate on the current session and do not add client files to the repository. The public project contains demonstration data and templates only.

| Surface | Local intake limit | Cloud-recognition limit |
| --- | ---: | ---: |
| Streamlit | 25 MB per file | 12 MB per PDF/image |
| Vercel web app | 25 MB per file | 3 MB per PDF/image |

The lower Vercel recognition limit keeps the request within serverless body limits. Larger documents should be inspected in the Streamlit workstation or split by the client before authorised recognition.

## Model-readiness paths

The readiness panel evaluates monthly baseline and EUI, tariff and bill screening, interval anomaly detection, PV performance, operational calibration, and the equipment/space digital twin. It states what is ready and what evidence is still required. Some cases need deterministic calculation, some need calibration, and only sufficiently rich histories justify a fitted predictive model.
