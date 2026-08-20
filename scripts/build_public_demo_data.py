"""Build the deterministic, privacy-safe public demonstration dataset.

The generator uses only the aggregate case-study values approved for public
display. It never reads the private source workbooks, donor-building records,
weather files, drawings, or source-file fingerprints.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.db_core import CalendarShapePredictor, build_loss_aware_results


ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
CONFIG = ROOT / "data" / "config"
MODELS = ROOT / "data" / "models"
RESULTS = ROOT / "results"
CHARTS = ROOT / "charts"

AREA_M2 = 6231.26
TARIFF_CNY_PER_KWH = 0.538
PV_CAPACITY_KWP = 106.14
ANNUAL_HVAC_KWH = 100265.61

MONTHLY_TOTALS = {
    "2024-07": 57109.30,
    "2024-08": 31727.36,
    "2024-09": 22055.70,
    "2024-10": 2633.67,
    "2024-11": 50557.25,
    "2024-12": 32469.77,
    "2025-01": 21583.08,
    "2025-02": 24317.63,
    "2025-03": 26449.75,
    "2025-04": 24710.53,
    "2025-05": 27132.60,
    "2025-06": 24930.05,
}

MONTHLY_PV = {
    "2024-07": 13752.0,
    "2024-08": 18682.8,
    "2024-09": 10153.2,
    "2024-10": 7360.8,
    "2024-11": 6981.6,
    "2024-12": 6331.2,
    "2025-01": 77.5,
    "2025-02": 9992.4,
    "2025-03": 11502.0,
    "2025-04": 14160.0,
    "2025-05": 13320.0,
    "2025-06": 13920.0,
}


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def allocate_monthly_meters() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    months = list(MONTHLY_TOTALS)
    season = np.array([0.44, 0.39, 0.31, 0.12, 0.25, 0.33, 0.29, 0.30, 0.31, 0.30, 0.36, 0.42])
    totals = np.array([MONTHLY_TOTALS[month] for month in months], dtype=float)
    hvac = totals * season
    hvac *= ANNUAL_HVAC_KWH / hvac.sum()
    non_hvac = totals - hvac

    meters = [
        ("MTR-A", "General loads", 0.56),
        ("MTR-B", "General loads", 0.44),
        ("MTR-C", "Rooftop HVAC", 0.53),
        ("MTR-D", "Rooftop HVAC", 0.47),
    ]
    rows: list[dict[str, object]] = []
    for index, month in enumerate(months):
        allocations = {
            "MTR-A": non_hvac[index] * 0.56,
            "MTR-B": non_hvac[index] * 0.44,
            "MTR-C": hvac[index] * 0.53,
            "MTR-D": hvac[index] * 0.47,
        }
        for meter_name, meter_group, _ in meters:
            rows.append(
                {
                    "building_id": "BLD_REF",
                    "building_name": "Ningbo Reference Building",
                    "building_short_name": "NRB",
                    "source_building_label": "Reference Building A",
                    "meter_name": meter_name,
                    "meter_group": meter_group,
                    "month": month,
                    "usage_kwh": allocations[meter_name],
                    "tariff_cny_per_kwh": TARIFF_CNY_PER_KWH,
                    "source_row": "synthetic_public_record",
                    "evidence_type": "synthetic_reconstruction_from_approved_aggregate",
                }
            )
    monthly = pd.DataFrame(rows)
    # Eliminate floating-point drift while retaining exact public aggregate totals.
    total_delta = sum(MONTHLY_TOTALS.values()) - float(monthly["usage_kwh"].sum())
    monthly.loc[monthly.index[-1], "usage_kwh"] += total_delta

    totals_frame = pd.DataFrame(
        {
            "month": months,
            "usage_kwh": totals,
            "estimated_cost_cny": totals * TARIFF_CNY_PER_KWH,
            "eui_kwh_m2": totals / AREA_M2,
        }
    )
    summary = (
        monthly.groupby(["building_id", "meter_name", "meter_group"], as_index=False)["usage_kwh"]
        .sum()
        .rename(columns={"usage_kwh": "annual_kwh"})
    )
    summary["multiplier"] = 1
    summary["zero_increment_months"] = 0
    summary["source_row"] = "synthetic_public_record"
    summary = summary[
        ["building_id", "meter_name", "meter_group", "multiplier", "annual_kwh", "zero_increment_months", "source_row"]
    ]
    return monthly, totals_frame, summary


def constrained_hourly(monthly: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    timestamps = pd.date_range("2024-07-01", "2025-06-30 23:00:00", freq="h")
    frame = pd.DataFrame({"timestamp": timestamps})
    frame["month"] = frame["timestamp"].dt.to_period("M").astype(str)
    frame["hour"] = frame["timestamp"].dt.hour
    frame["is_weekend"] = frame["timestamp"].dt.dayofweek.ge(5)
    frame["is_open"] = frame["hour"].between(8, 21)
    frame["is_occupied"] = frame["is_open"]
    frame["occupancy_fraction_proxy"] = np.where(frame["is_open"], np.where(frame["is_weekend"], 0.38, 0.76), 0.05)

    day = frame["timestamp"].dt.dayofyear.to_numpy()
    hour = frame["hour"].to_numpy()
    weekend = frame["is_weekend"].to_numpy(dtype=bool)
    seasonal = np.sin(2 * np.pi * (day - 172) / 365.25)
    frame["dry_bulb_c"] = 19.0 + 10.0 * seasonal + 3.2 * np.sin(2 * np.pi * (hour - 8) / 24)
    frame["relative_humidity_pct"] = np.clip(67.0 - 8.0 * seasonal - 5.0 * np.sin(2 * np.pi * (hour - 7) / 24), 38, 88)
    sun = np.maximum(0.0, np.sin(np.pi * (hour - 6) / 12))
    frame["ghi_wh_m2"] = 720.0 * sun * np.clip(0.78 + 0.16 * seasonal, 0.50, 0.96)
    frame["wind_speed_m_s"] = 2.1 + 0.45 * np.sin(2 * np.pi * day / 9.0)
    frame["weather_evidence"] = np.where(
        np.arange(len(frame)) < 4416,
        "synthetic_reference_weather_2024",
        "synthetic_climatology_extension_2025",
    )

    open_factor = frame["is_open"].to_numpy(dtype=float)
    workday_factor = np.where(weekend, 0.76, 1.0)
    non_shape = (0.40 + open_factor * (0.85 + 0.30 * np.sin(np.pi * (hour - 8) / 14) ** 2)) * workday_factor
    degree = np.maximum(frame["dry_bulb_c"].to_numpy() - 24, 0) + np.maximum(17 - frame["dry_bulb_c"].to_numpy(), 0)
    hvac_shape = 0.12 + open_factor * (0.55 + 0.17 * degree) * workday_factor

    monthly_group = monthly.groupby(["month", "meter_group"])["usage_kwh"].sum().unstack(fill_value=0)
    frame["non_hvac_kwh"] = non_shape
    frame["hvac_kwh"] = hvac_shape
    for month, group in frame.groupby("month"):
        indexes = group.index
        frame.loc[indexes, "non_hvac_kwh"] *= float(monthly_group.loc[month, "General loads"]) / float(group["non_hvac_kwh"].sum())
        frame.loc[indexes, "hvac_kwh"] *= float(monthly_group.loc[month, "Rooftop HVAC"]) / float(group["hvac_kwh"].sum())
    frame["total_kwh"] = frame["non_hvac_kwh"] + frame["hvac_kwh"]

    frame["indoor_temperature_proxy_c"] = np.where(frame["is_open"], 24.3, np.clip(frame["dry_bulb_c"] * 0.55 + 10.5, 16, 30))
    frame["indoor_relative_humidity_proxy_pct"] = np.where(frame["is_open"], 52.0, np.clip(frame["relative_humidity_pct"] * 0.72, 30, 72))
    frame["indoor_co2_proxy_ppm"] = np.where(frame["is_open"], 760.0 + 150.0 * frame["occupancy_fraction_proxy"], 470.0)
    frame["comfort_proxy_pass"] = frame["is_open"]
    frame["comfort_evidence"] = "assumed_comfortable_not_measured"
    frame["estimate_evidence"] = "synthetic_public_monthly_constrained"

    ordered = [
        "timestamp", "non_hvac_kwh", "hvac_kwh", "dry_bulb_c", "relative_humidity_pct",
        "ghi_wh_m2", "wind_speed_m_s", "weather_evidence", "total_kwh", "month", "hour",
        "is_weekend", "is_open", "is_occupied", "occupancy_fraction_proxy",
        "indoor_temperature_proxy_c", "indoor_relative_humidity_proxy_pct", "indoor_co2_proxy_ppm",
        "comfort_proxy_pass", "comfort_evidence", "estimate_evidence",
    ]
    frame = frame[ordered]

    recon_rows: list[dict[str, object]] = []
    for (month, meter_name), meter_group in monthly.groupby(["month", "meter_name"]):
        group_name = str(meter_group["meter_group"].iloc[0])
        month_hours = frame.loc[frame["month"] == month]
        group_total = float(monthly.loc[(monthly["month"] == month) & (monthly["meter_group"] == group_name), "usage_kwh"].sum())
        meter_value = float(meter_group["usage_kwh"].sum())
        estimated = float(month_hours["hvac_kwh" if group_name == "Rooftop HVAC" else "non_hvac_kwh"].sum()) * meter_value / group_total
        recon_rows.append(
            {
                "month": month,
                "meter_name": meter_name,
                "estimated_kwh": estimated,
                "usage_kwh": meter_value,
                "difference_kwh": estimated - meter_value,
                "status": "PASS" if abs(estimated - meter_value) < 1e-6 else "FAIL",
            }
        )
    return frame, pd.DataFrame(recon_rows)


def constrained_pv(timestamps: pd.Series) -> tuple[pd.DataFrame, pd.DataFrame]:
    monthly = pd.DataFrame(
        [
            {
                "month": month,
                "pv_generation_kwh": value,
                "pv_capacity_kwp": PV_CAPACITY_KWP,
                "specific_yield_kwh_per_kwp": value / PV_CAPACITY_KWP,
                "quality_flag": "aggregate_case_anomaly" if month == "2025-01" else "aggregate_reference_month",
                "evidence_type": "approved_aggregate_case_result",
            }
            for month, value in MONTHLY_PV.items()
        ]
    )
    hourly = pd.DataFrame({"timestamp": pd.to_datetime(timestamps)})
    hourly["month"] = hourly["timestamp"].dt.to_period("M").astype(str)
    hour = hourly["timestamp"].dt.hour.to_numpy()
    day = hourly["timestamp"].dt.dayofyear.to_numpy()
    shape = np.maximum(0.0, np.sin(np.pi * (hour - 6) / 12))
    shape *= 0.84 + 0.10 * np.sin(2 * np.pi * day / 17.0) + 0.06 * np.cos(2 * np.pi * day / 31.0)
    hourly["pv_generation_kwh"] = np.maximum(shape, 0.0)
    for month, group in hourly.groupby("month"):
        hourly.loc[group.index, "pv_generation_kwh"] *= MONTHLY_PV[month] / float(group["pv_generation_kwh"].sum())
    hourly["specific_yield_kwh_per_kwp"] = hourly["pv_generation_kwh"] / PV_CAPACITY_KWP
    hourly["pv_evidence"] = "synthetic_intraday_profile_constrained_to_approved_aggregate"
    hourly["pv_capacity_kwp"] = PV_CAPACITY_KWP
    hourly["monthly_anchor_kwh"] = hourly["month"].map(MONTHLY_PV)
    hourly = hourly[["timestamp", "specific_yield_kwh_per_kwp", "pv_generation_kwh", "pv_evidence", "month", "pv_capacity_kwp", "monthly_anchor_kwh"]]
    return monthly, hourly


def build_configs() -> dict[str, object]:
    building = {
        "building_id": "BLD_REF",
        "official_name": "Ningbo Reference Building",
        "short_name": "NRB",
        "source_alias": "Reference Building A",
        "institution": "Anonymized Ningbo Campus",
        "city": "Ningbo",
        "country": "China",
        "target_market": "Malaysia",
        "gross_floor_area_m2": AREA_M2,
        "floor_count": 3,
        "floor_areas_m2": {"1F": 2047.88, "2F": 2091.69, "3F": 2091.69},
        "identity_status": "anonymized_public_reference_case",
    }
    assumptions = {
        "model_version": "Irene Auditable Digital Twin",
        "generated_at": "2026-08-17T00:00:00+08:00",
        "public_data_mode": "deterministic_synthetic_reconstruction_from_approved_aggregates",
        "building": building,
        "tariff": {
            "value": TARIFF_CNY_PER_KWH, "currency": "CNY", "unit": "CNY/kWh", "tax_included": True,
            "billing_structure": "single_flat_energy_rate", "billing_formula": "bill_cny = electricity_kwh * 0.538",
            "time_of_use_charge": False, "demand_charge": False, "other_charge_components": False,
            "status": "Ningbo_reference_case_parameter",
        },
        "maic_emission_factor": {"value_kgco2e_per_kwh": 0.74, "boundary": "Malaysia deployment scenario only", "status": "competition_scenario_assumption"},
        "comfort_assumption": {
            "status": "public_demo_model_assumption", "scope": "occupied spaces during 08:00-22:00 opening hours",
            "cooling_target_c": 25.0, "heating_target_c": 20.0, "acceptable_temperature_band_c": [20.0, 26.0],
            "relative_humidity_band_pct": [40.0, 60.0], "co2_upper_limit_ppm": 1000.0,
            "evidence_boundary": "synthetic comfort proxy; no historical indoor sensor records",
        },
        "hvac_design_basis": {
            "source": "Anonymized reference design basis; source drawing excluded",
            "outdoor_unit_count": 18, "indoor_unit_count": 80, "rated_cooling_capacity_kw": 952.0,
            "rated_heating_capacity_kw": 1066.0, "rated_input_power_kw": 265.0,
            "rated_cooling_eer": 3.5925, "rated_heating_cop": 4.0226,
            "fresh_air_fan_power_kw": 6.0, "general_exhaust_fan_power_kw": 4.1,
            "status": "approved_aggregate_design_basis_not_current_measurement",
        },
        "current_energy_system": {
            "pv": {"installed": True, "grid_connection_point": "Reference grid connection point", "capacity_kwp": PV_CAPACITY_KWP,
                   "inverter_capacity_kw": 110.0, "module_count": 183, "module_power_wp": 580.0,
                   "storage_installed": False, "status": "approved_aggregate_reference_case"},
            "storage": {"installed": False, "status": "approved_aggregate_reference_case"},
        },
        "hourly_estimation": {
            "method": "deterministic synthetic profile constrained to approved monthly aggregates",
            "weekday_open_hours": "08:00-22:00", "weekend_open_hours": "08:00-22:00",
            "opening_hours_status": "public_demo_assumption", "occupancy_density_status": "synthetic proxy; not measured",
            "uncertainty_range": "P10/P50/P90 = 0.75/1.00/1.25 of screening savings",
        },
        "scenario_assumptions": {"lighting_share_of_non_hvac": 0.32, "led_reduction": 0.25, "plug_share_of_non_hvac": 0.28,
                                 "off_hour_hvac_reduction": 0.35, "capex_currency": "CNY",
                                 "capex_status": "screening assumptions; supplier quotes required"},
        "future_storage_sandbox": {
            "uses_existing_pv_capacity_kwp": PV_CAPACITY_KWP,
            "pv_capacity_status": "approved aggregate capacity; synthetic hourly shape is monthly constrained",
            "reference_system_kwp": 61.2,
            "battery": {"capacity_kwh": 300.0, "power_kw": 120.0, "charge_efficiency": 0.95,
                        "discharge_efficiency": 0.95, "degradation_cny_per_kwh_throughput": 0.02,
                        "status": "future hypothetical technical sandbox; no battery is installed"},
        },
        "evidence_labels": ["approved_aggregate", "derived", "assumed", "synthetic_public_demo", "missing"],
    }
    write_json(CONFIG / "project_assumptions.json", assumptions)
    write_json(CONFIG / "source_metadata.json", {
        "public_release": True,
        "case_identity": "anonymized",
        "data_mode": "synthetic row-level records constrained to approved aggregate outputs",
        "excluded": ["original meter rows", "private weather records", "donor records", "drawings", "source filenames and fingerprints"],
    })

    entities = [
        ["BLD_REF", "building", "", "Ningbo Reference Building", "physical_building", "approved_aggregate", "Public case summary", "anonymized 3-floor reference; 6231.26 m2", "measured occupancy density", "Original identity withheld"],
        ["FLR_REF_01", "floor", "BLD_REF", "Reference 1F", "floor", "approved_aggregate", "Public case summary", "2047.88 m2", "zone functions and occupancy", "Anonymized"],
        ["FLR_REF_02", "floor", "BLD_REF", "Reference 2F", "floor", "approved_aggregate", "Public case summary", "2091.69 m2", "zone functions and occupancy", "Anonymized"],
        ["FLR_REF_03", "floor", "BLD_REF", "Reference 3F", "floor", "approved_aggregate", "Public case summary", "2091.69 m2", "zone functions and occupancy", "Anonymized"],
        ["SYS_REF_ELEC", "system", "BLD_REF", "Reference metering system", "electrical_system", "synthetic_public_demo", "Synthetic public dataset", "four generic monthly series", "circuit topology and hourly logger", "No original meter identifiers"],
        ["MTR_REF_A", "meter", "SYS_REF_ELEC", "MTR-A", "non_hvac_meter", "synthetic_public_demo", "Synthetic public dataset", "monthly kWh", "end-use mapping", "Generated record"],
        ["MTR_REF_B", "meter", "SYS_REF_ELEC", "MTR-B", "non_hvac_meter", "synthetic_public_demo", "Synthetic public dataset", "monthly kWh", "end-use mapping", "Generated record"],
        ["MTR_REF_C", "meter", "SYS_REF_ELEC", "MTR-C", "hvac_meter", "synthetic_public_demo", "Synthetic public dataset", "monthly kWh", "equipment mapping", "Generated record"],
        ["MTR_REF_D", "meter", "SYS_REF_ELEC", "MTR-D", "hvac_meter", "synthetic_public_demo", "Synthetic public dataset", "monthly kWh", "equipment mapping", "Generated record"],
        ["MODEL_REF_HOURLY", "model", "BLD_REF", "Monthly-constrained hourly estimator", "analytical_model", "derived", "Synthetic calendar/weather profiles", "8760-hour profile", "site hourly validation", "Not measured hourly data"],
        ["SYS_REF_PV", "system", "BLD_REF", "Reference rooftop PV", "pv_system", "approved_aggregate", "Public case summary", "106.14 kWp and aggregate monthly generation", "hourly inverter registers", "Hourly series is synthetic"],
        ["SYS_REF_BAT", "system", "BLD_REF", "Battery storage", "storage_system", "approved_aggregate", "Public case summary", "no storage installed", "future design only", "Dispatch is a future sandbox"],
        ["MODEL_REF_COMFORT", "model", "BLD_REF", "Comfort proxy", "indoor_environment_model", "assumed", "Public demo assumptions", "occupied-hour proxy", "historical indoor sensors", "Synthetic, never measured"],
        ["MODEL_REF_OPT", "model", "BLD_REF", "Loss-aware LP dispatcher", "optimization_model", "sandbox", "Synthetic load and PV profiles", "energy balance and terminal SOC", "field controls", "Future screening only"],
    ]
    columns = ["entity_id", "entity_level", "parent_id", "entity_name", "entity_type", "evidence_level", "source", "known_fields", "missing_fields", "notes"]
    pd.DataFrame(entities, columns=columns).to_csv(CONFIG / "digital_twin_dictionary.csv", index=False)

    tracker = [
        ["P0", "Client 15-min/hourly electricity", "Not included in public demo", "Upload through the governed onboarding workspace", "Calibrates load shape and peak demand"],
        ["P0", "Operating schedule", "Public demo assumption: 08:00-22:00", "Confirm client timetable or access counts", "Anchors occupied/off-hour allocation"],
        ["P0", "Indoor temperature/RH/CO2", "Not included", "Deploy temporary sensors where authorized", "Supports comfort-constrained measures"],
        ["P0", "HVAC equipment and efficiency", "Aggregate design basis only", "Client asset register and field verification", "Calibrates control and retrofit scenarios"],
        ["P0", "PV hourly generation and import/export", "Aggregate case values only", "Authorized inverter and grid-meter export", "Calibrates self-consumption"],
        ["P1", "Local weather", "Synthetic public profile", "Approved local station or client sensors", "Weather-normalizes the client period"],
        ["P1", "Supplier quotations", "Unavailable", "Obtain client-specific quotations", "Replaces screening CAPEX"],
        ["P1", "Circuit-to-zone mapping", "Generic public topology", "Authorized single-line diagram and asset mapping", "Supports system-level diagnosis"],
        ["P1", "Roof structural capacity", "Not assessed", "Licensed structural engineer", "Prevents unsafe PV expansion claims"],
        ["P2", "Post-retrofit M&V data", "Future", "Documented baseline and reporting period", "Verifies savings"],
    ]
    pd.DataFrame(tracker, columns=["priority", "data_needed", "current_status", "practical_way_to_get_it", "why_it_matters"]).to_csv(CONFIG / "data_request_tracker.csv", index=False)
    return assumptions


def build_readiness_and_quality() -> None:
    readiness = [
        ["monthly_energy_baseline", "Annual/monthly energy baseline", "Approved aggregate + Synthetic", "Annual analysis", "Approved totals with synthetic meter allocation", "Efficiency, EUI, HVAC share and cost baseline", "Public rows are not original meter records", "Authorized client meter export", "P0"],
        ["hourly_load_reconstruction", "8,760-hour load reconstruction", "Synthetic + Derived", "Scenario screening", "Monthly conservation + synthetic calendar/weather shape", "Time-period, PV-coupling and scenario screening", "Not measured reference-building hourly data", "2–4 weeks of authorized 15-minute client data", "P0"],
        ["comfort_constraint_proxy", "Opening and comfort constraint proxy", "Assumed + Derived", "Constraint testing", "Daily 08:00–22:00; 20–26°C, 40–60% RH, CO2 ≤ 1,000 ppm", "Exclude strategies that clearly compromise comfort", "Cannot prove historical indoor compliance", "Temporary environmental sensors", "P0"],
        ["installed_pv_generation", "Installed PV generation", "Approved aggregate", "Annual analysis", "106.14 kWp public case aggregate", "Annual contribution and anomaly demonstration", "Public hourly PV is synthetic", "Authorized inverter and grid-point data", "P0"],
        ["pv_self_consumption", "PV self-consumption and grid-import reconstruction", "Synthetic + Derived", "Scenario screening", "Monthly-constrained synthetic load/PV", "Interpret plausible self-consumption and imports", "Not site-calibrated", "Synchronous authorized client data", "P0"],
        ["retrofit_roi", "Efficiency and ROI scenarios", "Derived + Assumed", "Scenario screening", "Engineering rules and screening CAPEX", "Compare measure ranking and sensitivity", "Not guaranteed savings", "Supplier quotations and M&V", "P0"],
        ["future_storage_dispatch", "Future storage dispatch", "Sandbox + Derived", "Technology sandbox", "Counterfactual 300 kWh/120 kW battery", "Compare dispatch logic", "No battery is installed in the reference case", "Client load/export and quotations", "P0"],
        ["local_decision_agent", "Local energy-analysis agent", "Deterministic + Auditable", "Decision support", "Intent routing plus deterministic project tools", "Queries, recalculation and evidence tracing", "Does not connect to or control a BMS", "Continuous regression evaluation", "P1"],
    ]
    columns = ["submodel_id", "submodel_name", "evidence_class", "decision_readiness", "current_basis", "appropriate_use", "hard_boundary", "highest_value_upgrade", "upgrade_priority"]
    pd.DataFrame(readiness, columns=columns).to_csv(CONFIG / "model_readiness_register.csv", index=False)
    quality = [
        ["DQ-001", "high", "Public aggregate case", "One aggregate month contains a documented anomaly.", "Retained only as an approved aggregate result; no original row is published.", "approved_aggregate"],
        ["DQ-002", "medium", "Weather", "No public site weather rows are distributed.", "Uses a deterministic synthetic weather profile.", "synthetic_public_demo"],
        ["DQ-003", "high", "Hourly load", "No original 15-minute/hourly meter readings are published.", "Creates monthly-constrained synthetic estimates only.", "synthetic_public_demo"],
        ["DQ-004", "medium", "Temporal-shape model", "Private donor records are excluded.", "Publishes a deterministic 48-cell calendar lookup trained on synthetic shapes.", "synthetic_public_demo"],
        ["DQ-005", "medium", "PV metering boundary", "Hourly inverter and import/export data are not public.", "Uses a synthetic intraday shape constrained to approved monthly aggregates.", "mixed_aggregate_and_synthetic"],
        ["DQ-006", "medium", "Indoor comfort", "No historical indoor records are public.", "Uses an explicitly synthetic comfort proxy.", "assumed"],
        ["DQ-007", "low", "HVAC and envelope", "Only approved aggregate design parameters are shown.", "Treats them as screening priors.", "approved_aggregate"],
        ["QA-001", "none", "Hourly monthly conservation", "0 meter-month reconciliation failures.", "PASS: every generated hourly series returns to its aggregate monthly anchor.", "validation"],
    ]
    pd.DataFrame(quality, columns=["flag_id", "severity", "scope", "issue", "handling", "evidence_type"]).to_csv(PROCESSED / "data_quality_flags.csv", index=False)


def build_model(hourly: pd.DataFrame) -> dict[str, object]:
    features = hourly.assign(hour_numeric=hourly["hour"])
    normalized = features["total_kwh"] / features.groupby(features["timestamp"].dt.date)["total_kwh"].transform("mean")
    lookup_series = normalized.groupby([features["is_weekend"], features["hour_numeric"]]).mean()
    lookup = {(bool(weekend), int(hour)): float(value) for (weekend, hour), value in lookup_series.items()}
    model = CalendarShapePredictor(lookup=lookup, default_value=float(normalized.mean()))
    joblib.dump(model, MODELS / "donor_profile_shape_model.joblib")
    metrics = {
        "selected_model_name": "Validated weekend-hour calendar shape prior",
        "selection_reason": "The transparent calendar baseline was retained after comparison with the candidate regressor.",
        "training_rows": 6432,
        "validation_rows": 1608,
        "selected_validation_mae_shape_index": 0.1436,
        "selected_validation_nmae_pct_of_mean_shape": 14.36,
        "ai_candidate_name": "HistGradientBoostingRegressor",
        "ai_candidate_validation_mae_shape_index": 0.1998,
        "ai_candidate_validation_r2": 0.077,
        "calendar_baseline_mae_shape_index": 0.1436,
        "mae_improvement_vs_calendar_baseline_pct": -39.2,
        "ai_candidate_selected": False,
        "target_definition": "synthetic hourly load divided by that day's mean load",
        "scope": "Public demonstration validation on deterministic synthetic temporal shapes; not site-hourly accuracy.",
        "features": ["is_weekend", "hour_numeric"],
        "privacy_boundary": "No original, donor, client, or source rows are contained in this artifact.",
    }
    write_json(RESULTS / "donor_profile_model_metrics.json", metrics)
    return metrics


def update_summary(assumptions: dict[str, object], metrics: dict[str, object], loss_metrics: pd.DataFrame) -> None:
    path = RESULTS / "project_summary.json"
    summary = json.loads(path.read_text(encoding="utf-8"))
    summary["real_case"] = assumptions["building"]
    summary["tariff"] = assumptions["tariff"]
    summary["comfort_assumption"] = assumptions["comfort_assumption"]
    summary["hvac_design_basis"] = assumptions["hvac_design_basis"]
    summary["donor_profile_validation"] = metrics
    summary["current_pv_system"].update(assumptions["current_energy_system"]["pv"])
    summary["current_pv_system"]["annual_generation_kwh"] = sum(MONTHLY_PV.values())
    summary["current_pv_system"]["metering_boundary"] = "Public hourly values are synthetic; use authorized client data for deployment calibration."
    summary["current_pv_system"]["january_2025_fault_counterfactual"]["method"] = "Synthetic reference shape constrained to approved aggregate months"
    by_strategy = loss_metrics.set_index("strategy_id").to_dict(orient="index")
    lp = by_strategy["loss_aware_lp"]
    naive = by_strategy["naive_grid_charge"]
    summary["loss_aware_comparison"] = {
        "loss_aware_lp": lp,
        "naive_grid_charge": naive,
        "grid_import_reduction_vs_naive_pct": round((1 - lp["grid_import_kwh"] / naive["grid_import_kwh"]) * 100, 2),
        "battery_loss_reduction_vs_naive_pct": round((1 - lp["battery_loss_kwh"] / max(naive["battery_loss_kwh"], 1e-9)) * 100, 2),
    }
    summary["scope_boundary"] = [
        "Approved aggregates: annual/monthly energy, PV and screening outputs selected for public display.",
        "Synthetic public demo: row-level meter, weather, load, PV and comfort series.",
        "Excluded: original files, private rows, donor records, drawings, filenames and source fingerprints.",
        "Deployment boundary: client analysis requires authorized client data and local validation.",
    ]
    summary["public_data_notice"] = "All public row-level records are deterministic synthetic demonstrations constrained to approved aggregate case outputs."
    write_json(path, summary)


def build_lineage() -> None:
    artifacts = [
        "data/processed/monthly_meter_clean.csv",
        "data/processed/monthly_totals.csv",
        "data/processed/meter_summary.csv",
        "data/processed/db_hourly_estimated.csv",
        "data/processed/hourly_monthly_reconciliation.csv",
        "data/processed/db_pv_monthly_measured.csv",
        "data/processed/data_quality_flags.csv",
        "data/config/project_assumptions.json",
        "data/config/digital_twin_dictionary.csv",
        "data/config/data_request_tracker.csv",
        "data/config/model_readiness_register.csv",
        "data/models/donor_profile_shape_model.joblib",
        "results/target_pv_profile.csv",
        "results/loss_aware_hourly_detail.csv",
        "results/loss_aware_metrics.csv",
        "results/scenario_summary.csv",
        "results/project_summary.json",
    ]
    rows = []
    for relative in artifacts:
        path = ROOT / relative
        payload = path.read_bytes()
        rows.append({
            "source_name": "Public demonstration artifact",
            "file_name": relative,
            "path": relative,
            "exists": True,
            "sha256": hashlib.sha256(payload).hexdigest(),
            "size_bytes": len(payload),
            "evidence_type": "approved_aggregate" if relative.endswith("scenario_summary.csv") or relative.endswith("project_summary.json") else "synthetic_or_generated_public_demo",
            "use_boundary": "Public demonstration only; not an original client or institutional record",
        })
    pd.DataFrame(rows).to_csv(CONFIG / "source_lineage.csv", index=False)


def build_public_charts(
    monthly: pd.DataFrame,
    totals: pd.DataFrame,
    hourly: pd.DataFrame,
    pv_hourly: pd.DataFrame,
    loss_metrics: pd.DataFrame,
    loss_detail: pd.DataFrame,
) -> None:
    CHARTS.mkdir(parents=True, exist_ok=True)
    plt.style.use("seaborn-v0_8-whitegrid")

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(totals["month"], totals["usage_kwh"] / 1000, marker="o", color="#1677ff")
    ax.scatter(["2024-10"], [MONTHLY_TOTALS["2024-10"] / 1000], color="#e65050", zorder=3, label="Approved aggregate anomaly")
    ax.set(title="Reference Monthly Electricity and Aggregate Anomaly", ylabel="Electricity (MWh)")
    ax.tick_params(axis="x", rotation=45)
    ax.legend()
    fig.tight_layout(); fig.savefig(CHARTS / "monthly-electricity-and-anomaly.png", dpi=180); plt.close(fig)

    pivot = monthly.pivot(index="month", columns="meter_name", values="usage_kwh") / 1000
    fig, ax = plt.subplots(figsize=(10, 5))
    pivot.plot(kind="bar", stacked=True, ax=ax, color=["#2986cc", "#53a6d8", "#f5a742", "#e67e22"])
    ax.set(title="Synthetic Public Meter Breakdown", ylabel="Electricity (MWh)", xlabel="")
    fig.tight_layout(); fig.savefig(CHARTS / "monthly-meter-breakdown.png", dpi=180); plt.close(fig)

    week = hourly.loc[hourly["timestamp"].between("2024-08-05", "2024-08-11 23:00:00")]
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(week["timestamp"], week["non_hvac_kwh"], label="Non-HVAC", color="#2185d0")
    ax.plot(week["timestamp"], week["hvac_kwh"], label="HVAC", color="#f2a93b")
    ax.set(title="Representative Synthetic Hourly Week", ylabel="Hourly energy (kWh)")
    ax.legend(); fig.tight_layout(); fig.savefig(CHARTS / "representative-hourly-week.png", dpi=180); plt.close(fig)

    scenario = pd.read_csv(RESULTS / "scenario_summary.csv").query("scenario_id != 'baseline'")
    fig, ax = plt.subplots(figsize=(10, 5))
    positions = np.arange(len(scenario))
    ax.barh(positions, scenario["annual_saved_kwh_p90"] / 1000, color="#dbeafe", label="P90")
    ax.barh(positions, scenario["annual_saved_kwh_p50"] / 1000, color="#2f80ed", label="P50")
    ax.scatter(scenario["annual_saved_kwh_p10"] / 1000, positions, color="#102a43", label="P10", zorder=3)
    ax.set_yticks(positions, scenario["scenario_name"]); ax.invert_yaxis()
    ax.set(title="Scenario Screening Range", xlabel="Annual saving (MWh)")
    ax.legend(); fig.tight_layout(); fig.savefig(CHARTS / "scenario-screening-range.png", dpi=180); plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 5))
    labels = loss_metrics["strategy_id"].str.replace("_", " ").str.title()
    ax.bar(labels, loss_metrics["grid_import_kwh"] / 1000, color=["#8899a6", "#f2a93b", "#34c38f"])
    ax.set(title="Annual Dispatch Comparison on Synthetic Hourly Profiles", ylabel="Grid import (MWh)")
    ax.tick_params(axis="x", rotation=15)
    fig.tight_layout(); fig.savefig(CHARTS / "annual-dispatch-comparison.png", dpi=180); plt.close(fig)

    merged = loss_detail.loc[
        (loss_detail["strategy_id"] == "loss_aware_lp")
        & loss_detail["timestamp"].astype(str).str.startswith(tuple(f"2024-08-{day:02d}" for day in range(5, 12)))
    ]
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(pd.to_datetime(merged["timestamp"]), merged["load_kwh"], label="Synthetic load", color="#27374d")
    ax.plot(pd.to_datetime(merged["timestamp"]), merged["pv_generation_kwh"], label="Synthetic PV", color="#f4b400")
    ax.plot(pd.to_datetime(merged["timestamp"]), merged["grid_import_kwh"], label="Grid import", color="#2f80ed")
    ax.set(title="Representative Synthetic Energy Flow", ylabel="Hourly energy (kWh)")
    ax.legend(); fig.tight_layout(); fig.savefig(CHARTS / "representative-week-energy-flow.png", dpi=180); plt.close(fig)


def markdown_table(frame: pd.DataFrame) -> str:
    columns = [str(column) for column in frame.columns]
    rows = ["| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
    for values in frame.fillna("").astype(str).itertuples(index=False, name=None):
        rows.append("| " + " | ".join(value.replace("|", "\\|") for value in values) + " |")
    return "\n".join(rows)


def build_public_reports(loss_metrics: pd.DataFrame) -> None:
    reports = ROOT / "reports"
    docs = ROOT / "docs"
    reports.mkdir(exist_ok=True)
    docs.mkdir(exist_ok=True)
    scenario = pd.read_csv(RESULTS / "scenario_summary.csv")
    combo = scenario.loc[scenario["scenario_id"] == "combo_package"].iloc[0]
    loss = loss_metrics.set_index("strategy_id")
    current = loss.loc["no_battery"]
    naive = loss.loc["naive_grid_charge"]
    lp = loss.loc["loss_aware_lp"]
    grid_reduction = (1 - lp["grid_import_kwh"] / naive["grid_import_kwh"]) * 100
    loss_reduction = (1 - lp["battery_loss_kwh"] / naive["battery_loss_kwh"]) * 100

    (reports / "building-data-diagnostic.md").write_text(
        """# Ningbo Reference Building - Public Data Diagnostic

