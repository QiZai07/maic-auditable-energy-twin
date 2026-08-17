export const CLIENT_MAX_BYTES = 25 * 1024 * 1024;
export const CLOUD_MAX_BYTES = 3 * 1024 * 1024;
export const CLOUD_EXTENSIONS = new Set(["pdf", "png", "jpg", "jpeg"]);

export type FieldMapping = {
  source: string;
  target: string;
  unit: string;
  confidence: number;
  review: boolean;
};

export type QualityIssue = { severity: "error" | "warning"; check: string; detail: string };

export type ParsedTable = {
  name: string;
  rowCount: number;
  columns: string[];
  rows: unknown[][];
  sessionRows: unknown[][];
  includedForProject: boolean;
  mappings: FieldMapping[];
  quality: {
    score: number;
    errors: number;
    warnings: number;
    issues: QualityIssue[];
    granularity: string;
  };
};

export type ExtractedFact = {
  field: string;
  value: string | number;
  unit: string;
  source: string;
};

export type ClientManifest = {
  id: string;
  sha256?: string;
  filename: string;
  extension: string;
  size: number;
  kind: string;
  phase: string;
  status: "review_required" | "recognition_optional" | "conversion_required";
  tables: ParsedTable[];
  facts: ExtractedFact[];
  details: Record<string, unknown>;
  notes: string[];
};

export type CloudRecognition = {
  documentType: string;
  summary: string;
  facts: Array<{ field: string; value: string | number | null; unit: string; sourceLocation: string; confidence: number }>;
  equipment: Array<{ identifier: string; type: string; capacity: string | number | null; unit: string; sourceLocation: string }>;
  reviewItems: string[];
  retention: "store:false";
};

const types: Record<string, [string, string]> = {
  csv: ["Tabular data", "Phase 1"], xlsx: ["Excel workbook", "Phase 1"], xlsm: ["Excel workbook", "Phase 1"],
  pdf: ["PDF document", "Phase 2"], docx: ["Word document", "Phase 2"], png: ["Image or scan", "Phase 2"],
  jpg: ["Image or scan", "Phase 2"], jpeg: ["Image or scan", "Phase 2"], tif: ["Image or scan", "Phase 2"], tiff: ["Image or scan", "Phase 2"],
  dxf: ["CAD drawing", "Phase 3"], ifc: ["BIM model", "Phase 3"], dwg: ["CAD drawing", "Phase 3"],
};

export const fieldLibrary: Record<string, { label: string; unit: string; aliases: string[] }> = {
  timestamp: { label: "Timestamp", unit: "ISO 8601", aliases: ["timestamp", "date time", "datetime", "time", "recorded at", "reading date"] },
  billing_period: { label: "Billing period", unit: "YYYY-MM", aliases: ["billing period", "bill month", "month", "period", "billing month"] },
  meter_id: { label: "Meter identifier", unit: "text", aliases: ["meter id", "meter no", "meter number", "mpan", "account number", "point id"] },
  electricity_kwh: { label: "Electricity consumption", unit: "kWh", aliases: ["electricity kwh", "energy kwh", "consumption kwh", "usage kwh", "electricity consumption", "active energy", "kwh"] },
  cumulative_kwh: { label: "Cumulative meter reading", unit: "kWh", aliases: ["cumulative kwh", "meter reading", "total kwh", "register value", "cumulative energy"] },
  demand_kw: { label: "Electrical demand", unit: "kW", aliases: ["demand kw", "load kw", "power kw", "peak demand", "maximum demand", "active power"] },
  grid_import_kwh: { label: "Grid import", unit: "kWh", aliases: ["grid import", "import kwh", "purchased energy", "utility import"] },
  grid_export_kwh: { label: "Grid export", unit: "kWh", aliases: ["grid export", "export kwh", "exported energy"] },
  pv_generation_kwh: { label: "PV generation", unit: "kWh", aliases: ["pv generation", "solar generation", "pv energy", "photovoltaic generation", "solar kwh"] },
  tariff: { label: "Electricity tariff", unit: "currency/kWh", aliases: ["tariff", "unit rate", "price per kwh", "energy rate", "electricity price"] },
  cost: { label: "Electricity cost", unit: "currency", aliases: ["electricity cost", "energy cost", "bill amount", "cost", "charge", "total due"] },
  temperature_c: { label: "Temperature", unit: "degC", aliases: ["temperature", "temperature c", "temp c", "outdoor temperature", "dry bulb"] },
  humidity_pct: { label: "Relative humidity", unit: "%", aliases: ["humidity", "relative humidity", "rh", "humidity pct"] },
  ghi_w_m2: { label: "Global horizontal irradiance", unit: "W/m2", aliases: ["ghi", "solar irradiance", "global horizontal irradiance", "irradiance"] },
  building_area_m2: { label: "Gross floor area", unit: "m2", aliases: ["gross floor area", "floor area", "building area", "area m2", "gfa"] },
  equipment_id: { label: "Equipment identifier", unit: "text", aliases: ["equipment id", "asset id", "plant id", "device id", "tag id"] },
  equipment_type: { label: "Equipment type", unit: "text", aliases: ["equipment type", "asset type", "plant type", "device type", "category"] },
  capacity_kw: { label: "Equipment capacity", unit: "kW", aliases: ["capacity kw", "rated power", "nameplate kw", "nominal capacity", "capacity"] },
  floor: { label: "Floor or storey", unit: "text", aliases: ["floor", "storey", "story", "level"] },
  space: { label: "Space or room", unit: "text", aliases: ["space", "room", "zone", "location", "area name"] },
};

