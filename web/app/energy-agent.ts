export type AgentResponse = {
  intent: string;
  intents: string[];
  tool: string;
  title: string;
  answer: string;
  evidence: string;
  sources: string[];
  nextSteps: string[];
  confidence: string;
  planSteps: string[];
  calculations: string[];
  followUps: string[];
  modelMode: string;
  routeConfidence: number;
  decisionReadiness: string;
  matchedConcepts: string[];
  warnings: string[];
  engine?: "local" | "openai" | "fallback";
  provider?: string;
  usage?: { inputTokens: number; outputTokens: number; totalTokens: number };
  toolCallCount?: number;
  fallbackReason?: string;
};

export type ToolResult = {
  intent: string;
  tool: string;
  title: string;
  body: string;
  evidence: string;
  sources: string[];
  actions: string[];
  calculations?: string[];
};

type WhatIf = { tariff: number; savingFactor: number; capex: number; active: boolean; warnings: string[] };

const facts = {
  annual: 345676.69, hvac: 100265.61, hvacShare: 29.01, area: 6231.26, eui: 55.47, tariff: 0.538,
  pvCapacity: 106.14, pvGeneration: 126233.50, currentGrid: 230970.24, selfSufficiency: 33.18, pvSelfUse: 90.87,
  comboSaved: 41581.69, comboCapex: 62000, comboCarbon: 30.77,
  lossAwareGrid: 224486.41, naiveGrid: 233924.17, gridReduction: 4.03, batteryReduction: 91.73,
} as const;

const scenarios = [
  { name: "Comfort-constrained HVAC optimisation", saved: 7158.82, capex: 8000 },
  { name: "HVAC operating-hours optimisation", saved: 5011.17, capex: 12000 },
  { name: "LED lighting retrofit", saved: 19632.89, capex: 45000 },
  { name: "Plug-load and standby management", saved: 9778.82, capex: 18000 },
  { name: "Combined package", saved: 41581.69, capex: 62000 },
] as const;

export const quickPrompts = [
  "If the electricity tariff rises by 20%, what is the combined package payback?",
  "Which measure pays back fastest, and which saves the most energy?",
  "Why is October 2024 anomalous, and can it still support annual analysis?",
  "How do installed PV and future storage affect grid imports?",
  "Which three missing datasets should be collected first to improve confidence?",
  "Which decisions can this model support, and which can it not support?",
  "What should the next model upgrade be, and why is a new algorithm alone insufficient?",
] as const;

const profiles: Record<string, { examples: string[]; signals: string[] }> = {
  energy_baseline: {
    examples: ["how much electricity does the building use each year", "what is the overall energy performance", "what is the energy use intensity", "what share is HVAC", "annual electricity cost baseline"],
    signals: ["electricity", "energy", "consumption", "eui", "hvac", "baseline", "annual", "year", "area", "bill", "cost"],
  },
  meter_anomaly: {
    examples: ["why is October suddenly so low", "was the meter faulty", "does November include October", "how is the anomalous month handled", "aggregate meter anomaly"],
    signals: ["october", "2024-10", "anomaly", "anomalous", "fault", "meter", "missing reading", "impute"],
  },
  scenario_roi: {
    examples: ["which retrofit is most worthwhile", "how long is the payback", "recalculate if the tariff changes", "compare all energy-efficiency measures", "how much cost and carbon can be saved"],
    signals: ["saving", "savings", "payback", "roi", "investment", "retrofit", "carbon", "emissions", "scenario", "measure", "priority", "tariff", "capex"],
  },
  pv_status: {
    examples: ["how much electricity did rooftop solar generate", "how much load can PV cover", "what is the self-consumption ratio", "where is the grid connection point", "what renewable energy is installed"],
    signals: ["pv", "photovoltaic", "solar", "grid connection", "self-consumption", "self-sufficiency", "export", "generation", "renewable"],
  },
  storage_sandbox: {
    examples: ["would a battery add value", "how could storage reduce grid imports", "compare two battery-dispatch strategies", "soc and battery losses", "future pv and storage scenario"],
    signals: ["storage", "battery", "loss-aware", "loss aware", "soc", "charge", "charging", "discharge", "dispatch"],
  },
  data_gap: {
    examples: ["what should be collected first to improve accuracy", "which site data are still missing", "what can be done without hourly data", "how should the model be calibrated", "are substitute data reliable"],
    signals: ["missing", "gap", "need", "collect", "collection", "substitute", "estimate", "estimated", "accuracy", "data", "validation"],
  },
  comfort_schedule: {
    examples: ["when is the teaching building open", "will optimisation compromise comfort", "what temperature and humidity ranges are used", "what is the carbon-dioxide limit", "how is the operating calendar defined"],
    signals: ["open", "opening", "close", "closing", "comfort", "temperature", "humidity", "co2", "carbon dioxide", "classroom", "schedule", "hours"],
  },
  model_governance: {
    examples: ["are the model results trustworthy", "which data are measured and which are simulated", "was the algorithm validated", "can this value support procurement", "model boundaries and evidence classes"],
    signals: ["model", "trust", "confidence", "validate", "validation", "calibrate", "measured", "derived", "assumed", "evidence", "ai", "boundary", "decision", "procurement"],
  },
  model_improvement: {
    examples: ["how can the model be improved", "what should the next version upgrade first", "how can hourly accuracy improve", "should data or the algorithm change first", "model improvement roadmap"],
    signals: ["model improvement", "model upgrade", "improve model", "upgrade model", "next version", "improve accuracy", "roadmap", "algorithm upgrade", "optimise model", "optimize model"],
  },
};

