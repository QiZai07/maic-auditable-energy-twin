import assert from "node:assert/strict";
import test from "node:test";

import { assessClientReadiness, assessTable, extractTextFacts, inferField, recogniseClientDocument } from "../app/client-onboarding.ts";
import { runDocumentRecognition } from "../worker/document-recognition.ts";
import { assessClientProject, buildClientDeliverable } from "../app/client-project.ts";
import { unzipSync } from "fflate";

test("maps common client energy fields without forcing unknown columns", () => {
  assert.equal(inferField("Electricity kWh").target, "electricity_kwh");
  assert.equal(inferField("Peak Demand (kW)").target, "demand_kw");
  assert.equal(inferField("Comment reference").target, "unmapped");
});

test("finds row quality exceptions and interval granularity", () => {
  const columns = ["Timestamp", "Usage kWh"];
  const rows = [
    ["2026-01-01 00:00", 10], ["2026-01-01 01:00", 12], ["2026-01-01 02:00", -1],
  ];
  const quality = assessTable(columns, rows);
  assert.equal(quality.granularity, "hourly");
  assert.equal(quality.errors, 1);
});

test("extracts document facts while preserving units", () => {
  const facts = extractTextFacts("Gross floor area: 6,231.26 m2. Installed capacity: 106.14 kWp. Tariff: 0.538 CNY/kWh.");
  assert.deepEqual(new Set(facts.map((item) => item.field)), new Set(["floor_area", "capacity", "tariff"]));
});

test("readiness does not claim calibration from monthly data", () => {
  const manifest = {
    id: "test", filename: "meter.csv", extension: "csv", size: 100, kind: "Tabular data", phase: "Phase 1", status: "review_required",
    facts: [], details: {}, notes: [], tables: [{ name: "data", rowCount: 2, columns: ["Month", "Usage kWh"], rows: [], mappings: [inferField("Month"), inferField("Usage kWh")], quality: { score: 100, errors: 0, warnings: 0, issues: [], granularity: "monthly" } }],
  };
  const readiness = assessClientReadiness([manifest]);
  assert.equal(readiness.capabilities.find((item) => item.name === "Operational calibration").ready, false);
});

test("a short interval preview is not sufficient for calibration", () => {
  const manifest = {
    id: "short", filename: "meter.csv", extension: "csv", size: 100, kind: "Tabular data", phase: "Phase 1", status: "review_required",
    facts: [], details: {}, notes: [], tables: [{ name: "data", rowCount: 3, columns: ["Timestamp", "Usage kWh", "Temperature C"], rows: [], mappings: [inferField("Timestamp"), inferField("Usage kWh"), inferField("Temperature C")], quality: { score: 100, errors: 0, warnings: 0, issues: [], granularity: "hourly" } }],
  };
  assert.equal(assessClientReadiness([manifest]).capabilities.find((item) => item.name === "Operational calibration").ready, false);
});

test("cloud document request is stateless and structured", async () => {
  let request;
  const fetchStub = async (_input, init) => {
    request = JSON.parse(init.body);
    return new Response(JSON.stringify({ output_text: JSON.stringify({ document_type: "bill", summary: "One bill", facts: [], equipment: [], review_items: [] }) }), { status: 200 });
  };
  const result = await runDocumentRecognition({ filename: "bill.pdf", mediaType: "application/pdf", base64: "JVBERg==" }, { OPENAI_API_KEY: "test-only-key" }, "test-session", fetchStub);
  assert.equal(request.store, false);
  assert.equal(request.input[0].content[1].type, "input_file");
  assert.equal(request.text.format.type, "json_schema");
  assert.equal(result.retention, "store:false");
});