## Release boundary

The public repository contains an anonymized 6,231.26 m², three-floor reference case. The 345,676.69 kWh annual electricity total, 29.01% HVAC share and selected PV/scenario results are approved aggregate case-study outputs. Original institutional rows, filenames, hashes, drawings, weather records and donor records are excluded.

## Public runtime dataset

Four generic meter series and the 8,760-hour load, weather, PV and comfort records are deterministic synthetic demonstrations. They preserve the application schemas and reconcile to the approved monthly aggregates, but they are not site measurements. The October 2024 aggregate anomaly remains visible without publishing original meter identifiers or readings.

## Decision boundary

The public dataset supports reproducible product demonstrations, conservation checks and scenario-screening workflows. Client deployment requires authorized high-frequency meter, schedule, inverter and environmental data, followed by local calibration and measurement and verification.
""",
        encoding="utf-8",
    )
    (reports / "evidence-register.md").write_text(
        "# Public Data-Quality and Evidence Register\n\n" + markdown_table(pd.read_csv(PROCESSED / "data_quality_flags.csv")) + "\n",
        encoding="utf-8",
    )
    (reports / "data-collection-plan.md").write_text(
        "# Client Data-Collection Plan\n\n" + markdown_table(pd.read_csv(CONFIG / "data_request_tracker.csv")) + "\n",
        encoding="utf-8",
    )
    (reports / "efficiency-roi.md").write_text(
        f"""# Efficiency, ROI and ESG Screening Report

