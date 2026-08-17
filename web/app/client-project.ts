import { strToU8, zipSync } from "fflate";
import type { ClientManifest, ParsedTable } from "./client-onboarding";

export type ClientProjectProfile = {
  projectName: string;
  clientReference: string;
  siteName: string;
  countryOrRegion: string;
  currency: string;
  tariffPerKwh: number | null;
  gridEmissionFactorKgCo2eKwh: number | null;
  grossFloorAreaM2: number | null;
};

type MonthlyResult = {
  period: string;
  electricityKwh?: number;
  gridImportKwh?: number;
  gridExportKwh?: number;
  pvGenerationKwh?: number;
  cost?: number;
  calculatedCost?: number;
  emissionsTco2e?: number;
};

export type ClientProjectAnalysis = {
  schemaVersion: "irene-client-project-v1";
  project: ClientProjectProfile;
  controlGate: { approvedFiles: number; duplicateFilesExcluded: string[] };
  coverage: { start: string | null; end: string | null; days: number | null; datedMonths: number };
  results: {
    electricityKwh: number | null;
    gridImportKwh: number | null;
    gridExportKwh: number | null;
    pvGenerationKwh: number | null;
    peakDemandKw: number | null;
    observedCost: number | null;
    calculatedCost: number | null;
    reportingCost: number | null;
    costBasis: string;
    tariffPerKwh: number | null;
    tariffSource: string;
    gridEmissionFactorKgCo2eKwh: number | null;
    emissionsTco2e: number | null;
    grossFloorAreaM2: number | null;
    areaSource: string;
    reportingPeriodEuiKwhM2: number | null;
    qualityScore: number | null;
  };
  monthly: MonthlyResult[];
  sourceTables: Array<{ filename: string; table: string; rowCount: number; qualityScore: number }>;
  warnings: string[];
  evidenceBoundary: string;
};

const energyFields = ["electricity_kwh", "grid_import_kwh", "grid_export_kwh", "pv_generation_kwh"] as const;
type EnergyField = typeof energyFields[number];

function finite(value: unknown) {
  if (value === null || value === undefined || value === "") return null;
  const number = typeof value === "number" ? value : Number(String(value).replace(/,/g, ""));
  return Number.isFinite(number) ? number : null;
}

function positive(value: unknown) {
  const number = finite(value);
  return number !== null && number > 0 ? number : null;
}

function cleanText(value: unknown, fallback: string) {
  return [...String(value ?? "")].map((character) => {
    const code = character.codePointAt(0) ?? 0;
    return code < 32 || code === 127 ? " " : character;
  }).join("").trim().slice(0, 160) || fallback;
}

function normaliseProfile(profile: Partial<ClientProjectProfile>): ClientProjectProfile {
  return {
    projectName: cleanText(profile.projectName, "Client energy review"),
    clientReference: cleanText(profile.clientReference, "Not supplied"),
    siteName: cleanText(profile.siteName, "Not supplied"),
    countryOrRegion: cleanText(profile.countryOrRegion, "Not supplied"),
    currency: cleanText(profile.currency, "Local currency").slice(0, 16),
    tariffPerKwh: positive(profile.tariffPerKwh),
    gridEmissionFactorKgCo2eKwh: positive(profile.gridEmissionFactorKgCo2eKwh),
    grossFloorAreaM2: positive(profile.grossFloorAreaM2),
  };
}

function unitMultiplier(field: string, unit: string) {
  const clean = unit.toLowerCase().replace(/[^a-z0-9]+/g, "");
  if ([...energyFields, "cumulative_kwh"].includes(field as EnergyField)) {
    if (clean.startsWith("mwh")) return 1_000;
    if (clean.startsWith("wh") && !clean.startsWith("kwh")) return .001;
  }
  if (["demand_kw", "capacity_kw"].includes(field)) {
    if (clean.startsWith("mw")) return 1_000;
    if (clean.startsWith("w") && !clean.startsWith("kw")) return .001;
  }
  if (field === "building_area_m2" && ["ft2", "sqft", "squarefeet"].some((item) => clean.includes(item))) return .09290304;
  return 1;
}

