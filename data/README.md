# Data Included in This Repository

`processed/` contains deterministic synthetic row-level records required to run the Streamlit application and regression tests. The generated records are constrained to the aggregate case-study outputs approved for public display. `config/` contains public-demo assumptions, evidence labels, the data-request register and a lineage register for public artifacts. `models/` contains the small calendar-shape demonstration artifact described in `docs/model-card.md`.

Original institutional spreadsheets, weather rows, donor records, drawings and documents are not published. Original filenames, file sizes and hashes are also excluded. The public lineage register fingerprints only the generated artifacts that are actually present in this repository.

Important interpretation rules:

- Monthly energy and PV values are approved aggregate case-study outputs.
- Meter-level and hourly public records are deterministic synthetic demonstrations constrained to those aggregates.
- No original or donor-building row is present in the public repository.
- Comfort outputs are proxies because historical indoor sensor records are unavailable.
- Battery outputs are future-scenario results; the reference case has no installed storage.

Rebuild the public demo at any time with:

```bash
python -m scripts.build_public_demo_data
```