const compoundMarkers = ["and", "also", "together", "respectively", "versus", "vs", "/"];
const decisionReadiness: Record<string, string> = {
  energy_baseline: "Suitable for annual analysis", meter_anomaly: "Suitable for annual analysis; anomalous-month diagnosis is limited", scenario_roi: "Scenario screening",
  pv_status: "Current-state interpretation; hourly relationships require calibration", storage_sandbox: "Technology sandbox; not procurement-ready", data_gap: "Data-collection planning",
  comfort_schedule: "Constraint testing; not a measured comfort conclusion", model_governance: "Governance guidance", model_improvement: "Upgrade-roadmap planning",
};

const followUps: Record<string, string[]> = {
  energy_baseline: ["If the tariff rises by 20%, what will the annual electricity cost be?", "Which HVAC end use should be investigated first?"],
  meter_anomaly: ["Does this anomaly affect the annual saving rate?", "If October must be estimated, what boundary should be applied?"],
  scenario_roi: ["If the tariff falls by 10%, compare every measure again.", "What if the combined-package CAPEX becomes CNY 80,000?"],
  pv_status: ["What share of annual use does PV generate, and why is it not the self-sufficiency ratio?", "How much further could storage reduce grid imports?"],
  storage_sandbox: ["Why does the loss-aware strategy outperform the rule-based strategy?", "Which data are required before investing in storage?"],
  data_gap: ["If only one dataset can be collected, which should it be?", "Which conclusions would each dataset change?"],
  comfort_schedule: ["How can short-term monitoring validate the comfort proxy?", "What would change if opening hours were reduced by one hour?"],
  model_governance: ["Which conclusion is currently the most mature?", "How can the model become procurement-ready?"],
  model_improvement: ["If only one dataset can be added, what should be collected first?", "Which site-error metrics should be used after the upgrade?"],
};

const normalize = (text: string) => text.toLowerCase().replace(/[^0-9a-z\u4e00-\u9fff%.-]+/g, "");
const genericFeatures = new Set(["how", "what", "which", "this", "that", "is", "are", "does", "do", "can", "could", "would"]);

function features(text: string) {
  const value = normalize(text);
  const result = new Set<string>();
  for (const size of [2, 3]) for (let index = 0; index <= value.length - size; index += 1) result.add(value.slice(index, index + size));
  for (const token of value.match(/[a-z]+|\d+(?:\.\d+)?%?/g) ?? []) result.add(token);
  for (const token of genericFeatures) result.delete(token);
  return result;
}

function cosine(left: Set<string>, right: Set<string>) {
  if (!left.size || !right.size) return 0;
  let overlap = 0;
  for (const item of left) if (right.has(item)) overlap += 1;
  return overlap / Math.sqrt(left.size * right.size);
}

function semanticScores(text: string) {
  const query = features(text);
  const normalized = normalize(text);
  return Object.fromEntries(Object.entries(profiles).map(([intent, profile]) => {
    const semantic = Math.max(...profile.examples.map((example) => cosine(query, features(example))));
    const hits = profile.signals.filter((signal) => normalized.includes(normalize(signal))).length;
    return [intent, Math.min(1, semantic * 1.45 + Math.min(.72, hits * .24))];
  })) as Record<string, number>;
}

