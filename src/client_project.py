from __future__ import annotations

import csv
import io
import json
import math
import re
import zipfile
from datetime import datetime, timezone
from typing import Any, Iterable

import pandas as pd


SCHEMA_VERSION = "irene-client-project-v1"
ENERGY_FIELDS = (
    "electricity_kwh",
    "grid_import_kwh",
    "grid_export_kwh",
    "pv_generation_kwh",
)


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _positive(value: Any) -> float | None:
    number = _finite(value)
    return number if number is not None and number > 0 else None


def _clean_text(value: Any, fallback: str = "") -> str:
    clean = re.sub(r"[\x00-\x1f\x7f]+", " ", str(value or "")).strip()
    return clean[:160] or fallback


def normalise_project_profile(profile: dict[str, Any] | None = None) -> dict[str, Any]:
    source = profile or {}
    return {
        "project_name": _clean_text(source.get("project_name"), "Client energy review"),
        "client_reference": _clean_text(source.get("client_reference"), "Not supplied"),
        "site_name": _clean_text(source.get("site_name"), "Not supplied"),
        "country_or_region": _clean_text(source.get("country_or_region"), "Not supplied"),
        "currency": _clean_text(source.get("currency"), "Local currency")[:16],
        "tariff_per_kwh": _positive(source.get("tariff_per_kwh")),
        "grid_emission_factor_kg_co2e_kwh": _positive(source.get("grid_emission_factor_kg_co2e_kwh")),
        "gross_floor_area_m2": _positive(source.get("gross_floor_area_m2")),
    }


def _unit_multiplier(field: str, unit: Any) -> float:
    clean = re.sub(r"[^a-z0-9]+", "", str(unit or "").lower())
    if field in {*ENERGY_FIELDS, "cumulative_kwh"}:
        if clean.startswith("mwh"):
            return 1_000.0
        if clean.startswith("wh") and not clean.startswith("kwh"):
            return 0.001
    if field in {"demand_kw", "capacity_kw"}:
        if clean.startswith("mw"):
            return 1_000.0
        if clean.startswith("w") and not clean.startswith("kw"):
            return 0.001
    if field == "building_area_m2" and any(token in clean for token in ("ft2", "sqft", "squarefeet")):
        return 0.09290304
    return 1.0