function normalise(value: unknown) {
  return String(value ?? "").trim().toLowerCase().replaceAll("²", "2").replace(/[_-]/g, " ").replace(/[^a-z0-9%]+/g, " ").trim();
}

export function inferField(source: string): FieldMapping {
  const name = normalise(source);
  const tokens = new Set(name.split(" ").filter(Boolean));
  let target = "unmapped";
  let score = 0;
  for (const [field, definition] of Object.entries(fieldLibrary)) {
    for (const alias of definition.aliases) {
      const cleanAlias = normalise(alias);
      const aliasTokens = cleanAlias.split(" ").filter(Boolean);
      let candidate = name === cleanAlias ? 1 : cleanAlias && name.includes(cleanAlias) ? 0.88 : 0;
      if (aliasTokens.length) candidate = Math.max(candidate, aliasTokens.filter((token) => tokens.has(token)).length / aliasTokens.length * 0.78);
      if (candidate > score) { target = field; score = candidate; }
    }
  }
  if (score < 0.48) return { source, target: "unmapped", unit: "", confidence: Number(score.toFixed(2)), review: true };
  return { source, target, unit: fieldLibrary[target].unit, confidence: Number(score.toFixed(2)), review: score < 0.85 };
}

function numeric(value: unknown) {
  if (typeof value === "number") return Number.isFinite(value) ? value : null;
  if (typeof value !== "string" || !value.trim()) return null;
  const parsed = Number(value.replace(/,/g, ""));
  return Number.isFinite(parsed) ? parsed : null;
}

function dateValue(value: unknown) {
  if (value instanceof Date && !Number.isNaN(value.valueOf())) return value;
  if (typeof value !== "string" && typeof value !== "number") return null;
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? null : date;
}

export function assessTable(columns: string[], rows: unknown[][], mappings = columns.map(inferField)) {
  const issues: QualityIssue[] = [];
  const seen = new Set<string>();
  let duplicates = 0;
  for (const row of rows) {
    const key = JSON.stringify(row);
    if (seen.has(key)) duplicates += 1;
    seen.add(key);
  }
  if (duplicates) issues.push({ severity: "warning", check: "Duplicate rows", detail: `${duplicates.toLocaleString()} duplicate row(s) detected.` });
  columns.forEach((column, index) => {
    const missing = rows.filter((row) => row[index] === null || row[index] === undefined || row[index] === "").length;
    if (missing) issues.push({ severity: missing / Math.max(rows.length, 1) >= .5 ? "error" : "warning", check: "Missing values", detail: `${column}: ${missing.toLocaleString()} missing (${(missing / Math.max(rows.length, 1) * 100).toFixed(1)}%).` });
  });
  for (const mapping of mappings.filter((item) => ["electricity_kwh", "demand_kw", "grid_import_kwh", "pv_generation_kwh", "cost"].includes(item.target))) {
    const index = columns.indexOf(mapping.source);
    const values = rows.map((row) => numeric(row[index])).filter((value): value is number => value !== null);
    const negative = values.filter((value) => value < 0).length;
    if (negative) issues.push({ severity: "error", check: "Negative value", detail: `${mapping.source}: ${negative} negative reading(s) require confirmation.` });
  }
  let granularity = "unknown";
  const timeMapping = mappings.find((item) => item.target === "timestamp" || item.target === "billing_period");
  if (timeMapping) {
    const index = columns.indexOf(timeMapping.source);
    const times = rows.map((row) => dateValue(row[index])).filter((value): value is Date => value !== null).map((value) => value.valueOf()).sort((a, b) => a - b);
    if (times.length >= 2) {
      const deltas = times.slice(1).map((value, i) => (value - times[i]) / 60_000).sort((a, b) => a - b);
      const median = deltas[Math.floor(deltas.length / 2)];
      granularity = median <= 20 ? "interval (15 minutes or finer)" : median <= 90 ? "hourly" : median <= 1_800 ? "daily" : median <= 50_000 ? "monthly" : "unknown";
    }
  }
  const errors = issues.filter((item) => item.severity === "error").length;
  const warnings = issues.filter((item) => item.severity === "warning").length;
  return { score: Math.max(0, 100 - errors * 18 - warnings * 5), errors, warnings, issues, granularity };
}