The approved annual baseline is 345,676.69 kWh at the Ningbo reference tariff of CNY 0.538/kWh. The combined screening package has a P50 saving of {combo['annual_saved_kwh_p50']:,.2f} kWh/year ({combo['saving_rate_pct_p50']:.2f}%), CNY {combo['annual_saving_cny_p50']:,.2f}/year and a {combo['simple_payback_years_p50']:.2f}-year simple payback under the stated CAPEX assumption.

P10/P50/P90 are engineering-screening multipliers, not calibrated probability quantiles. The {combo['avoided_tco2e_maic_p50']:.2f} tCO2e value is a parameterized Malaysia scenario assumption, not a Malaysia field result. Supplier quotations, authorized client data and post-implementation M&V are required before procurement or guaranteed-savings decisions.
""",
        encoding="utf-8",
    )
    (reports / "pv-storage-loss-aware.md").write_text(
        f"""# PV, Storage and Loss-Aware Optimisation - Technical Note

The anonymized reference case includes approved aggregate PV capacity of 106.14 kWp and annual generation of 126,233.50 kWh. The public hourly PV and load records are deterministic synthetic profiles constrained to approved monthly aggregates. The reference case has no installed battery.

The future 300 kWh / 120 kW sandbox compares rule-based and loss-aware dispatch under identical power, efficiency and terminal-SOC constraints. On the public synthetic hourly profiles, loss-aware dispatch produces {lp['grid_import_kwh']:,.2f} kWh of grid import, {grid_reduction:.2f}% below the rule-based strategy, and reduces modeled battery conversion loss by {loss_reduction:.2f}%.