test("quota response is explained without exposing provider details", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => new Response(JSON.stringify({ error: "RECOGNITION_HTTP_429" }), { status: 502, headers: { "content-type": "application/json" } });
  try {
    const file = new File([new Uint8Array([0x89, 0x50, 0x4e, 0x47])], "scan.png", { type: "image/png" });
    await assert.rejects(recogniseClientDocument(file), /quota or rate limit/);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("confirmed client project consolidates monthly energy with labelled inputs", () => {
  const makeManifest = (id, values) => ({
    id, sha256: id.padEnd(64, "0"), filename: `${id}.csv`, extension: "csv", size: 100, kind: "Tabular data", phase: "Phase 1", status: "review_required",
    facts: [], details: {}, notes: [], tables: [{
      name: "data", rowCount: values.length, columns: ["Month", "Usage kWh", "Demand kW"], rows: values, sessionRows: values, includedForProject: true,
      mappings: [inferField("Month"), inferField("Usage kWh"), inferField("Demand kW")], quality: { score: 95, errors: 0, warnings: 1, issues: [], granularity: "monthly" },
    }],
  });
  const analysis = assessClientProject([makeManifest("a", [["2026-01", 1000, 75], ["2026-02", 1200, 82]]), makeManifest("b", [["2026-01", 300, 20], ["2026-02", 400, 22]])], {
    projectName: "Client pilot", currency: "MYR", tariffPerKwh: .45, gridEmissionFactorKgCo2eKwh: .6, grossFloorAreaM2: 1000,
  });
  assert.equal(analysis.results.electricityKwh, 2900);
  assert.equal(analysis.results.reportingCost, 1305);
  assert.equal(analysis.results.emissionsTco2e, 1.74);
  assert.equal(analysis.results.reportingPeriodEuiKwhM2, 2.9);
  assert.equal(analysis.monthly[0].electricityKwh, 1300);
  assert.equal(analysis.monthly[0].period, "2026-01");
  assert.equal(analysis.results.tariffSource, "client project input");
  assert.ok(analysis.warnings.some((item) => item.includes("not annualised")));
});

test("client deliverable excludes session rows and includes audit registers", () => {
  const values = [["2026-01", 100]];
  const manifest = {
    id: "one", sha256: "a".repeat(64), filename: "meter.csv", extension: "csv", size: 100, kind: "Tabular data", phase: "Phase 1", status: "review_required",
    facts: [], details: {}, notes: [], tables: [{ name: "data", rowCount: 1, columns: ["Month", "Usage kWh"], rows: values, sessionRows: values, includedForProject: true, mappings: [inferField("Month"), inferField("Usage kWh")], quality: { score: 100, errors: 0, warnings: 0, issues: [], granularity: "monthly" } }],
  };
  const analysis = assessClientProject([manifest], { projectName: "Review", tariffPerKwh: .5 });
  const archive = unzipSync(buildClientDeliverable([manifest], analysis, "2026-08-12T00:00:00.000Z"));
  assert.deepEqual(new Set(Object.keys(archive)), new Set(["README.txt", "project_summary.json", "audit_log.json", "source_manifest.json", "mapping_register.csv", "quality_register.csv", "monthly_baseline.csv"]));
  assert.ok(!new TextDecoder().decode(archive["source_manifest.json"]).includes("2026-01"));
  assert.equal(JSON.parse(new TextDecoder().decode(archive["audit_log.json"])).generatedAtUtc, "2026-08-12T00:00:00.000Z");
});

test("duplicate fingerprints are excluded from analysis and audit counts", () => {
  const values = [["2026-01", 100]];
  const manifest = {
    id: "duplicate", sha256: "d".repeat(64), filename: "meter.csv", extension: "csv", size: 100, kind: "Tabular data", phase: "Phase 1", status: "review_required",
    facts: [], details: {}, notes: [], tables: [{ name: "data", rowCount: 1, columns: ["Month", "Usage kWh"], rows: values, sessionRows: values, includedForProject: true, mappings: [inferField("Month"), inferField("Usage kWh")], quality: { score: 100, errors: 0, warnings: 0, issues: [], granularity: "monthly" } }],
  };
  const analysis = assessClientProject([manifest, manifest], {});
  assert.equal(analysis.results.electricityKwh, 100);
  assert.equal(analysis.controlGate.approvedFiles, 1);
  const audit = JSON.parse(new TextDecoder().decode(unzipSync(buildClientDeliverable([manifest, manifest], analysis))["audit_log.json"]));
  assert.equal(audit.events[1].recordCount, 1);
});