function directSignalHits(text: string) {
  const value = normalize(text);
  return Object.fromEntries(Object.entries(profiles).map(([intent, profile]) => [
    intent, profile.signals.filter((signal) => value.includes(normalize(signal))),
  ])) as Record<string, string[]>;
}

function route(question: string, history: string[]) {
  const historyText = history.slice(-3).join(" ");
  const contextual = Boolean(historyText) && normalize(question).length <= 80 && ["then", "what if", "instead", "increase", "decrease", "raise", "lower", "again", "that", "previous"].some((marker) => normalize(question).includes(normalize(marker)));
  const routingText = contextual ? `${historyText} ${question}` : question;
  const scores = semanticScores(routingText);
  const direct = directSignalHits(routingText);
  const ordered = Object.keys(scores).sort((a, b) => direct[b].length - direct[a].length || scores[b] - scores[a]);
  const top = scores[ordered[0]];
  if (top < .20 || (!Object.values(direct).some((hits) => hits.length) && top < .45)) return { intents: [] as string[], scores, contextual, historyText };
  const compound = compoundMarkers.some((marker) => question.includes(marker));
  const intents = compound
    ? ordered.filter((intent) => direct[intent].length && scores[intent] >= .20).slice(0, 3)
    : [ordered[0]];
  return { intents: intents.length ? intents : [ordered[0]], scores, contextual, historyText };
}

function percentageChange(text: string, subjects: string[]) {
  const group = subjects.join("|");
  const up = text.match(new RegExp(`(?:${group})[^.;,]{0,30}?(?:rise|rises|increase|increases|go up|higher|raised?)\\s*(?:by\\s*)?(\\d+(?:\\.\\d+)?)\\s*%`, "i"));
  const down = text.match(new RegExp(`(?:${group})[^.;,]{0,30}?(?:fall|falls|decrease|decreases|drop|drops|go down|lower|reduced?)\\s*(?:by\\s*)?(\\d+(?:\\.\\d+)?)\\s*%`, "i"));
  if (up) return Number(up[1]) / 100;
  if (down) return -Number(down[1]) / 100;
  return null;
}

function absoluteTariff(text: string) {
  const patterns = [/(?:tariff|electricity price|energy price)[^.;,]{0,20}?(?:becomes?|changes? to|set to|at|is)\s*(?:cny|rmb|¥)?\s*(\d+(?:\.\d+)?)/i, /(?:cny|rmb|¥)\s*(\d+(?:\.\d+)?)\s*(?:\/|per)?\s*kwh/i, /(\d+(?:\.\d+)?)\s*(?:cny|rmb)\s*(?:\/|per)?\s*kwh/i];
  for (const pattern of patterns) {
    const value = Number(text.match(pattern)?.[1]);
    if (value >= .1 && value <= 5) return value;
  }
  return null;
}

function moneyValue(text: string) {
  const match = text.match(/(?:investment|capex|retrofit cost)[^.;,]{0,24}?(?:becomes?|changes? to|set to|at|is)?\s*(?:cny|rmb|¥)?\s*(\d+(?:\.\d+)?)\s*(k|thousand)?/i);
  if (!match) return null;
  return Number(match[1]) * (match[2]?.toLowerCase().startsWith("k") || match[2]?.toLowerCase().startsWith("thousand") ? 1000 : 1);
}

function parseWhatIf(question: string, historyText: string): WhatIf {
  const warnings: string[] = [];
  let tariffChange = percentageChange(question, ["tariff", "electricity price", "energy price"]);
  const genericUp = question.match(/(?:rise|rises|increase|increases|go up|higher|raise|raises)\s*(?:by\s*)?(\d+(?:\.\d+)?)\s*%/i);
  const genericDown = question.match(/(?:fall|falls|decrease|decreases|drop|drops|go down|lower|reduce|reduces)\s*(?:by\s*)?(\d+(?:\.\d+)?)\s*%/i);
  if (tariffChange === null && /tariff|electricity price|energy price/i.test(historyText)) {
    if (genericUp) tariffChange = Number(genericUp[1]) / 100;
    else if (genericDown) tariffChange = -Number(genericDown[1]) / 100;
  }
  const explicitTariff = absoluteTariff(question);
  const savingChange = percentageChange(question, ["saving rate", "energy savings", "electricity savings", "savings"]);
  const capex = moneyValue(question);
  const inheritedTariff = absoluteTariff(historyText);
  let tariff = explicitTariff ?? (tariffChange !== null ? facts.tariff * (1 + tariffChange) : inheritedTariff ?? facts.tariff);
  if (tariff <= 0 || tariff > 5) {
    warnings.push("The tariff input is outside the 0–5 CNY/kWh analysis boundary; the baseline tariff has been restored.");
    tariff = facts.tariff;
  }
  let savingFactor = 1 + (savingChange ?? 0);
  if (savingFactor < 0 || savingFactor > 4) {
    warnings.push("The saving change is outside the −100% to +300% scenario boundary; baseline savings have been restored.");
    savingFactor = 1;
  }
  return { tariff, savingFactor, capex: capex ?? facts.comboCapex, active: tariffChange !== null || explicitTariff !== null || savingChange !== null || capex !== null, warnings };
}