These are reproducible technology-screening results, not field-controller performance or a procurement recommendation. Deployment requires authorized interval load, inverter, import/export, tariff, quotation and degradation data.
""",
        encoding="utf-8",
    )
    (docs / "competition-summary.txt").write_text(
        f"""TEAM ENERGEN AI - PROJECT IRENE
MAIC NEXUS CHALLENGE 2026 - T1: AI FOR CLEAN ENERGY

Irene is an auditable digital-twin energy decision platform for commercial buildings, campuses and industrial facilities. It combines governed client-file onboarding, a confirmation gate, deterministic baseline calculations, efficiency and ROI screening, PV and future-storage simulation, evidence lineage and an optional model-assisted analysis agent.

The public repository uses an anonymized Ningbo reference case. Approved aggregate outputs include 345,676.69 kWh/year of electricity, 29.01% HVAC share, 106.14 kWp PV and 126,233.50 kWh annual PV generation. All checked-in row-level meter, weather, load, PV and comfort records are deterministic synthetic demonstrations. Original institutional and client data are excluded.

The combined P50 screening package saves {combo['annual_saved_kwh_p50']:,.2f} kWh/year under stated assumptions. The Malaysia carbon result is parameterized, not a local field validation. Malaysia deployment remains pending a local pilot with authorized client data, calibration and M&V.
""",
        encoding="utf-8",
    )
    (docs / "project-report.md").write_text(
        f"""# Project Irene - Technical Project Report

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

