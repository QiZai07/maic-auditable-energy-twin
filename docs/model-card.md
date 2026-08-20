# Public Temporal-Shape Model Card

## Purpose

`data/models/donor_profile_shape_model.joblib` is the public demonstration fallback used to produce a normalized hourly calendar shape when site-hourly data are unavailable.

## Artifact contents

The serialized `CalendarShapePredictor` contains 48 normalized lookup values: weekday/weekend × 24 hours, plus one default value. It contains no original meter rows, donor-building records, weather records, client data, filenames or source fingerprints.

## Training boundary

The public artifact is rebuilt from deterministic synthetic hourly profiles produced with `scripts/build_public_demo_data.py`. The candidate gradient-boosting regressor remains rejected by the documented performance gate; the transparent calendar prior is selected.

## Appropriate use

- Public demonstration and regression testing.
- Scenario-screening fallback when authorized high-frequency data are unavailable.
- Reproducible testing of the load-shape interface.

It is not evidence of site-hourly accuracy and is not suitable for peak-demand commitments, equipment control or guaranteed savings. A client deployment should retrain or recalibrate with authorized site data.

## Loading and security

Load only the artifact distributed with this repository. Joblib and pickle formats can execute code during deserialization; do not load untrusted replacement files.