const money = (value: number) => value.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

function energyTool(whatIf: WhatIf): ToolResult {
  const annualCost = facts.annual * whatIf.tariff;
  const scenarioNote = whatIf.active ? ` Under the user-defined counterfactual tariff of CNY ${whatIf.tariff.toFixed(3)}/kWh, annual electricity cost becomes CNY ${money(annualCost)}.` : "";
  return {
    intent: "energy_baseline", tool: "query_energy_baseline", title: "Annual Energy and Cost Baseline",
    body: `From July 2024 to June 2025, four meters total ${money(facts.annual)} kWh. With a gross floor area of ${money(facts.area)} m², EUI is ${facts.eui.toFixed(2)} kWh/m²·year. HVAC uses ${money(facts.hvac)} kWh, or ${facts.hvacShare.toFixed(2)}%. The Ningbo reference-case billing rule is electricity bill = kWh × CNY 0.538, with no time-of-use, demand or other charge components; annual cost is therefore CNY ${money(facts.annual * facts.tariff)}.${scenarioNote}`,
    evidence: "APPROVED AGGREGATE + SYNTHETIC", sources: ["monthly_meter_clean.csv", "meter_summary.csv", "project_summary.json"],
    actions: ["Use high-frequency metering to diagnose peaks and intraday loads."], calculations: [`Annual cost = ${money(facts.annual)} × CNY ${whatIf.tariff.toFixed(3)} = CNY ${money(annualCost)}`],
  };
}

function anomalyTool(): ToolResult {
  return {
    intent: "meter_anomaly", tool: "inspect_meter_quality_event", title: "October 2024 Meter-Anomaly Diagnosis",
    body: "The approved October 2024 aggregate is retained as a documented case-study meter fault. Public meter identifiers and row-level values are deterministic synthetic records, not original institutional records. Annual aggregates remain suitable for screening, while the anomalous month is not treated as a normal operating sample. The public model never presents an estimate as a measured value.",
    evidence: "MEASURED + DOCUMENTED", sources: ["monthly_meter_clean.csv", "data_quality_flags.csv", "Facilities response / original monthly records"],
    actions: ["Request backend meter logs or November daily records if monthly allocation must be reconstructed.", "Exclude October from month-by-month operational diagnosis until evidence is obtained."],
  };
}