function dateValue(value: unknown) {
  if (value instanceof Date && !Number.isNaN(value.valueOf())) return value;
  if (typeof value !== "string" && typeof value !== "number") return null;
  if (typeof value === "string") {
    const match = value.trim().match(/^(\d{4})-(\d{1,2})(?:-(\d{1,2}))?(?:[ T](\d{1,2}):?(\d{1,2})?(?::?(\d{1,2}))?)?$/);
    if (match) {
      const date = new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3] ?? 1), Number(match[4] ?? 0), Number(match[5] ?? 0), Number(match[6] ?? 0)));
      return Number.isNaN(date.valueOf()) ? null : date;
    }
  }
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? null : date;
}

function monthKey(date: Date | null) {
  return date ? `${date.getUTCFullYear()}-${String(date.getUTCMonth() + 1).padStart(2, "0")}` : "undated";
}

function analyseTable(table: ParsedTable) {
  const rows = table.sessionRows ?? table.rows;
  const mapped = new Map(table.mappings.filter((item) => item.target !== "unmapped").map((item) => [item.target, item]));
  const columnIndex = (field: string) => {
    const mapping = mapped.get(field);
    return mapping ? table.columns.indexOf(mapping.source) : -1;
  };
  const values = (field: string) => {
    const index = columnIndex(field);
    if (index < 0) return null;
    const multiplier = unitMultiplier(field, mapped.get(field)?.unit ?? "");
    return rows.map((row) => {
      const number = finite(row[index]);
      return number === null ? null : number * multiplier;
    });
  };
  const timeIndex = Math.max(columnIndex("timestamp"), columnIndex("billing_period"));
  const times = rows.map((row) => timeIndex >= 0 ? dateValue(row[timeIndex]) : null);
  const series: Record<string, Array<number | null> | null> = Object.fromEntries([...energyFields, "demand_kw", "cost", "tariff", "building_area_m2"].map((field) => [field, values(field)]));
  let energySource: string | null = series.electricity_kwh ? "electricity_kwh" : series.grid_import_kwh ? "grid_import_kwh" : null;
  if (!series.electricity_kwh && series.grid_import_kwh) series.electricity_kwh = series.grid_import_kwh;
  if (!series.electricity_kwh) {
    const readings = values("cumulative_kwh");
    if (readings) {
      const meterIndex = columnIndex("meter_id");
      const groups = new Map<string, number[]>();
      rows.forEach((row, index) => {
        const key = meterIndex >= 0 ? String(row[meterIndex] ?? "") : "__single_meter__";
        groups.set(key, [...(groups.get(key) ?? []), index]);
      });
      const deltas: Array<number | null> = Array(rows.length).fill(null);
      for (const indexes of groups.values()) {
        indexes.sort((a, b) => (times[a]?.valueOf() ?? a) - (times[b]?.valueOf() ?? b));
        for (let index = 1; index < indexes.length; index += 1) {
          const current = readings[indexes[index]], previous = readings[indexes[index - 1]];
          if (current !== null && previous !== null && current - previous >= 0) deltas[indexes[index]] = current - previous;
        }
      }
      series.electricity_kwh = deltas;
      energySource = "cumulative_kwh";
    }
  }
  const monthly = new Map<string, Record<string, number>>();
  [...energyFields, "cost"].forEach((field) => {
    series[field]?.forEach((value, index) => {
      if (value === null || value < 0) return;
      const period = monthKey(times[index]);
      const item = monthly.get(period) ?? {};
      item[field] = (item[field] ?? 0) + value;
      monthly.set(period, item);
    });
  });
  const total = (field: string) => {
    const clean = series[field]?.filter((value): value is number => value !== null && value >= 0) ?? [];
    return clean.length ? clean.reduce((sum, value) => sum + value, 0) : null;
  };
  const max = (field: string) => {
    const clean = series[field]?.filter((value): value is number => value !== null && value > 0) ?? [];
    return clean.length ? Math.max(...clean) : null;
  };
  const median = (field: string) => {
    const clean = (series[field]?.filter((value): value is number => value !== null && value > 0) ?? []).sort((a, b) => a - b);
    return clean.length ? clean[Math.floor(clean.length / 2)] : null;
  };
  const validDates = times.filter((value): value is Date => value !== null).sort((a, b) => a.valueOf() - b.valueOf());
  return {
    energySource,
    totals: Object.fromEntries([...energyFields, "cost"].map((field) => [field, total(field)])),
    peakDemandKw: max("demand_kw"), medianTariffPerKwh: median("tariff"), grossFloorAreaM2: max("building_area_m2"),
    coverageStart: validDates.at(0)?.toISOString() ?? null, coverageEnd: validDates.at(-1)?.toISOString() ?? null,
    monthly: [...monthly.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([period, item]) => ({ period, ...item })),
  };
}

