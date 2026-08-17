# Public Data Disclosure

This competition repository is a privacy-safe demonstration release.

## Included

- Source code for the Streamlit and Vercel applications.
- Deterministic synthetic row-level meter, weather, load, PV and comfort records.
- Approved aggregate case-study energy, PV and screening outputs.
- Generated validation, reconciliation, dispatch and chart artifacts.
- A small public calendar-shape model artifact with no source rows.

## Excluded

- Original institutional or client meter records.
- Private weather and donor-building datasets.
- Drawings, source documents and client uploads.
- Original filenames, file sizes and private-source fingerprints.
- Credentials, API keys and local deployment secrets.

The public synthetic records preserve the application schemas, modules, interactions and calculation paths. They are constrained to the approved aggregate case-study totals but are not original measurements. A deployment must replace them with authorized client data and complete local validation before operational or guaranteed-savings use.

The `source_lineage.csv` register fingerprints only public artifacts present in this repository. The deterministic release can be rebuilt with `python -m scripts.build_public_demo_data`.