function scenarioTool(question: string, whatIf: WhatIf): ToolResult {
  const rows = scenarios.map((item) => {
    const saved = item.saved * whatIf.savingFactor;
    const capex = item.name === "Combined package" && whatIf.capex !== facts.comboCapex ? whatIf.capex : item.capex;
    const saving = saved * whatIf.tariff;
    return { name: item.name, saved, saving, payback: capex / saving, paybackBest: capex / (saved * 1.25 * whatIf.tariff), paybackWorst: capex / (saved * .75 * whatIf.tariff) };
  });
  const fastest = [...rows].sort((a, b) => a.payback - b.payback)[0];
  const largest = [...rows].sort((a, b) => b.saved - a.saved)[0];
  const combo = rows.find((row) => row.name === "Combined package")!;
  const comparing = ["which", "compare", "best value", "fastest", "priority", "rank"].some((term) => normalize(question).includes(term));
  const body = comparing
    ? `At CNY ${whatIf.tariff.toFixed(3)}/kWh, ${fastest.name} has the fastest payback at about ${fastest.payback.toFixed(2)} years, while ${largest.name} saves the most energy at ${(largest.saved / 1000).toFixed(2)} MWh/year. These optimise different objectives: choose ${fastest.name} for low-cost, rapid payback; choose the combined package for maximum annual impact, with a payback of about ${combo.payback.toFixed(2)} years.`
    : `Under current assumptions, the combined package saves ${(combo.saved / 1000).toFixed(2)} MWh/year, or about ${(combo.saved / facts.annual * 100).toFixed(2)}% of baseline use. At CNY ${whatIf.tariff.toFixed(3)}/kWh, annual cost savings are CNY ${money(combo.saving)} and simple payback is ${combo.payback.toFixed(2)} years. Across low/high engineering-screening bounds, payback is approximately ${combo.paybackBest.toFixed(2)}–${combo.paybackWorst.toFixed(2)} years; this is not a statistical confidence interval. The parameterized Malaysia carbon scenario is ${(facts.comboCarbon * whatIf.savingFactor).toFixed(2)} tCO₂e/year; it is an assumption, not a Malaysia field result.`;
  return {
    intent: "scenario_roi", tool: "rank_and_recalculate_scenarios", title: comparing ? "Dynamic Multi-Scenario Ranking" : "Combined-Package What-If Result", body,
    evidence: whatIf.active ? "DERIVED + USER WHAT-IF + ASSUMED CAPEX" : "DERIVED + ASSUMED",
    sources: ["scenario_summary.csv", "project_assumptions.json", "project_summary.json"],
    actions: ["Replace assumed CAPEX with supplier quotations before procurement.", "Confirm HVAC schedules and luminaire counts, then design M&V before implementation.", "The billing rule is confirmed; no time-of-use or demand-charge inputs are required."],
    calculations: rows.map((row) => `${row.name}: ${(row.saved / 1000).toFixed(2)} MWh/year saved · CNY ${row.saving.toLocaleString("en-US", { maximumFractionDigits: 0 })}/year · ${row.payback.toFixed(2)}-year payback`),
  };
}

function pvTool(): ToolResult {
  return {
    intent: "pv_status", tool: "summarize_pv_operation", title: "Installed PV Contribution",
    body: `A ${facts.pvCapacity.toFixed(2)} kWp PV system is installed at grid connection point 2, with ${(facts.pvGeneration / 1000).toFixed(2)} MWh measured across 12 months. The monthly-constrained hourly reconstruction estimates current grid imports at ${(facts.currentGrid / 1000).toFixed(2)} MWh, energy self-sufficiency at ${facts.selfSufficiency.toFixed(2)}%, and PV self-consumption at ${facts.pvSelfUse.toFixed(2)}%. Those final three values are screening estimates, not grid-point measurements.`,
    evidence: "MEASURED + DERIVED", sources: ["db_pv_monthly_measured.csv", "target_pv_profile.csv", "loss_aware_metrics.csv", "LDB PV as-built records"],
    actions: ["Export hourly inverter generation and grid connection point 2 import/export data for calibration.", "Require a structural engineer to verify roof capacity before expansion."],
    calculations: [`Annual PV generation / annual building use = ${(facts.pvGeneration / facts.annual * 100).toFixed(2)}% (not the self-sufficiency ratio)`],
  };
}

function storageTool(): ToolResult {
  return {
    intent: "storage_sandbox", tool: "compare_storage_strategies", title: "No Storage Is Installed at reference case · Future Counterfactual Analysis",
    body: `reference case currently has no battery storage. The future sandbox assumes a 300 kWh / 120 kW battery. Loss-aware dispatch produces ${(facts.lossAwareGrid / 1000).toFixed(2)} MWh/year of grid imports, ${facts.gridReduction.toFixed(2)}% below the ${(facts.naiveGrid / 1000).toFixed(2)} MWh/year rule-based strategy. Battery-loss/throughput indicators fall by ${facts.batteryReduction.toFixed(2)}%. This demonstrates dispatch logic; it does not prove that a battery is worth purchasing.`,
    evidence: "SANDBOX + DERIVED", sources: ["loss_aware_metrics.csv", "loss_aware_hourly_detail.csv", "project_assumptions.json"],
    actions: ["Re-size the battery after high-frequency load and import/export data are available.", "Using the Ningbo reference-case tariff of CNY 0.538/kWh, add battery quotations, maintenance and lifetime data before calculating financial returns."],
    calculations: [`Grid-import difference = ${money(facts.naiveGrid - facts.lossAwareGrid)} kWh/year`],
  };
}