def _mapped_columns(table: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for mapping in table.get("mappings", []):
        target = mapping.get("target")
        source = mapping.get("source")
        if target and target != "unmapped" and source and target not in result:
            result[str(target)] = dict(mapping)
    return result


def _time_series(frame: pd.DataFrame, mapped: dict[str, dict[str, Any]]) -> pd.Series:
    item = mapped.get("timestamp") or mapped.get("billing_period")
    if not item or item["source"] not in frame:
        return pd.Series(pd.NaT, index=frame.index, dtype="datetime64[ns]")
    return pd.to_datetime(frame[item["source"]], errors="coerce")


def _numeric_series(frame: pd.DataFrame, mapped: dict[str, dict[str, Any]], field: str) -> pd.Series | None:
    item = mapped.get(field)
    if not item or item["source"] not in frame:
        return None
    return pd.to_numeric(frame[item["source"]], errors="coerce") * _unit_multiplier(field, item.get("unit"))


def _cumulative_deltas(frame: pd.DataFrame, mapped: dict[str, dict[str, Any]], times: pd.Series) -> pd.Series | None:
    readings = _numeric_series(frame, mapped, "cumulative_kwh")
    if readings is None:
        return None
    working = pd.DataFrame({"reading": readings, "time": times}, index=frame.index)
    meter_mapping = mapped.get("meter_id")
    if meter_mapping and meter_mapping["source"] in frame:
        working["meter"] = frame[meter_mapping["source"]].astype(str)
    else:
        working["meter"] = "__single_meter__"
    sort_columns = ["meter"] + (["time"] if working["time"].notna().any() else [])
    working = working.sort_values(sort_columns)
    deltas = working.groupby("meter", dropna=False)["reading"].diff()
    deltas = deltas.where(deltas >= 0)
    return deltas.reindex(frame.index)


def analyse_table(table: dict[str, Any]) -> dict[str, Any]:
    frame = table.get("_frame")
    if not isinstance(frame, pd.DataFrame):
        frame = pd.DataFrame(table.get("preview", []))
    mapped = _mapped_columns(table)
    times = _time_series(frame, mapped)
    energy = _numeric_series(frame, mapped, "electricity_kwh")
    energy_source = "electricity_kwh"
    if energy is None:
        energy = _numeric_series(frame, mapped, "grid_import_kwh")
        energy_source = "grid_import_kwh"
    if energy is None:
        energy = _cumulative_deltas(frame, mapped, times)
        energy_source = "cumulative_kwh"

    numeric: dict[str, pd.Series | None] = {field: _numeric_series(frame, mapped, field) for field in ENERGY_FIELDS}
    numeric["demand_kw"] = _numeric_series(frame, mapped, "demand_kw")
    numeric["cost"] = _numeric_series(frame, mapped, "cost")
    numeric["tariff"] = _numeric_series(frame, mapped, "tariff")
    numeric["building_area_m2"] = _numeric_series(frame, mapped, "building_area_m2")
    if numeric["electricity_kwh"] is None and energy is not None:
        numeric["electricity_kwh"] = energy

    monthly: dict[str, dict[str, float]] = {}
    periods = times.dt.to_period("M").astype(str).where(times.notna(), "undated")
    for field in (*ENERGY_FIELDS, "cost"):
        series = numeric.get(field)
        if series is None:
            continue
        grouped = series.where(series >= 0).groupby(periods).sum(min_count=1)
        for period, value in grouped.dropna().items():
            monthly.setdefault(str(period), {})[field] = float(value)

    def total(field: str) -> float | None:
        series = numeric.get(field)
        if series is None:
            return None
        clean = series.where(series >= 0).dropna()
        return float(clean.sum()) if len(clean) else None

    valid_times = times.dropna()
    demand = numeric["demand_kw"]
    tariff = numeric["tariff"]
    area = numeric["building_area_m2"]
    return {
        "energy_source": energy_source if energy is not None else None,
        "totals": {field: total(field) for field in (*ENERGY_FIELDS, "cost")},
        "peak_demand_kw": float(demand.max()) if demand is not None and len(demand.dropna()) else None,
        "median_tariff_per_kwh": float(tariff.where(tariff > 0).median()) if tariff is not None and len(tariff.where(tariff > 0).dropna()) else None,
        "gross_floor_area_m2": float(area.where(area > 0).max()) if area is not None and len(area.where(area > 0).dropna()) else None,
        "coverage_start": valid_times.min().isoformat() if len(valid_times) else None,
        "coverage_end": valid_times.max().isoformat() if len(valid_times) else None,
        "dated_rows": int(times.notna().sum()),
        "monthly": [{"period": period, **values} for period, values in sorted(monthly.items())],
    }


def _fact_number(manifests: Iterable[dict[str, Any]], fact_type: str) -> float | None:
    values = [
        _positive(fact.get("value"))
        for manifest in manifests
        for fact in manifest.get("extracted_facts", [])
        if fact.get("type") == fact_type
    ]
    clean = [value for value in values if value is not None]
    return max(clean) if clean else None


def assess_client_project(manifests: Iterable[dict[str, Any]], profile: dict[str, Any] | None = None) -> dict[str, Any]:
    project = normalise_project_profile(profile)
    unique: list[dict[str, Any]] = []
    seen_hashes: set[str] = set()
    duplicate_files: list[str] = []
    for manifest in manifests:
        digest = str(manifest.get("sha256") or manifest.get("id") or manifest.get("filename"))
        if digest in seen_hashes:
            duplicate_files.append(str(manifest.get("filename", "unnamed file")))
            continue
        seen_hashes.add(digest)
        unique.append(manifest)

    table_results: list[dict[str, Any]] = []
    for manifest in unique:
        for table in manifest.get("tables", []):
            if table.get("included_for_project", True) is False:
                continue
            table_results.append({
                "filename": manifest.get("filename"),
                "table": table.get("name"),
                "row_count": table.get("row_count", 0),
                "quality_score": table.get("quality", {}).get("score", 0),
                "analysis": analyse_table(table),
            })

    monthly: dict[str, dict[str, float]] = {}
    for item in table_results:
        for row in item["analysis"]["monthly"]:
            period = row["period"]
            target = monthly.setdefault(period, {})
            for field in (*ENERGY_FIELDS, "cost"):
                value = _finite(row.get(field))
                if value is not None:
                    target[field] = target.get(field, 0.0) + value

    def sum_metric(field: str) -> float | None:
        values = [_finite(item["analysis"]["totals"].get(field)) for item in table_results]
        clean = [value for value in values if value is not None]
        return sum(clean) if clean else None

    electricity = sum_metric("electricity_kwh")
    grid_import = sum_metric("grid_import_kwh")
    grid_export = sum_metric("grid_export_kwh")
    pv_generation = sum_metric("pv_generation_kwh")
    observed_cost = sum_metric("cost")
    peak_values = [_finite(item["analysis"].get("peak_demand_kw")) for item in table_results]
    peak_demand = max((value for value in peak_values if value is not None), default=None)

    table_tariffs = [_positive(item["analysis"].get("median_tariff_per_kwh")) for item in table_results]
    fact_tariff = _fact_number(unique, "tariff")
    tariff = project["tariff_per_kwh"] or next((value for value in table_tariffs if value is not None), None) or fact_tariff
    tariff_source = "client project input" if project["tariff_per_kwh"] else "confirmed file evidence" if tariff else "not supplied"

    table_areas = [_positive(item["analysis"].get("gross_floor_area_m2")) for item in table_results]
    fact_area = _fact_number(unique, "floor_area")
    area = project["gross_floor_area_m2"] or max((value for value in table_areas if value is not None), default=None) or fact_area
    area_source = "client project input" if project["gross_floor_area_m2"] else "confirmed file evidence" if area else "not supplied"

    dates = [
        pd.Timestamp(value)
        for item in table_results
        for value in (item["analysis"].get("coverage_start"), item["analysis"].get("coverage_end"))
        if value
    ]
    coverage_start = min(dates).isoformat() if dates else None
    coverage_end = max(dates).isoformat() if dates else None
    coverage_days = max(1, (max(dates) - min(dates)).days + 1) if dates else None
    dated_periods = sorted(period for period in monthly if period != "undated")

    calculated_cost = electricity * tariff if electricity is not None and tariff is not None else None
    reporting_cost = observed_cost if observed_cost is not None else calculated_cost
    cost_basis = "measured bill amount" if observed_cost is not None else "energy × confirmed tariff" if calculated_cost is not None else "unavailable"
    carbon_factor = project["grid_emission_factor_kg_co2e_kwh"]
    emissions_tco2e = electricity * carbon_factor / 1_000 if electricity is not None and carbon_factor is not None else None
    eui = electricity / area if electricity is not None and area is not None else None

    monthly_rows: list[dict[str, Any]] = []
    for period, values in sorted(monthly.items()):
        energy_value = values.get("electricity_kwh")
        monthly_rows.append({
            "period": period,
            **{field: round(value, 6) for field, value in values.items()},
            "calculated_cost": round(energy_value * tariff, 6) if energy_value is not None and tariff is not None else None,
            "emissions_tco2e": round(energy_value * carbon_factor / 1_000, 6) if energy_value is not None and carbon_factor is not None else None,
        })

    row_weight = sum(max(1, int(item["row_count"])) for item in table_results)
    quality_score = round(sum(item["quality_score"] * max(1, int(item["row_count"])) for item in table_results) / row_weight) if row_weight else None
    warnings: list[str] = []
    if not unique:
        warnings.append("No client file has passed the human confirmation gate.")
    if electricity is None:
        warnings.append("No confirmed electricity-consumption series is available.")
    if electricity is not None and not dated_periods:
        warnings.append("Energy is available, but no valid reporting date was mapped.")
    if electricity is not None and tariff is None and observed_cost is None:
        warnings.append("Supply a confirmed tariff or bill amount to calculate reporting-period cost.")
    if electricity is not None and carbon_factor is None:
        warnings.append("Supply the applicable grid emission factor to calculate operational emissions.")
    if electricity is not None and area is None:
        warnings.append("Supply confirmed gross floor area to calculate reporting-period EUI.")
    if coverage_days is not None and coverage_days < 330:
        warnings.append("Coverage is shorter than 330 days; results are reporting-period totals and are not annualised.")
    if duplicate_files:
        warnings.append(f"{len(duplicate_files)} duplicate file(s) were excluded using their file fingerprint.")

    return {
        "schema_version": SCHEMA_VERSION,
        "project": project,
        "control_gate": {"approved_files": len(unique), "duplicate_files_excluded": duplicate_files},
        "coverage": {"start": coverage_start, "end": coverage_end, "days": coverage_days, "dated_months": len(dated_periods)},
        "results": {
            "electricity_kwh": electricity,
            "grid_import_kwh": grid_import,
            "grid_export_kwh": grid_export,
            "pv_generation_kwh": pv_generation,
            "peak_demand_kw": peak_demand,
            "observed_cost": observed_cost,
            "calculated_cost": calculated_cost,
            "reporting_cost": reporting_cost,
            "cost_basis": cost_basis,
            "tariff_per_kwh": tariff,
            "tariff_source": tariff_source,
            "grid_emission_factor_kg_co2e_kwh": carbon_factor,
            "emissions_tco2e": emissions_tco2e,
            "gross_floor_area_m2": area,
            "area_source": area_source,
            "reporting_period_eui_kwh_m2": eui,
            "quality_score": quality_score,
        },
        "monthly": monthly_rows,
        "source_tables": table_results,
        "warnings": warnings,
        "evidence_boundary": "Calculated results use only human-confirmed mappings and files. Tariff, emission factor and area are labelled by source. Raw uploads are not included in the deliverable pack.",
    }


def _public_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "filename": manifest.get("filename"),
        "sha256": manifest.get("sha256"),
        "kind": manifest.get("kind"),
        "phase": manifest.get("phase"),
        "status": manifest.get("status"),
        "tables": [
            {
                "name": table.get("name"),
                "row_count": table.get("row_count"),
                "included_for_project": table.get("included_for_project", True),
                "quality": table.get("quality"),
                "mappings": table.get("mappings", []),
            }
            for table in manifest.get("tables", [])
        ],
        "extracted_facts": manifest.get("extracted_facts", []),
    }


