from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

import joblib
import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


class TestDBCoreOutputs(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.processed = PROJECT_ROOT / "data" / "processed"
        cls.config = PROJECT_ROOT / "data" / "config"
        cls.results = PROJECT_ROOT / "results"
        cls.summary = json.loads((cls.results / "project_summary.json").read_text(encoding="utf-8"))
        cls.monthly = pd.read_csv(cls.processed / "monthly_meter_clean.csv")
        cls.hourly = pd.read_csv(cls.processed / "db_hourly_estimated.csv", parse_dates=["timestamp"])
        cls.reconciliation = pd.read_csv(cls.processed / "hourly_monthly_reconciliation.csv")
        cls.scenarios = pd.read_csv(cls.results / "scenario_summary.csv")
        cls.loss = pd.read_csv(cls.results / "loss_aware_hourly_detail.csv", parse_dates=["timestamp"])
        cls.pv_monthly = pd.read_csv(cls.processed / "db_pv_monthly_measured.csv")
        cls.pv_hourly = pd.read_csv(cls.results / "target_pv_profile.csv", parse_dates=["timestamp"])
        cls.readiness = pd.read_csv(cls.config / "model_readiness_register.csv")

    def test_canonical_identity_and_tariff(self) -> None:
        self.assertEqual(self.summary["real_case"]["official_name"], "Ningbo Reference Building")
        self.assertEqual(self.summary["real_case"]["building_id"], "BLD_REF")
        self.assertEqual(self.summary["real_case"]["source_alias"], "Reference Building A")
        self.assertEqual(self.summary["real_case"]["identity_status"], "anonymized_public_reference_case")
        self.assertAlmostEqual(self.summary["real_case"]["gross_floor_area_m2"], 6231.26, places=2)
        self.assertEqual(self.summary["tariff"]["currency"], "CNY")
        self.assertAlmostEqual(self.summary["tariff"]["value"], 0.538, places=6)
        self.assertEqual(self.summary["tariff"]["billing_structure"], "single_flat_energy_rate")
        self.assertEqual(self.summary["tariff"]["billing_formula"], "bill_cny = electricity_kwh * 0.538")
        self.assertFalse(self.summary["tariff"]["time_of_use_charge"])
        self.assertFalse(self.summary["tariff"]["demand_charge"])

    def test_annual_meter_totals(self) -> None:
        self.assertAlmostEqual(self.monthly["usage_kwh"].sum(), 345676.69, places=2)
        hvac = self.monthly.loc[self.monthly["meter_group"] == "Rooftop HVAC", "usage_kwh"].sum()
        self.assertAlmostEqual(hvac, 100265.61, places=2)
        self.assertAlmostEqual(self.summary["estimated_annual_bill_cny"], 345676.69 * 0.538, places=2)
        self.assertAlmostEqual(self.summary["calculated_annual_bill_cny"], 345676.69 * 0.538, places=2)

    def test_hourly_output_is_complete_and_monthly_constrained(self) -> None:
        self.assertEqual(len(self.hourly), 8760)
        self.assertFalse(self.hourly["timestamp"].duplicated().any())
        self.assertTrue((self.hourly[["total_kwh", "hvac_kwh", "non_hvac_kwh"]].to_numpy() >= -1e-9).all())
        self.assertEqual(int((self.reconciliation["status"] != "PASS").sum()), 0)
        self.assertLess(float(self.reconciliation["difference_kwh"].abs().max()), 1e-6)

    def test_opening_hours_and_comfort_proxy(self) -> None:
        expected_open = self.hourly["hour"].between(8, 21)
        self.assertTrue((self.hourly["is_open"].astype(bool) == expected_open).all())
        open_rows = self.hourly.loc[expected_open]
        self.assertTrue(open_rows["indoor_temperature_proxy_c"].between(20, 26).all())
        self.assertTrue(open_rows["indoor_relative_humidity_proxy_pct"].between(40, 60).all())
        self.assertTrue(open_rows["indoor_co2_proxy_ppm"].le(1000).all())
        self.assertTrue(open_rows["comfort_proxy_pass"].astype(bool).all())
        self.assertTrue((self.hourly["comfort_evidence"] == "assumed_comfortable_not_measured").all())

    def test_installed_pv_and_no_storage_current_state(self) -> None:
        self.assertAlmostEqual(float(self.pv_monthly["pv_generation_kwh"].sum()), 126233.5, places=2)
        self.assertAlmostEqual(float(self.pv_hourly["pv_generation_kwh"].sum()), 126233.5, places=2)
        self.assertTrue((self.pv_hourly["pv_capacity_kwp"] == 106.14).all())
        self.assertTrue(self.summary["current_pv_system"]["installed"])
        self.assertFalse(self.summary["current_pv_system"]["storage_installed"])
        self.assertEqual(self.summary["current_pv_system"]["grid_connection_point"], "Reference grid connection point")
        current = self.loss.loc[self.loss["strategy_id"] == "no_battery"]
        self.assertTrue(np.allclose(current["battery_throughput_kwh"] if "battery_throughput_kwh" in current else 0, 0))

    def test_scenario_uncertainty_and_currency_arithmetic(self) -> None:
        active = self.scenarios.loc[self.scenarios["scenario_id"] != "baseline"]
        self.assertTrue((active["annual_saved_kwh_p10"] <= active["annual_saved_kwh_p50"]).all())
        self.assertTrue((active["annual_saved_kwh_p50"] <= active["annual_saved_kwh_p90"]).all())
        calculated = active["annual_saved_kwh_p50"] * 0.538
        self.assertTrue(np.allclose(calculated, active["annual_saving_cny_p50"], atol=0.02))
        self.assertTrue((active["result_type"] == "screening_estimate_with_uncertainty").all())
        self.assertTrue((active["uncertainty_calibration_status"] == "not_calibrated_as_statistical_quantiles").all())

    def test_model_readiness_register_prevents_overclaiming(self) -> None:
        self.assertGreaterEqual(len(self.readiness), 8)
        hourly = self.readiness.loc[self.readiness["submodel_id"] == "hourly_load_reconstruction"].iloc[0]
        storage = self.readiness.loc[self.readiness["submodel_id"] == "future_storage_dispatch"].iloc[0]
        self.assertEqual(hourly["decision_readiness"], "Scenario screening")
        self.assertIn("Not measured reference-building hourly data", hourly["hard_boundary"])
        self.assertIn("Technology sandbox", storage["decision_readiness"])

    def test_dispatch_energy_balances(self) -> None:
        for strategy, frame in self.loss.groupby("strategy_id"):
            load_error = frame["grid_to_load_kwh"] + frame["pv_to_load_kwh"] + frame["battery_to_load_kwh"] - frame["load_kwh"]
            pv_error = frame["pv_to_load_kwh"] + frame["pv_to_battery_kwh"] + frame["curtailment_kwh"] - frame["pv_generation_kwh"]
            self.assertLess(float(load_error.abs().max()), 1e-5, strategy)
            self.assertLess(float(pv_error.abs().max()), 1e-5, strategy)
            self.assertTrue((frame["soc_kwh"] >= -1e-6).all(), strategy)
            grid_total = frame["grid_to_load_kwh"] + frame["grid_to_battery_kwh"]
            self.assertTrue(np.allclose(grid_total, frame["grid_import_kwh"], atol=1e-8), strategy)
        lp = self.loss.loc[self.loss["strategy_id"] == "loss_aware_lp"]
        self.assertAlmostEqual(float(lp["soc_kwh"].iloc[-1]), 0.0, places=5)

    def test_weather_evidence_labels(self) -> None:
        counts = self.hourly["weather_evidence"].value_counts().to_dict()
        self.assertEqual(counts.get("synthetic_reference_weather_2024", 0), 4416)
        self.assertEqual(counts.get("synthetic_climatology_extension_2025", 0), 4344)
        self.assertTrue((self.hourly["estimate_evidence"] == "synthetic_public_monthly_constrained").all())

    def test_source_lineage_hashes(self) -> None:
        lineage = pd.read_csv(self.config / "source_lineage.csv")
        existing = lineage.loc[lineage["exists"].astype(str).str.lower().eq("true")]
        self.assertGreaterEqual(len(existing), 12)
        self.assertTrue(existing["sha256"].astype(str).str.fullmatch(r"[0-9a-f]{64}").all())

    def test_model_selection_gate_never_selects_worse_candidate(self) -> None:
        metrics = json.loads((self.results / "donor_profile_model_metrics.json").read_text(encoding="utf-8"))
        selected = metrics["selected_validation_mae_shape_index"]
        candidate = metrics["ai_candidate_validation_mae_shape_index"]
        baseline = metrics["calendar_baseline_mae_shape_index"]
        self.assertLessEqual(selected, min(candidate, baseline) + 1e-9)

    def test_public_model_artifact_loads_and_contains_only_calendar_lookup(self) -> None:
        model = joblib.load(PROJECT_ROOT / "data" / "models" / "donor_profile_shape_model.joblib")
        self.assertEqual(set(vars(model)), {"lookup", "default_value"})
        self.assertEqual(len(model.lookup), 48)
        features = pd.DataFrame({"is_weekend": [False, True], "hour_numeric": [9, 18]})
        prediction = model.predict(features)
        self.assertEqual(prediction.shape, (2,))
        self.assertTrue(np.isfinite(prediction).all())

    def test_public_release_contains_no_direct_source_identifiers(self) -> None:
        forbidden = tuple(
            bytes.fromhex(value).decode("utf-8")
            for value in (
                "746865206c6f72642064656172696e67206275696c64696e67",
                "756e6976657273697479206f66206e6f7474696e6768616d206e696e67626f206368696e61",
                "6275696c64696e67203234",
                "7a617031",
                "7a617032",
                "6b617031",
                "6b617032",
                "64625f6d6f6e74686c795f6d657465725f72656164696e67732e786c7378",
                "646f6e6f725f656e657267795f686f75726c792e786c7378",
                "646f6e6f725f70765f356d696e2e786c7378",
                "757064617465645f776561746865725f323032342e637376",
            )
        )
        text_suffixes = {".csv", ".json", ".md", ".py", ".ts", ".tsx", ".txt", ".yml", ".yaml", ".toml"}
        hits: list[str] = []
        for path in PROJECT_ROOT.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in text_suffixes or ".git" in path.parts:
                continue
            content = path.read_text(encoding="utf-8", errors="ignore").lower()
            for token in forbidden:
                if token in content:
                    hits.append(f"{path.relative_to(PROJECT_ROOT)}: {token}")
        self.assertEqual(hits, [])

    def test_file_manifest_excludes_workspaces_caches_and_secrets(self) -> None:
        from src.db_core import build_file_manifest

        manifest = build_file_manifest(PROJECT_ROOT)
        normalized_paths = manifest["relative_path"].astype(str).str.replace("\\", "/", regex=False).str.lower()
        excluded_parts = {
            ".git",
            ".next",
            ".vercel",
            ".vinext",
            ".wrangler",
            "01_原始资料_只读副本",
            "__pycache__",
            "dist",
            "node_modules",
            "tmp",
        }
        for relative_path in normalized_paths:
            self.assertFalse(set(relative_path.split("/")).intersection(excluded_parts), relative_path)
            self.assertFalse(
                Path(relative_path).name.startswith(".env") and Path(relative_path).name != ".env.example",
                relative_path,
            )
        self.assertNotIn("06_结果输出/file_manifest.csv", normalized_paths.tolist())


if __name__ == "__main__":
    unittest.main(verbosity=2)
