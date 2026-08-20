# Project Irene - Technical Project Report

## Purpose

Project Irene converts incomplete building evidence into traceable energy decisions while keeping evidence quality, assumptions and decision readiness visible. Its first paid-product pathway is a file-based energy diagnosis followed by temporary metering, calibration, savings verification and multi-site scale.

## Public reference case

The public version uses an anonymized Ningbo reference case with approved aggregate energy, PV and scenario outputs. Its row-level data are deterministic synthetic records built by `scripts/build_public_demo_data.py`; they preserve the complete application workflow without publishing original institutional data.

## Technical chain

1. Ingest CSV, Excel, PDF, Word, image, DXF, IFC or DWG client files.
2. Map fields, identify quality issues and require human confirmation.
3. Consolidate a client reporting-period baseline.
4. Run deterministic EUI, cost, efficiency, PV and future-storage calculations.
5. Route questions through nine auditable project tools, optionally assisted by a server-side model.
6. Export privacy-safe mappings, quality records, results and an audit log without raw uploads.

## Results and boundary

The approved baseline is 345,676.69 kWh/year with a 29.01% HVAC share. The combined P50 package screens at 41,581.69 kWh/year and a 2.77-year simple payback under the stated assumptions. Public hourly and dispatch outputs are synthetic demonstrations, not site measurements. Malaysia deployment requires a local pilot and M&V.