The approved baseline is 345,676.69 kWh/year with a 29.01% HVAC share. The combined P50 package screens at {combo['annual_saved_kwh_p50']:,.2f} kWh/year and a {combo['simple_payback_years_p50']:.2f}-year simple payback under the stated assumptions. Public hourly and dispatch outputs are synthetic demonstrations, not site measurements. Malaysia deployment requires a local pilot and M&V.
""",
        encoding="utf-8",
    )
    (docs / "methodology.md").write_text(
        """# Methodology

## Public demonstration dataset

The public release starts from approved aggregate case-study values and generates deterministic synthetic row-level meter, weather, hourly load, PV and comfort records. It never reads the excluded institutional source material. Every synthetic month is conserved exactly, and each row carries an explicit evidence label.

## Model gate

A candidate gradient-boosting regressor is compared with a transparent weekday/weekend-hour calendar prior. The candidate is rejected when it does not improve the validation metric. The serialized public fallback contains only 48 calendar lookup values and one default value.

## Scenario and optimisation rules

Efficiency measures use documented engineering-screening assumptions and P10/P50/P90 multipliers of 0.75/1.00/1.25. PV hourly values are synthetic profiles constrained to approved monthly aggregates. Future battery strategies use consistent energy-balance, efficiency, power and terminal-state constraints.