function gapTool(): ToolResult {
  return {
    intent: "data_gap", tool: "prioritize_data_requests", title: "Data-Collection Plan Ranked by Model Value",
    body: "Priorities are ranked by their ability to change decisions. First, collect 2–4 weeks of 15-minute reference case main/submeter data to calibrate peaks and intraday shape. Second, collect hourly inverter generation, export and self-use data to calibrate PV value. Third, measure temperature, RH and CO₂ in 3–6 representative rooms to validate comfort constraints. Then add equipment mapping, start/stop and fault records, and supplier quotations. Current substitutes are sufficient for screening, but not for guaranteed savings.",
    evidence: "MIXED · GAP REGISTER + VALUE-OF-INFORMATION RANKING", sources: ["data_request_tracker.csv", "data_quality_flags.csv", "source_lineage.csv"],
    actions: ["Start with low-cost short-term monitoring; do not wait for a complete BMS upgrade.", "Re-run calibration gates and scenario rankings whenever new data arrive."],
  };
}

function comfortTool(): ToolResult {
  return {
    intent: "comfort_schedule", tool: "check_operating_constraints", title: "Opening-Hours and Comfort-Constraint Check",
    body: "Classrooms are assumed open daily from 08:00 to 22:00, giving 5,110 open hours. During opening, the comfort proxy uses 20–26°C, 40–60% RH and CO₂ ≤ 1,000 ppm. This proves only that simulated scenarios respect the defined boundary; it does not prove historical indoor conditions were compliant.",
    evidence: "ASSUMED + DERIVED", sources: ["project_assumptions.json", "comfort_proxy_hourly.csv", "run_validation.json"], actions: ["Install sensors in representative rooms and record actual holidays and event days."],
  };
}

function governanceTool(): ToolResult {
  return {
    intent: "model_governance", tool: "audit_decision_readiness", title: "Decisions the Model Can and Cannot Support",
    body: "Irene supports annual baselines, scenario screening, data-collection priorities, interpretation of installed PV and technical comparison of future storage strategies. It cannot directly support procurement commitments, equipment control, guaranteed savings, precise peak/demand estimates or conclusions about actual indoor comfort. Zero monthly-reconciliation failures and a successful LP validate internal consistency, not site-validated hourly accuracy.",
    evidence: "MIXED · EXPLICIT EVIDENCE HIERARCHY", sources: ["run_validation.json", "donor_profile_model_metrics.json", "source_lineage.csv", "data_quality_flags.csv"],
    actions: ["Calculate CV(RMSE) and NMBE after high-frequency metering is available, then upgrade the calibration level.", "Register the source, time range and use boundary of every new dataset before modelling."],
  };
}

function improvementTool(): ToolResult {
  return {
    intent: "model_improvement", tool: "prioritize_model_upgrades", title: "Model-Upgrade Priorities and Achievable Boundary",
    body: "The next version should prioritise observations that enable site calibration, not a more complex algorithm. Priorities are: (1) 2–4 weeks of 15-minute reference case main/submeter data to replace cross-building reconstruction with a reference case-calibrated profile; (2) synchronous inverter and grid-point data to calibrate PV self-consumption and exports; (3) temperature, RH and CO₂ in representative rooms plus the actual operating calendar to replace the comfort proxy; (4) current HVAC nameplates, part-load COP and BMS states to improve the HVAC mechanism; and (5) supplier quotations and battery-degradation parameters to improve the financial model. The billing rule is already confirmed, so time-of-use and demand-charge inputs are unnecessary. Without new evidence, changing the machine-learning algorithm only adds complexity and cannot honestly improve site accuracy.",
    evidence: "MODEL READINESS REGISTER + VALUE-OF-INFORMATION",
    sources: ["model_readiness_register.csv", "data_request_tracker.csv", "donor_profile_model_metrics.json", "source_lineage.csv"],
    actions: ["Deploy temporary 15-minute loggers and create a holdout validation set first.", "Report CV(RMSE), NMBE, monthly conservation and evidence class for every upgrade.", "Keep the transparent calendar prior as the baseline every new algorithm must beat."],
    calculations: ["Release gate = improved site error + monthly conservation + an explainable evidence boundary; all three must pass."],
  };
}

const builders: Record<string, (question: string, whatIf: WhatIf) => ToolResult> = {
  energy_baseline: (_question, whatIf) => energyTool(whatIf), meter_anomaly: () => anomalyTool(), scenario_roi: scenarioTool,
  pv_status: () => pvTool(), storage_sandbox: () => storageTool(), data_gap: () => gapTool(), comfort_schedule: () => comfortTool(), model_governance: () => governanceTool(),
  model_improvement: () => improvementTool(),
};

