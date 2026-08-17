from __future__ import annotations

import io
import json
import sys
import unittest
import zipfile
from pathlib import Path

import pandas as pd


APP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_DIR))

from src.client_onboarding import (  # noqa: E402
    assess_readiness,
    build_mapping_template,
    extract_text_facts,
    infer_field,
    parse_client_file,
    validate_upload,
)
from src.client_project import assess_client_project, build_client_deliverable  # noqa: E402


class TestClientOnboarding(unittest.TestCase):
    def test_csv_mapping_quality_and_readiness(self) -> None:
        payload = (
            "Timestamp,Electricity kWh,Demand kW,Outdoor Temperature C\n"
            "2026-01-01 00:00,12.4,4.2,30.0\n"
            "2026-01-01 01:00,13.1,4.6,29.5\n"
            "2026-01-01 02:00,12.8,4.4,29.0\n"
        ).encode()
        result = parse_client_file("meter.csv", payload)
        self.assertEqual(result["phase"], "Phase 1")
        targets = {item["target"] for item in result["tables"][0]["mappings"]}
        self.assertIn("timestamp", targets)
        self.assertIn("electricity_kwh", targets)
        self.assertIn("demand_kw", targets)
        self.assertEqual(result["tables"][0]["quality"]["coverage"]["granularity"], "hourly")
        self.assertEqual(result["privacy"], "Processed in the current session. No raw file is retained by this parser.")
        operational = next(item for item in result["readiness"]["capabilities"] if item["name"] == "Operational calibration")
        self.assertFalse(operational["ready"])

    def test_excel_reads_multiple_sheets_without_running_macros(self) -> None:
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            pd.DataFrame({"Bill Month": ["2026-01"], "Usage kWh": [1200]}).to_excel(writer, sheet_name="Bills", index=False)
            pd.DataFrame({"Asset ID": ["AHU-01"], "Rated Power kW": [22]}).to_excel(writer, sheet_name="Assets", index=False)
        result = parse_client_file("client.xlsx", buffer.getvalue())
        self.assertEqual(len(result["tables"]), 2)
        self.assertEqual(result["tables"][0]["mappings"][0]["target"], "billing_period")

    def test_text_fact_extraction(self) -> None:
        facts = extract_text_facts("Gross floor area: 6,231.26 m2. Installed capacity: 106.14 kWp. Tariff: 0.538 CNY/kWh.")
        fact_types = {fact["type"] for fact in facts}
        self.assertEqual(fact_types, {"floor_area", "capacity", "tariff"})

    def test_ifc_structure_is_counted(self) -> None:
        ifc = b"ISO-10303-21;HEADER;FILE_SCHEMA(('IFC4'));ENDSEC;DATA;#1=IFCBUILDING('id',$,'Main Building',$,$,$,$,$,$,$,$,$);#2=IFCBUILDINGSTOREY('s',$,'Level 1',$,$,$,$,$,$,$);#3=IFCSPACE('r',$,'Room 101',$,$,$,$,$,$,$,$);ENDSEC;END-ISO-10303-21;"
        result = parse_client_file("model.ifc", ifc)
        self.assertEqual(result["details"]["buildings"], 1)
        self.assertEqual(result["details"]["storeys"], 1)
        self.assertEqual(result["details"]["spaces"], 1)

    def test_dxf_layers_labels_and_closed_area_are_extracted(self) -> None:
        try:
            import ezdxf
        except ImportError:
            self.skipTest("ezdxf is not installed in this test environment")
        document = ezdxf.new("R2018")
        document.header["$INSUNITS"] = 6
        document.layers.add("ENERGY")
        modelspace = document.modelspace()
        modelspace.add_text("AHU-01 rated power 22 kW", dxfattribs={"layer": "ENERGY"})
        modelspace.add_lwpolyline([(0, 0), (10, 0), (10, 5), (0, 5)], close=True, dxfattribs={"layer": "ENERGY"})
        buffer = io.StringIO()
        document.write(buffer)
        result = parse_client_file("floor.dxf", buffer.getvalue().encode())
        self.assertIn("ENERGY", result["details"]["layers"])
        self.assertIn("AHU-01 rated power 22 kW", result["details"]["text_labels"])
        self.assertAlmostEqual(result["details"]["closed_polyline_area_values"][0], 50.0)

    def test_dwg_is_truthfully_marked_for_conversion(self) -> None:
        result = parse_client_file("plant.dwg", b"AC1032" + b"\x00" * 128)
        self.assertEqual(result["phase"], "Phase 3")
        self.assertIn(result["status"], {"conversion_required", "review_required"})
        self.assertEqual(result["details"]["dwg_signature"], "AC1032")

    def test_mapping_template_requires_confirmation(self) -> None:
        result = parse_client_file("meter.csv", b"Month,Energy kWh\n2026-01,100\n")
        template = build_mapping_template(result)
        self.assertFalse(template["approved_for_model"])
        self.assertTrue(all(not mapping["confirmed"] for mapping in template["tables"][0]["mappings"]))

    def test_extension_and_signature_are_checked(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            validate_upload("script.exe", b"MZ")
        with self.assertRaisesRegex(ValueError, "signature"):
            validate_upload("fake.pdf", b"not a pdf")

    def test_low_confidence_column_is_not_forced(self) -> None:
        mapping = infer_field("Comment reference")
        self.assertEqual(mapping["target"], "unmapped")
        self.assertTrue(mapping["requires_confirmation"])

    def test_readiness_does_not_claim_training_from_monthly_data(self) -> None:
        result = parse_client_file("meter.csv", b"Bill Month,Usage kWh\n2026-01,100\n2026-02,120\n")
        readiness = assess_readiness(result["tables"])
        operational = next(item for item in readiness["capabilities"] if item["name"] == "Operational calibration")
        self.assertFalse(operational["ready"])

    def test_confirmed_project_consolidates_files_and_labels_assumptions(self) -> None:
        first = parse_client_file(
            "meter-a.csv",
            b"Bill Month,Usage kWh,Peak Demand kW\n2026-01,1000,75\n2026-02,1200,82\n",
        )
        second = parse_client_file(
            "meter-b.csv",
            b"Bill Month,Usage kWh\n2026-01,300\n2026-02,400\n",
        )
        analysis = assess_client_project(
            [first, second],
            {
                "project_name": "Client pilot",
                "currency": "MYR",
                "tariff_per_kwh": 0.45,
                "grid_emission_factor_kg_co2e_kwh": 0.6,
                "gross_floor_area_m2": 1_000,
            },
        )
        self.assertEqual(analysis["control_gate"]["approved_files"], 2)
        self.assertAlmostEqual(analysis["results"]["electricity_kwh"], 2_900)
        self.assertAlmostEqual(analysis["results"]["reporting_cost"], 1_305)
        self.assertAlmostEqual(analysis["results"]["emissions_tco2e"], 1.74)
        self.assertAlmostEqual(analysis["results"]["reporting_period_eui_kwh_m2"], 2.9)
        self.assertEqual(analysis["results"]["tariff_source"], "client project input")
        self.assertEqual(analysis["monthly"][0]["electricity_kwh"], 1_300)
        self.assertTrue(any("not annualised" in item for item in analysis["warnings"]))

    def test_cumulative_meter_readings_use_positive_deltas(self) -> None:
        manifest = parse_client_file(
            "register.csv",
            b"Timestamp,Meter ID,Cumulative kWh\n2026-01-01,A,100\n2026-02-01,A,175\n2026-03-01,A,20\n2026-04-01,A,55\n",
        )
        analysis = assess_client_project([manifest])
        self.assertAlmostEqual(analysis["results"]["electricity_kwh"], 110)

    def test_deliverable_has_audit_registers_but_no_raw_rows(self) -> None:
        manifest = parse_client_file("meter.csv", b"Bill Month,Usage kWh\n2026-01,100\n2026-02,120\n")
        analysis = assess_client_project([manifest], {"tariff_per_kwh": 0.5})
        payload = build_client_deliverable([manifest], analysis, generated_at="2026-08-12T00:00:00+00:00")
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            self.assertEqual(
                set(archive.namelist()),
                {"README.txt", "project_summary.json", "audit_log.json", "source_manifest.json", "mapping_register.csv", "quality_register.csv", "monthly_baseline.csv"},
            )
            self.assertNotIn("2026-01,100", archive.read("source_manifest.json").decode())
            audit = json.loads(archive.read("audit_log.json"))
            self.assertEqual(audit["generated_at_utc"], "2026-08-12T00:00:00+00:00")

    def test_duplicate_file_is_excluded_from_analysis_and_export(self) -> None:
        manifest = parse_client_file("meter.csv", b"Bill Month,Usage kWh\n2026-01,100\n")
        analysis = assess_client_project([manifest, manifest])
        self.assertEqual(analysis["results"]["electricity_kwh"], 100)
        self.assertEqual(analysis["control_gate"]["approved_files"], 1)
        with zipfile.ZipFile(io.BytesIO(build_client_deliverable([manifest, manifest], analysis))) as archive:
            audit = json.loads(archive.read("audit_log.json"))
            self.assertEqual(audit["events"][1]["record_count"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