export function assessClientProject(manifests: ClientManifest[], rawProfile: Partial<ClientProjectProfile>): ClientProjectAnalysis {
  const project = normaliseProfile(rawProfile);
  const seen = new Set<string>(), duplicates: string[] = [], unique: ClientManifest[] = [];
  for (const manifest of manifests) {
    const key = manifest.sha256 ?? manifest.id;
    if (seen.has(key)) duplicates.push(manifest.filename); else { seen.add(key); unique.push(manifest); }
  }
  const tableResults = unique.flatMap((manifest) => manifest.tables.filter((table) => table.includedForProject !== false).map((table) => ({ filename: manifest.filename, table: table.name, rowCount: table.rowCount, qualityScore: table.quality.score, analysis: analyseTable(table) })));
  const monthly = new Map<string, Record<string, number>>();
  for (const item of tableResults) for (const row of item.analysis.monthly) {
    const target = monthly.get(row.period) ?? {};
    Object.entries(row).forEach(([field, value]) => { if (field !== "period" && typeof value === "number") target[field] = (target[field] ?? 0) + value; });
    monthly.set(row.period, target);
  }
  const sumMetric = (field: string) => {
    const values = tableResults.map((item) => finite(item.analysis.totals[field])).filter((value): value is number => value !== null);
    return values.length ? values.reduce((sum, value) => sum + value, 0) : null;
  };
  const electricity = sumMetric("electricity_kwh"), observedCost = sumMetric("cost");
  const factNumber = (field: string) => unique.flatMap((item) => item.facts).filter((fact) => fact.field === field).map((fact) => positive(fact.value)).filter((value): value is number => value !== null).sort((a, b) => b - a)[0] ?? null;
  const tableTariff = tableResults.map((item) => positive(item.analysis.medianTariffPerKwh)).find((value) => value !== null) ?? null;
  const tariff = project.tariffPerKwh ?? tableTariff ?? factNumber("tariff");
  const tableAreas = tableResults.map((item) => positive(item.analysis.grossFloorAreaM2)).filter((value): value is number => value !== null);
  const area = project.grossFloorAreaM2 ?? (tableAreas.length ? Math.max(...tableAreas) : null) ?? factNumber("floor_area");
  const dates = tableResults.flatMap((item) => [item.analysis.coverageStart, item.analysis.coverageEnd]).filter((value): value is string => Boolean(value)).map((value) => new Date(value));
  const start = dates.length ? new Date(Math.min(...dates.map((value) => value.valueOf()))) : null;
  const end = dates.length ? new Date(Math.max(...dates.map((value) => value.valueOf()))) : null;
  const days = start && end ? Math.max(1, Math.floor((end.valueOf() - start.valueOf()) / 86_400_000) + 1) : null;
  const datedMonths = [...monthly.keys()].filter((period) => period !== "undated").length;
  const calculatedCost = electricity !== null && tariff !== null ? electricity * tariff : null;
  const reportingCost = observedCost ?? calculatedCost;
  const factor = project.gridEmissionFactorKgCo2eKwh;
  const monthlyRows: MonthlyResult[] = [...monthly.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([period, row]) => ({
    period, electricityKwh: row.electricity_kwh, gridImportKwh: row.grid_import_kwh, gridExportKwh: row.grid_export_kwh,
    pvGenerationKwh: row.pv_generation_kwh, cost: row.cost,
    calculatedCost: row.electricity_kwh !== undefined && tariff !== null ? row.electricity_kwh * tariff : undefined,
    emissionsTco2e: row.electricity_kwh !== undefined && factor !== null ? row.electricity_kwh * factor / 1_000 : undefined,
  }));
  const rowWeight = tableResults.reduce((sum, item) => sum + Math.max(1, item.rowCount), 0);
  const qualityScore = rowWeight ? Math.round(tableResults.reduce((sum, item) => sum + item.qualityScore * Math.max(1, item.rowCount), 0) / rowWeight) : null;
  const warnings: string[] = [];
  if (!unique.length) warnings.push("No client file has passed the human confirmation gate.");
  if (electricity === null) warnings.push("No confirmed electricity-consumption series is available.");
  if (electricity !== null && !datedMonths) warnings.push("Energy is available, but no valid reporting date was mapped.");
  if (electricity !== null && tariff === null && observedCost === null) warnings.push("Supply a confirmed tariff or bill amount to calculate reporting-period cost.");
  if (electricity !== null && factor === null) warnings.push("Supply the applicable grid emission factor to calculate operational emissions.");
  if (electricity !== null && area === null) warnings.push("Supply confirmed gross floor area to calculate reporting-period EUI.");
  if (days !== null && days < 330) warnings.push("Coverage is shorter than 330 days; results are reporting-period totals and are not annualised.");
  if (duplicates.length) warnings.push(`${duplicates.length} duplicate file(s) were excluded using their file fingerprint.`);
  return {
    schemaVersion: "irene-client-project-v1", project,
    controlGate: { approvedFiles: unique.length, duplicateFilesExcluded: duplicates },
    coverage: { start: start?.toISOString() ?? null, end: end?.toISOString() ?? null, days, datedMonths },
    results: {
      electricityKwh: electricity, gridImportKwh: sumMetric("grid_import_kwh"), gridExportKwh: sumMetric("grid_export_kwh"), pvGenerationKwh: sumMetric("pv_generation_kwh"),
      peakDemandKw: tableResults.map((item) => positive(item.analysis.peakDemandKw)).filter((value): value is number => value !== null).sort((a, b) => b - a)[0] ?? null,
      observedCost, calculatedCost, reportingCost, costBasis: observedCost !== null ? "measured bill amount" : calculatedCost !== null ? "energy × confirmed tariff" : "unavailable",
      tariffPerKwh: tariff, tariffSource: project.tariffPerKwh !== null ? "client project input" : tariff !== null ? "confirmed file evidence" : "not supplied",
      gridEmissionFactorKgCo2eKwh: factor, emissionsTco2e: electricity !== null && factor !== null ? electricity * factor / 1_000 : null,
      grossFloorAreaM2: area, areaSource: project.grossFloorAreaM2 !== null ? "client project input" : area !== null ? "confirmed file evidence" : "not supplied",
      reportingPeriodEuiKwhM2: electricity !== null && area !== null ? electricity / area : null, qualityScore,
    },
    monthly: monthlyRows,
    sourceTables: tableResults.map((item) => ({ filename: item.filename, table: item.table, rowCount: item.rowCount, qualityScore: item.qualityScore })),
    warnings,
    evidenceBoundary: "Calculated results use only human-confirmed mappings and files. Tariff, emission factor and area are labelled by source. Raw uploads are not included in the deliverable pack.",
  };
}