export const toolNameToIntent: Record<string, string> = {
  query_energy_baseline: "energy_baseline",
  inspect_meter_quality_event: "meter_anomaly",
  rank_and_recalculate_scenarios: "scenario_roi",
  summarize_pv_operation: "pv_status",
  compare_storage_strategies: "storage_sandbox",
  prioritize_data_requests: "data_gap",
  check_operating_constraints: "comfort_schedule",
  audit_decision_readiness: "model_governance",
  prioritize_model_upgrades: "model_improvement",
};

const toolDescriptions: Record<string, string> = {
  query_energy_baseline: "Return reference case annual electricity, EUI, HVAC share and the cost baseline using the Ningbo reference-case tariff of CNY 0.538/kWh.",
  inspect_meter_quality_event: "Explain the October 2024 aggregate anomaly and the valid public-use boundary.",
  rank_and_recalculate_scenarios: "Recalculate and compare efficiency measures and payback using a user-defined tariff, savings change or CAPEX.",
  summarize_pv_operation: "Describe the installed 106.14 kWp PV at grid connection point 2, measured generation and derived self-use relationships.",
  compare_storage_strategies: "Compare future storage-sandbox strategies while making clear that reference case currently has no storage.",
  prioritize_data_requests: "Rank missing data and practical substitutes by decision value.",
  check_operating_constraints: "Check the 08:00–22:00 opening schedule and the valid use boundary of the comfort proxy.",
  audit_decision_readiness: "Audit which decisions the model can and cannot support and the corresponding evidence classes.",
  prioritize_model_upgrades: "Prioritise the next data and algorithm upgrades according to site-calibration value.",
};

export const openAIToolDefinitions = Object.entries(toolDescriptions).map(([name, description]) => ({
  type: "function",
  name,
  description,
  strict: true,
  parameters: { type: "object", properties: {}, required: [], additionalProperties: false },
}));

export function executeEnergyTool(toolName: string, question: string, history: string[] = []): ToolResult {
  const intent = toolNameToIntent[toolName];
  if (!intent || !builders[intent]) throw new Error(`Unsupported Irene energy tool: ${toolName}`);
  const historyText = history.slice(-3).join(" ");
  return builders[intent](question, parseWhatIf(question, historyText));
}

export function composeEnhancedResponse(
  results: ToolResult[],
  answer: string,
  model: string,
  usage = { inputTokens: 0, outputTokens: 0 },
): AgentResponse {
  if (!results.length) throw new Error("At least one deterministic tool result is required");
  const primary = results[0];
  const intents = unique(results.map((result) => result.intent));
  const toolNames = results.map((result) => result.tool);
  return {
    intent: primary.intent,
    intents,
    tool: results.length === 1 ? primary.tool : "openai_multi_tool_orchestrator",
    title: results.length === 1 ? primary.title : `${primary.title} (${results.length} analyses combined)`,
    answer: answer.trim() || results.map((result) => `【${result.title}】${result.body}`).join("\n\n"),
    evidence: unique(results.map((result) => result.evidence)).join(" · "),
    sources: unique(results.flatMap((result) => result.sources)),
    nextSteps: unique(results.flatMap((result) => result.actions)),
    confidence: "The model handles understanding and expression; project values come from deterministic tools, and reliability remains governed by evidence class and decision readiness.",
    planSteps: [
      "OpenAI interprets the question and selects project tools",
      `Run deterministic reference case tools: ${toolNames.join(" → ")}`,
      "Compose the answer from tool outputs while preserving evidence boundaries",
    ],
    calculations: results.flatMap((result) => result.calculations ?? []),
    followUps: unique(intents.flatMap((intent) => followUps[intent])).slice(0, 3),
    modelMode: `OPENAI RESPONSES · ${model} · 9 AUDITABLE TOOLS`,
    routeConfidence: 1,
    decisionReadiness: unique(intents.map((intent) => decisionReadiness[intent])).join(" · "),
    matchedConcepts: ["model-selected tool route"],
    warnings: [],
    engine: "openai",
    provider: "OpenAI Responses API",
    usage: { ...usage, totalTokens: usage.inputTokens + usage.outputTokens },
    toolCallCount: results.length,
  };
}