function table(name: string, rawRows: unknown[][]): ParsedTable {
  const firstNonEmpty = rawRows.findIndex((row) => row.some((cell) => cell !== null && cell !== undefined && cell !== ""));
  if (firstNonEmpty < 0) return { name, rowCount: 0, columns: [], rows: [], sessionRows: [], includedForProject: true, mappings: [], quality: { score: 0, errors: 1, warnings: 0, issues: [{ severity: "error", check: "Empty table", detail: "No populated cells were found." }], granularity: "unknown" } };
  const width = Math.max(...rawRows.map((row) => row.length));
  const columns = Array.from({ length: width }, (_, index) => String(rawRows[firstNonEmpty][index] ?? `column_${index + 1}`).trim() || `column_${index + 1}`);
  const rows = rawRows.slice(firstNonEmpty + 1).filter((row) => row.some((cell) => cell !== null && cell !== undefined && cell !== "")).slice(0, 100_000).map((row) => columns.map((_, index) => row[index] ?? null));
  const mappings = columns.map(inferField);
  return { name, rowCount: rows.length, columns, rows: rows.slice(0, 25), sessionRows: rows, includedForProject: true, mappings, quality: assessTable(columns, rows, mappings) };
}

function parseCsv(text: string) {
  const firstLine = text.split(/\r?\n/, 1)[0] ?? "";
  const separators = [",", ";", "\t", "|"];
  const separator = separators.sort((a, b) => firstLine.split(b).length - firstLine.split(a).length)[0];
  const rows: string[][] = [];
  let row: string[] = [], cell = "", quoted = false;
  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    if (char === '"') {
      if (quoted && text[index + 1] === '"') { cell += '"'; index += 1; } else quoted = !quoted;
    } else if (char === separator && !quoted) { row.push(cell); cell = ""; }
    else if ((char === "\n" || char === "\r") && !quoted) {
      if (char === "\r" && text[index + 1] === "\n") index += 1;
      row.push(cell); if (row.some((value) => value.length)) rows.push(row); row = []; cell = "";
    } else cell += char;
  }
  row.push(cell); if (row.some((value) => value.length)) rows.push(row);
  return { rows, separator };
}

export function extractTextFacts(text: string): ExtractedFact[] {
  const value = text.replace(/\s+/g, " ");
  const patterns: Array<[string, RegExp, string | null]> = [
    ["floor_area", /(?:gross floor area|building area|floor area|gfa)\s*[:=]?\s*([\d,.]+)\s*(m2|m²|sqm|square met(?:er|re)s?)/gi, "m2"],
    ["energy", /(?:electricity|energy|consumption|usage)\s*[:=]?\s*([\d,.]+)\s*(kwh|mwh)/gi, null],
    ["demand", /(?:peak demand|maximum demand|demand|load)\s*[:=]?\s*([\d,.]+)\s*(kw|mw)/gi, null],
    ["capacity", /(?:capacity|rated power|installed capacity)\s*[:=]?\s*([\d,.]+)\s*(kw|mw|kwp|mwp)/gi, null],
    ["tariff", /(?:tariff|unit rate|price per kwh)\s*[:=]?\s*(?:[A-Z]{3}|[$¥£€])?\s*([\d,.]+)\s*(?:[A-Z]{3}|[$¥£€])?\s*(?:\/|per)?\s*kwh/gi, "currency/kWh"],
  ];
  const facts: ExtractedFact[] = [];
  for (const [field, pattern, fixedUnit] of patterns) {
    for (const match of value.matchAll(pattern)) {
      facts.push({ field, value: Number(match[1].replaceAll(",", "")), unit: fixedUnit ?? match[2].toLowerCase(), source: value.slice(Math.max(0, match.index! - 35), Math.min(value.length, match.index! + match[0].length + 35)) });
    }
  }
  return facts.slice(0, 100);
}