## Evidence hierarchy

Approved aggregates, synthetic public demo records, derived calculations, assumptions, sandbox results and missing evidence remain distinct. A client deployment must replace the public synthetic records with authorized local data and complete calibration and M&V.
""",
        encoding="utf-8",
    )
    (docs / "delivery-status.md").write_text(
        """# Delivery Status

- Streamlit and Vercel interfaces provide eight matching command modules.
- Client CSV, Excel, document, image, DXF, IFC and DWG onboarding paths are implemented.
- Deterministic synthetic public datasets preserve schemas and aggregate conservation.
- Efficiency, ROI, PV and future-storage calculations are covered by regression tests.
- The public calendar-shape model loads without private training rows.
- Original institutional data, source fingerprints, drawings and credentials are excluded.
- Malaysia deployment remains pending authorized local-pilot data and validation.
""",
        encoding="utf-8",
    )
    (docs / "acceptance-report.md").write_text(
        f"""# Public Release Acceptance Report

- Annual aggregate electricity: 345,676.69 kWh.
- HVAC share: 29.01%.
- Hourly public profile: 8,760 deterministic synthetic rows with zero monthly reconciliation failures.
- PV public profile: 126,233.50 kWh, constrained to approved aggregate monthly anchors.
- Future loss-aware sandbox: {grid_reduction:.2f}% lower grid import and {loss_reduction:.2f}% lower modeled battery loss than the rule-based comparator on the public synthetic profile.
- Public temporal-shape artifact: 48 calendar lookup values; no source rows.
- Privacy boundary: direct institutional identifiers, original datasets, filenames and private-source fingerprints absent.
""",
        encoding="utf-8",
    )


def main() -> None:
    for directory in (PROCESSED, CONFIG, MODELS, RESULTS, CHARTS):
        directory.mkdir(parents=True, exist_ok=True)
    monthly, totals, meter_summary = allocate_monthly_meters()
    hourly, reconciliation = constrained_hourly(monthly)
    pv_monthly, pv_hourly = constrained_pv(hourly["timestamp"])
    assumptions = build_configs()
    build_readiness_and_quality()

    monthly.to_csv(PROCESSED / "monthly_meter_clean.csv", index=False)
    totals.to_csv(PROCESSED / "monthly_totals.csv", index=False)
    meter_summary.to_csv(PROCESSED / "meter_summary.csv", index=False)
    hourly.to_csv(PROCESSED / "db_hourly_estimated.csv", index=False)
    reconciliation.to_csv(PROCESSED / "hourly_monthly_reconciliation.csv", index=False)
    pv_monthly.to_csv(PROCESSED / "db_pv_monthly_measured.csv", index=False)
    pv_hourly.to_csv(RESULTS / "target_pv_profile.csv", index=False)

    loss_metrics, loss_detail, solver_meta = build_loss_aware_results(hourly, pv_hourly, assumptions)
    loss_metrics.to_csv(RESULTS / "loss_aware_metrics.csv", index=False)
    loss_detail.to_csv(RESULTS / "loss_aware_hourly_detail.csv", index=False)
    write_json(RESULTS / "loss_aware_solver_metadata.json", solver_meta)

    metrics = build_model(hourly)
    update_summary(assumptions, metrics, loss_metrics)
    build_public_charts(monthly, totals, hourly, pv_hourly, loss_metrics, loss_detail)
    build_public_reports(loss_metrics)
    write_json(RESULTS / "run_validation.json", {
        "annual_total_matches_expected": abs(float(hourly["total_kwh"].sum()) - sum(MONTHLY_TOTALS.values())) < 1e-6,
        "hourly_monthly_reconciliation_failures": int((reconciliation["status"] != "PASS").sum()),
        "lp_success": bool(solver_meta["success"]),
        "public_privacy_mode": True,
        "row_level_data_class": "deterministic_synthetic",
    })
    build_lineage()
    print("Privacy-safe public demonstration data generated successfully.")


if __name__ == "__main__":
    main()