function csv(rows: Array<Record<string, unknown>>, columns: string[]) {
  const escape = (value: unknown) => `"${String(value ?? "").replaceAll('"', '""')}"`;
  return [columns.map(escape).join(","), ...rows.map((row) => columns.map((column) => escape(row[column])).join(","))].join("\r\n");
}

export function buildClientDeliverable(manifests: ClientManifest[], analysis: ClientProjectAnalysis, generatedAt = new Date().toISOString()) {
  const seen = new Set<string>();
  const files = manifests.filter((manifest) => {
    const key = manifest.sha256 ?? manifest.id;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
  const mappings = files.flatMap((manifest) => manifest.tables.flatMap((table) => table.mappings.map((mapping) => ({ filename: manifest.filename, sha256: manifest.sha256, table: table.name, sourceField: mapping.source, modelField: mapping.target, confirmedUnit: mapping.unit, confirmed: true, includedForProject: table.includedForProject }))));
  const quality = files.flatMap((manifest) => manifest.tables.map((table) => ({ filename: manifest.filename, table: table.name, rows: table.rowCount, score: table.quality.score, errors: table.quality.errors, warnings: table.quality.warnings, granularity: table.quality.granularity, includedForProject: table.includedForProject })));
  const sources = files.map((manifest) => ({ filename: manifest.filename, sha256: manifest.sha256, kind: manifest.kind, phase: manifest.phase, status: manifest.status, tables: manifest.tables.map((table) => ({ name: table.name, rowCount: table.rowCount, includedForProject: table.includedForProject, quality: table.quality, mappings: table.mappings })) }));
  const audit = { schemaVersion: analysis.schemaVersion, generatedAtUtc: generatedAt, events: [{ sequence: 1, event: "project_profile_reviewed", recordCount: 1 }, { sequence: 2, event: "source_files_confirmed", recordCount: files.length }, { sequence: 3, event: "deterministic_project_analysis_completed", recordCount: analysis.sourceTables.length }, { sequence: 4, event: "deliverable_pack_created", recordCount: 1 }], fileFingerprints: files.map((item) => ({ filename: item.filename, sha256: item.sha256 })), controlGate: analysis.controlGate, evidenceBoundary: analysis.evidenceBoundary };
  const readme = "IRENE CLIENT PROJECT DELIVERABLE\n\nThis pack records confirmed mappings, quality, reporting-period results and the audit sequence.\nIt does not contain raw client uploads. Reconcile each SHA-256 fingerprint with the client-controlled source file before relying on results.\nResults are not annualised when confirmed coverage is shorter than 330 days. Procurement and operational decisions require client review.\n";
  return zipSync({
    "README.txt": strToU8(readme),
    "project_summary.json": strToU8(JSON.stringify(analysis, null, 2)),
    "audit_log.json": strToU8(JSON.stringify(audit, null, 2)),
    "source_manifest.json": strToU8(JSON.stringify(sources, null, 2)),
    "mapping_register.csv": strToU8(csv(mappings, ["filename", "sha256", "table", "sourceField", "modelField", "confirmedUnit", "confirmed", "includedForProject"])),
    "quality_register.csv": strToU8(csv(quality, ["filename", "table", "rows", "score", "errors", "warnings", "granularity", "includedForProject"])),
    "monthly_baseline.csv": strToU8(csv(analysis.monthly as Array<Record<string, unknown>>, ["period", "electricityKwh", "gridImportKwh", "gridExportKwh", "pvGenerationKwh", "cost", "calculatedCost", "emissionsTco2e"])),
  }, { level: 6 });
}

export function downloadClientDeliverable(manifests: ClientManifest[], analysis: ClientProjectAnalysis) {
  const bytes = buildClientDeliverable(manifests, analysis);
  const url = URL.createObjectURL(new Blob([bytes as Uint8Array<ArrayBuffer>], { type: "application/zip" }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "irene_client_project_deliverable.zip";
  anchor.click();
  URL.revokeObjectURL(url);
}