function cleanName(name: string) {
  return name.split(/[\\/]/).at(-1)!.replace(/[^A-Za-z0-9._() -]/g, "_").slice(0, 160) || "upload";
}

function extensionOf(name: string) { return name.split(".").at(-1)?.toLowerCase() ?? ""; }

function byteText(bytes: Uint8Array) {
  for (const encoding of ["utf-8", "gb18030", "windows-1252"]) {
    try { return { text: new TextDecoder(encoding, { fatal: true }).decode(bytes), encoding }; } catch { /* try next */ }
  }
  throw new Error("The text encoding could not be identified safely.");
}

function checkSignature(extension: string, bytes: Uint8Array) {
  const starts = (...values: number[]) => values.every((value, index) => bytes[index] === value);
  if (extension === "pdf" && new TextDecoder().decode(bytes.slice(0, 4)) !== "%PDF") throw new Error("The PDF signature does not match its extension.");
  if (extension === "png" && !starts(0x89, 0x50, 0x4e, 0x47)) throw new Error("The PNG signature does not match its extension.");
  if (["xlsx", "xlsm", "docx"].includes(extension) && !starts(0x50, 0x4b)) throw new Error("The Office document signature does not match its extension.");
  if (extension === "dwg" && !/^AC10\d{2}$/.test(new TextDecoder().decode(bytes.slice(0, 6)))) throw new Error("The DWG signature could not be validated.");
}

