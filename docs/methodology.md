# Methodology

## Public demonstration dataset

The public release starts from approved aggregate case-study values and generates deterministic synthetic row-level meter, weather, hourly load, PV and comfort records. It never reads the excluded institutional source material. Every synthetic month is conserved exactly, and each row carries an explicit evidence label.

## Model gate

A candidate gradient-boosting regressor is compared with a transparent weekday/weekend-hour calendar prior. The candidate is rejected when it does not improve the validation metric. The serialized public fallback contains only 48 calendar lookup values and one default value.

## Scenario and optimisation rules

Efficiency measures use documented engineering-screening assumptions and P10/P50/P90 multipliers of 0.75/1.00/1.25. PV hourly values are synthetic profiles constrained to approved monthly aggregates. Future battery strategies use consistent energy-balance, efficiency, power and terminal-state constraints.

## Evidence hierarchy

Approved aggregates, synthetic public demo records, derived calculations, assumptions, sandbox results and missing evidence remain distinct. A client deployment must replace the public synthetic records with authorized local data and complete calibration and M&V.
