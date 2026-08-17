# Public Data-Quality and Evidence Register

| flag_id | severity | scope | issue | handling | evidence_type |
| --- | --- | --- | --- | --- | --- |
| DQ-001 | high | Public aggregate case | One aggregate month contains a documented anomaly. | Retained only as an approved aggregate result; no original row is published. | approved_aggregate |
| DQ-002 | medium | Weather | No public site weather rows are distributed. | Uses a deterministic synthetic weather profile. | synthetic_public_demo |
| DQ-003 | high | Hourly load | No original 15-minute/hourly meter readings are published. | Creates monthly-constrained synthetic estimates only. | synthetic_public_demo |
| DQ-004 | medium | Temporal-shape model | Private donor records are excluded. | Publishes a deterministic 48-cell calendar lookup trained on synthetic shapes. | synthetic_public_demo |
| DQ-005 | medium | PV metering boundary | Hourly inverter and import/export data are not public. | Uses a synthetic intraday shape constrained to approved monthly aggregates. | mixed_aggregate_and_synthetic |
| DQ-006 | medium | Indoor comfort | No historical indoor records are public. | Uses an explicitly synthetic comfort proxy. | assumed |
| DQ-007 | low | HVAC and envelope | Only approved aggregate design parameters are shown. | Treats them as screening priors. | approved_aggregate |
| QA-001 | none | Hourly monthly conservation | 0 meter-month reconciliation failures. | PASS: every generated hourly series returns to its aggregate monthly anchor. | validation |