export async function parseClientFile(file: File): Promise<ClientManifest> {
  const filename = cleanName(file.name);
  const extension = extensionOf(filename);
  if (!types[extension]) throw new Error("Unsupported file type.");
  if (!file.size) throw new Error("The uploaded file is empty.");
  if (file.size > CLIENT_MAX_BYTES) throw new Error("The file exceeds the 25 MB browser-session limit.");
  const buffer = await file.arrayBuffer();
  const bytes = new Uint8Array(buffer);
  const sha256 = Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", buffer))).map((value) => value.toString(16).padStart(2, "0")).join("");
  checkSignature(extension, bytes);
  const [kind, phase] = types[extension];
  const result: ClientManifest = { id: `${file.name}-${file.size}-${file.lastModified}`, sha256, filename, extension, size: file.size, kind, phase, status: "review_required", tables: [], facts: [], details: {}, notes: [] };

  if (extension === "csv") {
    const decoded = byteText(bytes);
    const csv = parseCsv(decoded.text);
    result.tables = [table("data", csv.rows)];
    result.notes.push(`Decoded as ${decoded.encoding}; delimiter ${JSON.stringify(csv.separator)}.`);
  } else if (extension === "xlsx" || extension === "xlsm") {
    const readXlsxFile = (await import("read-excel-file/browser")).default;
    const sheets = await readXlsxFile(file);
    for (const sheet of sheets.slice(0, 100)) {
      result.tables.push(table(sheet.sheet, sheet.data));
    }
    result.notes.push(`Workbook contains ${result.tables.length} sheet(s).`, extension === "xlsm" ? "Macro content was not executed; only worksheet values were read." : "Workbook values were read locally in the browser.");
  } else if (extension === "docx") {
    const mammoth = await import("mammoth/mammoth.browser");
    const extracted = await mammoth.extractRawText({ arrayBuffer: buffer });
    result.facts = extractTextFacts(extracted.value);
    result.details = { textCharacters: extracted.value.length, messages: extracted.messages.map((item) => item.message) };
    result.notes.push("Word text was extracted locally; macros and external links were not executed.");
  } else if (extension === "pdf") {
    const pdfjs = await import("pdfjs-dist/legacy/build/pdf.mjs");
    const document = await pdfjs.getDocument({ data: bytes }).promise;
    const pages: string[] = [];
    for (let page = 1; page <= Math.min(document.numPages, 250); page += 1) {
      const content = await (await document.getPage(page)).getTextContent();
      pages.push(content.items.map((item) => "str" in item ? item.str : "").join(" "));
    }
    const text = pages.join("\n");
    result.facts = extractTextFacts(text);
    result.details = { pages: document.numPages, textCharacters: text.length };
    result.notes.push(`Extracted embedded text from ${pages.filter(Boolean).length} of ${document.numPages} page(s).`);
    if (text.length < Math.max(80, document.numPages * 25)) { result.status = "recognition_optional"; result.notes.push("Little embedded text was found. Optional document recognition may help after explicit consent."); }
  } else if (["png", "jpg", "jpeg", "tif", "tiff"].includes(extension)) {
    result.status = "recognition_optional";
    result.details = { mimeType: file.type || "unknown" };
    result.notes.push("Image validated locally. Optional document recognition requires explicit consent.");
  } else if (extension === "dxf") {
    const DxfParser = (await import("dxf-parser")).default;
    const decoded = byteText(bytes);
    const drawing = new DxfParser().parseSync(decoded.text);
    const entityCounts: Record<string, number> = {}, layers = new Set<string>(), blocks = new Set<string>(), labels: string[] = [];
    for (const entity of drawing?.entities ?? []) {
      entityCounts[entity.type] = (entityCounts[entity.type] ?? 0) + 1;
      if (entity.layer) layers.add(entity.layer);
      const value = "text" in entity ? String(entity.text) : "name" in entity && entity.type === "INSERT" ? String(entity.name) : "";
      if (value) { labels.push(value); if (entity.type === "INSERT") blocks.add(value); }
    }
    result.facts = extractTextFacts(labels.join("\n"));
    result.details = { header: drawing?.header ?? {}, entityCounts, layers: [...layers].slice(0, 250), blockReferences: [...blocks].slice(0, 250), textLabels: labels.slice(0, 250) };
    result.notes.push("DXF entities, layers, blocks and labels were extracted locally.");
  } else if (extension === "ifc") {
    const decoded = byteText(bytes);
    if (!decoded.text.slice(0, 1_000).toUpperCase().includes("ISO-10303-21") || !decoded.text.slice(0, 5_000).toUpperCase().includes("IFC")) throw new Error("The IFC header could not be validated.");
    const entityCounts: Record<string, number> = {};
    for (const match of decoded.text.matchAll(/=\s*(IFC[A-Z0-9_]+)\s*\(/gi)) entityCounts[match[1].toUpperCase()] = (entityCounts[match[1].toUpperCase()] ?? 0) + 1;
    result.details = { schema: decoded.text.match(/FILE_SCHEMA\s*\(\s*\(\s*'([^']+)'/i)?.[1] ?? "unknown", entityCount: Object.values(entityCounts).reduce((sum, count) => sum + count, 0), buildings: entityCounts.IFCBUILDING ?? 0, storeys: entityCounts.IFCBUILDINGSTOREY ?? 0, spaces: entityCounts.IFCSPACE ?? 0, entityCounts };
    result.notes.push("IFC STEP entities were counted locally; geometry is not recalculated in this lightweight review.");
  } else if (extension === "dwg") {
    result.status = "conversion_required";
    result.details = { dwgSignature: new TextDecoder().decode(bytes.slice(0, 6)) };
    result.notes.push("Browser parsing cannot safely decode native DWG. Export to DXF, or use the Streamlit workstation with a configured ODA File Converter / LibreDWG adapter.");
  }
  return result;
}

export function assessClientReadiness(manifests: ClientManifest[]) {
  const mappings = manifests.flatMap((item) => item.tables.flatMap((source) => source.mappings));
  const targets = new Set(mappings.filter((item) => item.target !== "unmapped").map((item) => item.target));
  const factTypes = new Set(manifests.flatMap((item) => item.facts.map((fact) => fact.field)));
  const monthly = manifests.some((item) => item.tables.some((source) => source.rowCount >= 6 && source.mappings.some((mapping) => ["billing_period", "timestamp"].includes(mapping.target)) && source.mappings.some((mapping) => ["electricity_kwh", "cumulative_kwh", "grid_import_kwh"].includes(mapping.target))));
  const interval = manifests.some((item) => item.tables.some((source) => source.rowCount >= 24 && /interval|hourly/.test(source.quality.granularity)));
  const calibrationHistory = manifests.some((item) => item.tables.some((source) => source.rowCount >= 168 && /interval|hourly/.test(source.quality.granularity)));
  const weather = ["temperature_c", "humidity_pct", "ghi_w_m2"].some((item) => targets.has(item));
  const assets = ["equipment_id", "equipment_type", "capacity_kw"].some((item) => targets.has(item));
  const building = targets.has("building_area_m2") || factTypes.has("floor_area") || manifests.some((item) => Number(item.details.spaces ?? 0) > 0);
  const capabilities = [
    { name: "Monthly baseline and EUI", ready: monthly && building, needs: "Dated energy plus confirmed floor area" },
    { name: "Tariff and bill screening", ready: monthly && (targets.has("tariff") || targets.has("cost") || factTypes.has("tariff")), needs: "Energy plus tariff or bill amount" },
    { name: "Interval anomaly detection", ready: interval, needs: "Hourly or finer energy or demand" },
    { name: "PV performance assessment", ready: targets.has("pv_generation_kwh") && (weather || targets.has("ghi_w_m2")), needs: "PV generation plus irradiance or benchmark" },
    { name: "Operational calibration", ready: calibrationHistory && weather, needs: "At least one representative week of aligned hourly-or-finer load and weather" },
    { name: "Equipment and space digital twin", ready: assets && building, needs: "Equipment register plus space/building data" },
  ];
  return { score: Math.round(capabilities.filter((item) => item.ready).length / capabilities.length * 100), capabilities, path: interval ? "Calibrate with interval data" : monthly ? "Establish the monthly baseline first" : "Complete mapping and supply a dated energy series" };
}

export function downloadMapping(manifest: ClientManifest, confirmed: boolean) {
  const payload = { schemaVersion: "irene-client-data-v1", source: { filename: manifest.filename, size: manifest.size }, tables: manifest.tables.map((source) => ({ name: source.name, mappings: source.mappings.map((mapping) => ({ ...mapping, confirmed })) })), facts: manifest.facts.map((fact) => ({ ...fact, confirmed })), approvedForModel: confirmed };
  const url = URL.createObjectURL(new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" }));
  const anchor = document.createElement("a"); anchor.href = url; anchor.download = `${manifest.filename.replace(/\.[^.]+$/, "")}_irene_mapping.json`; anchor.click(); URL.revokeObjectURL(url);
}

export async function recogniseClientDocument(file: File): Promise<CloudRecognition> {
  if (!CLOUD_EXTENSIONS.has(extensionOf(file.name))) throw new Error("Cloud recognition accepts PDF, PNG and JPEG only.");
  if (file.size > CLOUD_MAX_BYTES) throw new Error("The Vercel recognition limit is 3 MB per file; use Streamlit locally for larger documents.");
  const form = new FormData(); form.set("file", file);
  const response = await fetch("/api/onboarding/recognise", { method: "POST", body: form });
  const body = await response.json().catch(() => ({})) as CloudRecognition & { error?: string };
  if (!response.ok) {
    const friendlyErrors: Record<string, string> = {
      RECOGNITION_HTTP_429: "Document recognition is connected, but the current API quota or rate limit does not allow this request. Check platform billing and retry.",
      RECOGNITION_NOT_CONFIGURED: "Document recognition is not configured for this deployment.",
      FILE_TOO_LARGE: "This file exceeds the 3 MB Vercel recognition limit. Use Streamlit locally or split the document.",
      FILE_SIZE_NOT_ALLOWED: "This file exceeds the 3 MB Vercel recognition limit. Use Streamlit locally or split the document.",
      FILE_TYPE_NOT_ALLOWED: "Cloud recognition accepts PDF, PNG and JPEG only.",
      FILE_SIGNATURE_MISMATCH: "The file signature does not match the selected file type.",
      RATE_LIMITED: "Too many recognition requests were received. Wait one minute and retry.",
    };
    throw new Error(friendlyErrors[body.error ?? ""] ?? "Document recognition is temporarily unavailable. The file remains local and outside the model pipeline.");
  }
  return body;
}