const unique = <T,>(values: T[]) => [...new Set(values)];

export function answerEnergyQuestion(question: string, history: string[] = []): AgentResponse {
  const text = question.trim();
  if (!text) return {
    intent: "help", intents: [], tool: "capability_router", title: "Enter a Project Question",
    answer: "I can combine queries about energy, anomalies, scenarios, PV, storage, data gaps, model boundaries and the upgrade roadmap. I can also recalculate results for a user-defined tariff, savings change or investment amount.",
    evidence: "SYSTEM", sources: ["Agent capability register"], nextSteps: ["Try a question containing ‘what if’ or ‘compare’."], confidence: "No project tool executed",
    planSteps: [], calculations: [], followUps: [...quickPrompts.slice(0, 2)], modelMode: "LOCAL DOMAIN PLANNER · NO EXTERNAL API", routeConfidence: 0,
    decisionReadiness: "Not executed", matchedConcepts: [], warnings: [], engine: "local", provider: "Local deterministic engine",
  };

  const routed = route(text, history);
  if (!routed.intents.length) return {
    intent: "capability_help", intents: [], tool: "capability_router", title: "Question Outside the reference case Local-Model Evidence Boundary",
    answer: "I understand that this is a new question, but the current local tools cover only Irene energy and decision analysis. To avoid fabrication, I will not invent operations or external facts that are not connected to the project.",
    evidence: "SYSTEM BOUNDARY", sources: ["Agent capability register"], nextSteps: ["Relate the question to energy, equipment, scenarios, data or model reliability."], confidence: "Intent match was insufficient, so the request was safely declined (heuristic score, not statistical confidence).",
    planSteps: ["Analyse the question", "Check tool coverage", "Apply the evidence-boundary guardrail"], calculations: [], followUps: [], modelMode: "LOCAL DOMAIN PLANNER · NO EXTERNAL API", routeConfidence: Math.max(...Object.values(routed.scores)),
    decisionReadiness: "Outside tool boundary", matchedConcepts: [], warnings: [], engine: "local", provider: "Local deterministic engine",
  };

  const whatIf = parseWhatIf(text, routed.contextual ? routed.historyText : "");
  const results = routed.intents.map((intent) => builders[intent](text, whatIf));
  const primary = results[0];
  const routeConfidence = Math.min(.98, .42 + routed.scores[routed.intents[0]] * .56);
  const confidenceLevel = routeConfidence >= .80 ? "High" : routeConfidence >= .60 ? "Medium" : "Limited";
  const routingText = routed.contextual ? `${routed.historyText} ${text}` : text;
  const direct = directSignalHits(routingText);
  const matchedConcepts = unique(routed.intents.flatMap((intent) => direct[intent]));
  return {
    intent: primary.intent, intents: routed.intents,
    tool: results.length === 1 ? primary.tool : "local_multi_tool_planner",
    title: results.length === 1 ? primary.title : `${primary.title} (${results.length} analyses combined)`,
    answer: results.map((result) => `【${result.title}】${result.body}`).join("\n\n"),
    evidence: unique(results.map((result) => result.evidence)).join(" · "),
    sources: unique(results.flatMap((result) => result.sources)), nextSteps: unique(results.flatMap((result) => result.actions)),
    confidence: `${confidenceLevel} match: intent score ${(routeConfidence * 100).toFixed(0)}% (heuristic, not statistical confidence)${routed.contextual ? "; previous-question context was retained" : ""}${whatIf.active ? "; dynamic values belong to a user-defined scenario" : ""}. Conclusion reliability is governed by evidence class and decision readiness.`,
    planSteps: [
      `Interpret the question and extract conditions${routed.contextual ? " (including conversational context)" : ""}`,
      `Plan ${results.length} local tool call(s): ${results.map((result) => result.tool).join(" → ")}`,
      "Run deterministic calculations and verify evidence classes", "Combine conclusions, limitations and next actions",
    ],
    calculations: results.flatMap((result) => result.calculations ?? []),
    followUps: unique(routed.intents.flatMap((intent) => followUps[intent])).slice(0, 3),
    modelMode: "LOCAL DOMAIN PLANNER · NO EXTERNAL API", routeConfidence,
    decisionReadiness: unique(routed.intents.map((intent) => decisionReadiness[intent])).join(" · "),
    matchedConcepts, warnings: whatIf.warnings, engine: "local", provider: "Local deterministic engine",
  };
}