def build_project_audit(manifests: Iterable[dict[str, Any]], analysis: dict[str, Any], generated_at: str | None = None) -> dict[str, Any]:
    files = list(manifests)
    timestamp = generated_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": timestamp,
        "events": [
            {"sequence": 1, "event": "project_profile_reviewed", "record_count": 1},
            {"sequence": 2, "event": "source_files_confirmed", "record_count": len(files)},
            {"sequence": 3, "event": "deterministic_project_analysis_completed", "record_count": len(analysis.get("source_tables", []))},
            {"sequence": 4, "event": "deliverable_pack_created", "record_count": 1},
        ],
        "file_fingerprints": [{"filename": item.get("filename"), "sha256": item.get("sha256")} for item in files],
        "control_gate": analysis.get("control_gate"),
        "evidence_boundary": analysis.get("evidence_boundary"),
    }


def _csv_bytes(rows: list[dict[str, Any]], columns: list[str]) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode("utf-8-sig")


def build_client_deliverable(manifests: Iterable[dict[str, Any]], analysis: dict[str, Any], generated_at: str | None = None) -> bytes:
    files: list[dict[str, Any]] = []
    seen: set[str] = set()
    for manifest in manifests:
        key = str(manifest.get("sha256") or manifest.get("id") or manifest.get("filename"))
        if key not in seen:
            seen.add(key)
            files.append(manifest)
    audit = build_project_audit(files, analysis, generated_at)
    mappings = [
        {
            "filename": manifest.get("filename"),
            "sha256": manifest.get("sha256"),
            "table": table.get("name"),
            "source_field": mapping.get("source"),
            "model_field": mapping.get("target"),
            "confirmed_unit": mapping.get("unit"),
            "confirmed": True,
            "included_for_project": table.get("included_for_project", True),
        }
        for manifest in files
        for table in manifest.get("tables", [])
        for mapping in table.get("mappings", [])
    ]
    quality = [
        {
            "filename": manifest.get("filename"),
            "table": table.get("name"),
            "rows": table.get("row_count"),
            "score": table.get("quality", {}).get("score"),
            "errors": table.get("quality", {}).get("errors"),
            "warnings": table.get("quality", {}).get("warnings"),
            "granularity": table.get("quality", {}).get("coverage", {}).get("granularity"),
            "included_for_project": table.get("included_for_project", True),
        }
        for manifest in files
        for table in manifest.get("tables", [])
    ]
    public_analysis = {key: value for key, value in analysis.items() if key != "source_tables"}
    public_analysis["source_tables"] = [
        {key: value for key, value in item.items() if key != "analysis"}
        for item in analysis.get("source_tables", [])
    ]
    readme = (
        "IRENE CLIENT PROJECT DELIVERABLE\n\n"
        "This pack records the confirmed field mappings, quality register, reporting-period results and audit sequence.\n"
        "It does not contain the raw client uploads. Reconcile each SHA-256 fingerprint with the client-controlled source file before relying on the results.\n"
        "Results are not annualised when the confirmed coverage is shorter than 330 days. All procurement and operational decisions require client review.\n"
    )
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("README.txt", readme)
        archive.writestr("project_summary.json", json.dumps(public_analysis, indent=2, ensure_ascii=False, default=str))
        archive.writestr("audit_log.json", json.dumps(audit, indent=2, ensure_ascii=False, default=str))
        archive.writestr("source_manifest.json", json.dumps([_public_manifest(item) for item in files], indent=2, ensure_ascii=False, default=str))
        archive.writestr("mapping_register.csv", _csv_bytes(mappings, ["filename", "sha256", "table", "source_field", "model_field", "confirmed_unit", "confirmed", "included_for_project"]))
        archive.writestr("quality_register.csv", _csv_bytes(quality, ["filename", "table", "rows", "score", "errors", "warnings", "granularity", "included_for_project"]))
        archive.writestr("monthly_baseline.csv", _csv_bytes(analysis.get("monthly", []), ["period", "electricity_kwh", "grid_import_kwh", "grid_export_kwh", "pv_generation_kwh", "cost", "calculated_cost", "emissions_tco2e"]))
    return output.getvalue()
