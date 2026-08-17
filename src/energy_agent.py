"""Offline domain-reasoning agent for the Irene Energy Command Center.

This is not a remote chatbot.  It combines a lightweight semantic router,
multi-tool planning, parameter extraction, deterministic engineering
calculations, conversation context and explicit evidence boundaries.  Every
number is produced from the approved Irene project facts or a labelled what-if input.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Mapping, Sequence


@dataclass(frozen=True)
class AgentResponse:
    intent: str
    tool_name: str
    title: str
    answer: str
    evidence_class: str
    sources: tuple[str, ...]
    next_steps: tuple[str, ...]
    confidence: str
    intents: tuple[str, ...] = ()
    plan_steps: tuple[str, ...] = ()
    calculations: tuple[str, ...] = ()
    follow_ups: tuple[str, ...] = ()
    model_mode: str = "LOCAL DOMAIN PLANNER"
    route_confidence: float = 0.0
    decision_readiness: str = ""
    matched_concepts: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    engine: str = "local"
    provider: str = "Local deterministic engine"
    input_tokens: int = 0
    output_tokens: int = 0
    tool_call_count: int = 0
    fallback_reason: str = ""


@dataclass(frozen=True)
class ToolResult:
    intent: str
    tool: str
    title: str
    body: str
    evidence: str
    sources: tuple[str, ...]
    actions: tuple[str, ...]
    calculations: tuple[str, ...] = ()


DEFAULT_CONTEXT: dict[str, object] = {
    "model_version": "Irene Auditable Digital Twin",
    "annual_total_kwh": 345_676.69,
    "annual_hvac_kwh": 100_265.61,
    "hvac_share_pct": 29.01,
    "gross_floor_area_m2": 6_231.26,
    "annual_eui_kwh_m2": 55.47,
    "tariff_cny_kwh": 0.538,
    "pv_capacity_kwp": 106.14,
    "pv_generation_kwh": 126_233.50,
    "current_grid_import_kwh": 230_970.24,
    "current_self_sufficiency_pct": 33.18,
    "current_pv_self_consumption_pct": 90.87,
    "combo_saved_kwh": 41_581.69,
    "combo_saving_rate_pct": 12.03,
    "combo_saving_cny": 22_370.95,
    "combo_capex_cny": 62_000.0,
    "combo_payback_years": 2.77,
    "combo_carbon_tco2e": 30.77,
    "loss_aware_grid_import_kwh": 224_486.41,
    "naive_grid_import_kwh": 233_924.17,
    "grid_reduction_vs_naive_pct": 4.03,
    "battery_loss_reduction_pct": 91.73,
    "opening_hours": "08:00—22:00",
    "comfort_band": "20—26°C、40%—60% RH、CO₂≤1000 ppm",
}


SCENARIOS: tuple[dict[str, float | str], ...] = (
    {"name": "Comfort-constrained HVAC optimisation", "saved": 7_158.82, "capex": 8_000.0, "payback": 2.08},
    {"name": "HVAC operating-hours optimisation", "saved": 5_011.17, "capex": 12_000.0, "payback": 4.45},
    {"name": "LED lighting retrofit", "saved": 19_632.89, "capex": 45_000.0, "payback": 4.26},
    {"name": "Plug-load and standby management", "saved": 9_778.82, "capex": 18_000.0, "payback": 3.42},
    {"name": "Combined package", "saved": 41_581.69, "capex": 62_000.0, "payback": 2.77},
)


QUICK_PROMPTS: tuple[str, ...] = (
    "If the electricity tariff rises by 20%, what is the combined package payback?",
    "Which measure pays back fastest, and which saves the most energy?",
    "Why is October 2024 anomalous, and can it still support annual analysis?",
    "How do installed PV and future storage affect grid imports?",
    "Which three missing datasets should be collected first to improve confidence?",
    "Which decisions can this model support, and which can it not support?",
    "What should the next model upgrade be, and why is a new algorithm alone insufficient?",
)


INTENT_PROFILES: dict[str, dict[str, tuple[str, ...]]] = {
    "energy_baseline": {
        "examples": ("how much electricity does the building use each year", "what is the overall energy performance", "what is the energy use intensity", "what share is HVAC", "annual electricity cost baseline"),
        "signals": ("electricity", "energy", "consumption", "eui", "hvac", "baseline", "annual", "year", "area", "bill", "cost"),
    },
    "meter_anomaly": {
        "examples": ("why is October suddenly so low", "was the meter faulty", "does November include October", "how is the anomalous month handled", "aggregate meter anomaly"),
        "signals": ("october", "2024-10", "anomaly", "anomalous", "fault", "meter", "missing reading", "impute"),
    },
    "scenario_roi": {
        "examples": ("which retrofit is most worthwhile", "how long is the payback", "recalculate if the tariff changes", "compare all energy-efficiency measures", "how much cost and carbon can be saved"),
        "signals": ("saving", "savings", "payback", "roi", "investment", "retrofit", "carbon", "emissions", "scenario", "measure", "priority", "tariff", "capex"),
    },
    "pv_status": {
        "examples": ("how much electricity did rooftop solar generate", "how much load can PV cover", "what is the self-consumption ratio", "where is the grid connection point", "what renewable energy is installed"),
        "signals": ("pv", "photovoltaic", "solar", "grid connection", "self-consumption", "self-sufficiency", "export", "generation", "renewable"),
    },
    "storage_sandbox": {
        "examples": ("would a battery add value", "how could storage reduce grid imports", "compare two battery-dispatch strategies", "soc and battery losses", "future pv and storage scenario"),
        "signals": ("storage", "battery", "loss-aware", "loss aware", "soc", "charge", "charging", "discharge", "dispatch"),
    },
    "data_gap": {
        "examples": ("what should be collected first to improve accuracy", "which site data are still missing", "what can be done without hourly data", "how should the model be calibrated", "are substitute data reliable"),
        "signals": ("missing", "gap", "need", "collect", "collection", "substitute", "estimate", "estimated", "accuracy", "data", "validation"),
    },
    "comfort_schedule": {
        "examples": ("when is the teaching building open", "will optimisation compromise comfort", "what temperature and humidity ranges are used", "what is the carbon-dioxide limit", "how is the operating calendar defined"),
        "signals": ("open", "opening", "close", "closing", "comfort", "temperature", "humidity", "co2", "carbon dioxide", "classroom", "schedule", "hours"),
    },
    "model_governance": {
        "examples": ("are the model results trustworthy", "which data are measured and which are simulated", "was the algorithm validated", "can this value support procurement", "model boundaries and evidence classes"),
        "signals": ("model", "trust", "confidence", "validate", "validation", "calibrate", "measured", "derived", "assumed", "evidence", "ai", "boundary", "decision", "procurement"),
    },
    "model_improvement": {
        "examples": ("how can the model be improved", "what should the next version upgrade first", "how can hourly accuracy improve", "should data or the algorithm change first", "model improvement roadmap"),
        "signals": ("model improvement", "model upgrade", "improve model", "upgrade model", "next version", "improve accuracy", "roadmap", "algorithm upgrade", "optimise model", "optimize model"),
    },
}


FOLLOWUP_MARKERS = ("then", "what if", "instead", "increase", "decrease", "raise", "lower", "again", "that", "previous")
GENERIC_FEATURES = {"how", "what", "which", "this", "that", "is", "are", "does", "do", "can", "could", "would"}
COMPOUND_MARKERS = ("and", "also", "together", "respectively", "versus", "vs", "/")

DECISION_READINESS = {
    "energy_baseline": "Suitable for annual analysis",
    "meter_anomaly": "Suitable for annual analysis; anomalous-month diagnosis is limited",
    "scenario_roi": "Scenario screening",
    "pv_status": "Current-state interpretation; hourly relationships require calibration",
    "storage_sandbox": "Technology sandbox; not procurement-ready",
    "data_gap": "Data-collection planning",
    "comfort_schedule": "Constraint testing; not a measured comfort conclusion",
    "model_governance": "Governance guidance",
    "model_improvement": "Upgrade-roadmap planning",
}


def _context(overrides: Mapping[str, object] | None) -> dict[str, object]:
    merged = dict(DEFAULT_CONTEXT)
    if overrides:
        merged.update({key: value for key, value in overrides.items() if value is not None})
    return merged


def _normalize(text: str) -> str:
    return re.sub(r"[^0-9a-z\u4e00-\u9fff%.-]+", "", text.lower())


def _features(text: str) -> set[str]:
    normalized = _normalize(text)
    features = {normalized[index:index + size] for size in (2, 3) for index in range(max(0, len(normalized) - size + 1))}
    features.update(re.findall(r"[a-z]+|\d+(?:\.\d+)?%?", normalized))
    features.difference_update(GENERIC_FEATURES)
    return features


def _cosine(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / math.sqrt(len(left) * len(right))


def _semantic_scores(text: str) -> dict[str, float]:
    query = _features(text)
    scores: dict[str, float] = {}
    normalized = _normalize(text)
    for intent, profile in INTENT_PROFILES.items():
        semantic = max(_cosine(query, _features(example)) for example in profile["examples"])
        direct_hits = sum(1 for signal in profile["signals"] if _normalize(signal) in normalized)
        scores[intent] = min(1.0, semantic * 1.45 + min(0.72, direct_hits * 0.24))
    return scores


def _direct_signal_hits(text: str) -> dict[str, tuple[str, ...]]:
    normalized = _normalize(text)
    return {
        intent: tuple(signal for signal in profile["signals"] if _normalize(signal) in normalized)
        for intent, profile in INTENT_PROFILES.items()
    }


def _history_text(history: Sequence[str] | None) -> str:
    if not history:
        return ""
    return " ".join(str(item) for item in history[-3:] if str(item).strip())


def _route(question: str, history: Sequence[str] | None) -> tuple[list[str], dict[str, float], bool]:
    text = question.strip()
    contextual = bool(_history_text(history)) and len(_normalize(text)) <= 80 and any(_normalize(marker) in _normalize(text) for marker in FOLLOWUP_MARKERS)
    routing_text = f"{_history_text(history)} {text}" if contextual else text
    scores = _semantic_scores(routing_text)
    direct_hits = _direct_signal_hits(routing_text)
    ordered = sorted(scores, key=lambda intent: (len(direct_hits[intent]), scores[intent]), reverse=True)
    top_score = scores[ordered[0]]
    if top_score < 0.20 or (not any(direct_hits.values()) and top_score < 0.45):
        return [], scores, contextual
    compound = any(marker in text for marker in COMPOUND_MARKERS)
    if compound:
        selected = [
            intent for intent in ordered
            if direct_hits[intent] and scores[intent] >= 0.20
        ][:3]
    else:
        selected = [ordered[0]]
    return selected or [ordered[0]], scores, contextual


def _percent_change(text: str, subjects: Sequence[str]) -> float | None:
    subject_group = "|".join(map(re.escape, subjects))
    up = re.search(rf"(?:{subject_group})[^.;,]{{0,30}}?(?:rise|rises|increase|increases|go up|higher|raised?)\s*(?:by\s*)?(\d+(?:\.\d+)?)\s*%", text, re.I)
    down = re.search(rf"(?:{subject_group})[^.;,]{{0,30}}?(?:fall|falls|decrease|decreases|drop|drops|go down|lower|reduced?)\s*(?:by\s*)?(\d+(?:\.\d+)?)\s*%", text, re.I)
    if up:
        return float(up.group(1)) / 100
    if down:
        return -float(down.group(1)) / 100
    return None


def _absolute_tariff(text: str) -> float | None:
    patterns = (
        r"(?:tariff|electricity price|energy price)[^.;,]{0,20}?(?:becomes?|changes? to|set to|at|is)\s*(?:cny|rmb|¥)?\s*(\d+(?:\.\d+)?)",
        r"(?:cny|rmb|¥)\s*(\d+(?:\.\d+)?)\s*(?:/|per)?\s*kwh",
        r"(\d+(?:\.\d+)?)\s*(?:cny|rmb)\s*(?:/|per)?\s*kwh",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            value = float(match.group(1))
            if 0.1 <= value <= 5:
                return value
    return None


def _money_value(text: str, subject: str) -> float | None:
    match = re.search(rf"{subject}[^.;,]{{0,24}}?(?:becomes?|changes? to|set to|at|is)?\s*(?:cny|rmb|¥)?\s*(\d+(?:\.\d+)?)\s*(k|thousand)?", text, re.I)
    if not match:
        return None
    value = float(match.group(1))
    return value * 1_000 if match.group(2) and match.group(2).lower().startswith(("k", "thousand")) else value


def _what_if(question: str, context_text: str, c: Mapping[str, object]) -> dict[str, float | bool]:
    text = f"{context_text} {question}".strip()
    base_tariff = float(c["tariff_cny_kwh"])
    tariff = _absolute_tariff(question)
    tariff_change = _percent_change(question, ("tariff", "electricity price", "energy price"))
    generic_up = re.search(r"(?:rise|rises|increase|increases|go up|higher|raise|raises)\s*(?:by\s*)?(\d+(?:\.\d+)?)\s*%", question, re.I)
    generic_down = re.search(r"(?:fall|falls|decrease|decreases|drop|drops|go down|lower|reduce|reduces)\s*(?:by\s*)?(\d+(?:\.\d+)?)\s*%", question, re.I)
    if tariff_change is None and re.search(r"tariff|electricity price|energy price", context_text, re.I):
        if generic_up:
            tariff_change = float(generic_up.group(1)) / 100
        elif generic_down:
            tariff_change = -float(generic_down.group(1)) / 100
    warnings: list[str] = []
    if tariff is None:
        tariff = base_tariff * (1 + tariff_change) if tariff_change is not None else base_tariff
    if tariff <= 0 or tariff > 5:
        warnings.append("The tariff input is outside the 0–5 CNY/kWh analysis boundary; the baseline tariff has been restored.")
        tariff = base_tariff

    saving_change = _percent_change(question, ("saving rate", "energy savings", "electricity savings", "savings"))
    saving_factor = 1 + saving_change if saving_change is not None else 1.0
    if saving_factor < 0 or saving_factor > 4:
        warnings.append("The saving change is outside the −100% to +300% scenario boundary; baseline savings have been restored.")
        saving_factor = 1.0
    capex = _money_value(question, "(?:investment|capex|retrofit cost)") or float(c["combo_capex_cny"])
    is_what_if = any(value is not None for value in (tariff_change, saving_change, _absolute_tariff(question), _money_value(question, "(?:investment|capex|retrofit cost)")))
    return {"tariff": tariff, "saving_factor": saving_factor, "capex": capex, "is_what_if": is_what_if, "warnings": tuple(warnings)}


def _energy_tool(c: Mapping[str, object], what_if: Mapping[str, float | bool]) -> ToolResult:
    tariff = float(what_if["tariff"])
    annual_cost = float(c["annual_total_kwh"]) * tariff
    scenario_note = "" if not what_if["is_what_if"] else f" Under the user-defined counterfactual tariff of CNY {tariff:.3f}/kWh, annual electricity cost becomes CNY {annual_cost:,.2f}."
    return ToolResult(
        "energy_baseline", "query_energy_baseline", "Annual Energy and Cost Baseline",
        f"From July 2024 to June 2025, four meters total {float(c['annual_total_kwh']):,.2f} kWh. With a gross floor area of {float(c['gross_floor_area_m2']):,.2f} m², "
        f"EUI is {float(c['annual_eui_kwh_m2']):.2f} kWh/m²·year. HVAC uses {float(c['annual_hvac_kwh']):,.2f} kWh, or {float(c['hvac_share_pct']):.2f}%. "
        f"The Ningbo reference-case billing rule is electricity bill = kWh × CNY 0.538, with no time-of-use, demand or other charge components; annual cost is therefore CNY {float(c['annual_total_kwh'])*float(c['tariff_cny_kwh']):,.2f}.{scenario_note}",
        "APPROVED AGGREGATE + SYNTHETIC", ("monthly_meter_clean.csv", "meter_summary.csv", "project_summary.json"),
        ("Use high-frequency metering to diagnose peaks and intraday loads.",),
        (f"Annual cost = {float(c['annual_total_kwh']):,.2f} × CNY {tariff:.3f} = CNY {annual_cost:,.2f}",),
    )


def _anomaly_tool() -> ToolResult:
    return ToolResult(
        "meter_anomaly", "inspect_meter_quality_event", "October 2024 Meter-Anomaly Diagnosis",
        "The approved October 2024 aggregate is retained as a documented case-study meter fault. Public meter identifiers and row-level values are deterministic synthetic records, not original institutional records. "
        "Annual aggregates remain suitable for screening, while the anomalous month is not treated as a normal operating sample. The public model never presents an estimate as a measured value.",
        "MEASURED + DOCUMENTED", ("monthly_meter_clean.csv", "data_quality_flags.csv", "Facilities response / original monthly records"),
        ("Request backend meter logs or November daily records if monthly allocation must be reconstructed.", "Exclude October from month-by-month operational diagnosis until evidence is obtained."),
    )


def _scenario_tool(question: str, c: Mapping[str, object], what_if: Mapping[str, float | bool]) -> ToolResult:
    tariff = float(what_if["tariff"])
    saving_factor = float(what_if["saving_factor"])
    capex_override = float(what_if["capex"])
    comparing = any(term in _normalize(question) for term in ("which", "compare", "best value", "fastest", "priority", "rank"))
    rows = []
    for item in SCENARIOS:
        saved = float(item["saved"]) * saving_factor
        capex = capex_override if item["name"] == "Combined package" and capex_override != float(c["combo_capex_cny"]) else float(item["capex"])
        saving = saved * tariff
        payback = capex / saving if saving > 0 else math.inf
        rows.append({
            "name": str(item["name"]), "saved": saved, "saving": saving, "payback": payback,
            "payback_best": capex / (saved * 1.25 * tariff) if saved * tariff > 0 else math.inf,
            "payback_worst": capex / (saved * 0.75 * tariff) if saved * tariff > 0 else math.inf,
        })
    fastest = min(rows, key=lambda row: row["payback"])
    largest = max(rows, key=lambda row: row["saved"])
    combo = next(row for row in rows if row["name"] == "Combined package")

    if comparing:
        body = (
            f"At CNY {tariff:.3f}/kWh, {fastest['name']} has the fastest payback at about {fastest['payback']:.2f} years, while "
            f"{largest['name']} saves the most energy at {largest['saved']/1000:,.2f} MWh/year. "
            f"These optimise different objectives: choose {fastest['name']} for low-cost, rapid payback; choose the combined package for maximum annual impact, with a payback of about {combo['payback']:.2f} years."
        )
        title = "Dynamic Multi-Scenario Ranking"
    else:
        body = (
            f"Under current assumptions, the combined package saves {combo['saved']/1000:,.2f} MWh/year, or about {combo['saved']/float(c['annual_total_kwh'])*100:.2f}% of baseline use. "
            f"At CNY {tariff:.3f}/kWh, annual cost savings are CNY {combo['saving']:,.2f} and simple payback is {combo['payback']:.2f} years. "
            f"Across low/high engineering-screening bounds, payback is approximately {combo['payback_best']:.2f}–{combo['payback_worst']:.2f} years; this is not a statistical confidence interval. "
            f"The parameterized Malaysia carbon scenario is {float(c['combo_carbon_tco2e'])*saving_factor:.2f} tCO₂e/year; it is an assumption, not a Malaysia field result."
        )
        title = "Combined-Package What-If Result"
    calculations = tuple(f"{row['name']}: {row['saved']/1000:.2f} MWh/year saved · CNY {row['saving']:,.0f}/year · {row['payback']:.2f}-year payback" for row in rows)
    return ToolResult(
        "scenario_roi", "rank_and_recalculate_scenarios", title, body,
        "DERIVED + USER WHAT-IF + ASSUMED CAPEX" if what_if["is_what_if"] else "DERIVED + ASSUMED",
        ("scenario_summary.csv", "project_assumptions.json", "project_summary.json"),
        ("Replace assumed CAPEX with supplier quotations before procurement.", "Confirm HVAC schedules and luminaire counts, then design M&V before implementation.", "The billing rule is confirmed; no time-of-use or demand-charge inputs are required."), calculations,
    )


def _pv_tool(c: Mapping[str, object]) -> ToolResult:
    return ToolResult(
        "pv_status", "summarize_pv_operation", "Installed PV Contribution",
        f"A {float(c['pv_capacity_kwp']):.2f} kWp PV system is installed at grid connection point 2, with {float(c['pv_generation_kwh'])/1000:,.2f} MWh measured across 12 months. "
        f"The monthly-constrained hourly reconstruction estimates current grid imports at {float(c['current_grid_import_kwh'])/1000:,.2f} MWh, energy self-sufficiency at {float(c['current_self_sufficiency_pct']):.2f}%, and "
        f"PV self-consumption at {float(c['current_pv_self_consumption_pct']):.2f}%. Those final three values are screening estimates, not grid-point measurements.",
        "MEASURED + DERIVED", ("db_pv_monthly_measured.csv", "target_pv_profile.csv", "loss_aware_metrics.csv", "LDB PV as-built records"),
        ("Export hourly inverter generation and grid connection point 2 import/export data for calibration.", "Require a structural engineer to verify roof capacity before expansion."),
        (f"Annual PV generation / annual building use = {float(c['pv_generation_kwh'])/float(c['annual_total_kwh'])*100:.2f}% (not the self-sufficiency ratio)",),
    )


def _storage_tool(c: Mapping[str, object]) -> ToolResult:
    return ToolResult(
        "storage_sandbox", "compare_storage_strategies", "No Storage Is Installed at reference case · Future Counterfactual Analysis",
        f"reference case currently has no battery storage. The future sandbox assumes a 300 kWh / 120 kW battery. Loss-aware dispatch produces {float(c['loss_aware_grid_import_kwh'])/1000:,.2f} MWh/year of grid imports, "
        f"{float(c['grid_reduction_vs_naive_pct']):.2f}% below the {float(c['naive_grid_import_kwh'])/1000:,.2f} MWh/year rule-based strategy. "
        f"Battery-loss/throughput indicators fall by {float(c['battery_loss_reduction_pct']):.2f}%. This demonstrates dispatch logic; it does not prove that a battery is worth purchasing.",
        "SANDBOX + DERIVED", ("loss_aware_metrics.csv", "loss_aware_hourly_detail.csv", "project_assumptions.json"),
        ("Re-size the battery after high-frequency load and import/export data are available.", "Using the Ningbo reference-case tariff of CNY 0.538/kWh, add battery quotations, maintenance and lifetime data before calculating financial returns."),
        (f"Grid-import difference = {float(c['naive_grid_import_kwh'])-float(c['loss_aware_grid_import_kwh']):,.2f} kWh/year",),
    )


def _gap_tool() -> ToolResult:
    return ToolResult(
        "data_gap", "prioritize_data_requests", "Data-Collection Plan Ranked by Model Value",
        "Priorities are ranked by their ability to change decisions, not by ease of access. First, collect 2–4 weeks of 15-minute reference case main/submeter data to calibrate peaks and intraday shape. "
        "Second, collect hourly inverter generation, export and self-use data to calibrate PV value. Third, measure temperature, RH and CO₂ in 3–6 representative rooms to validate comfort constraints. "
        "Then add meter–space–equipment mapping, HVAC start/stop and fault records, and supplier quotations. Current transparent substitutes are sufficient for screening, but not for guaranteed savings.",
        "MIXED · GAP REGISTER + VALUE-OF-INFORMATION RANKING", ("data_request_tracker.csv", "data_quality_flags.csv", "source_lineage.csv"),
        ("Start with low-cost short-term monitoring; do not wait for a complete BMS upgrade.", "Re-run calibration gates and scenario rankings whenever new data arrive."),
    )


def _comfort_tool(c: Mapping[str, object]) -> ToolResult:
    return ToolResult(
        "comfort_schedule", "check_operating_constraints", "Opening-Hours and Comfort-Constraint Check",
        f"Classrooms are assumed open daily from {c['opening_hours']}, giving 5,110 open hours; the comfort proxy uses {c['comfort_band']} during opening. "
        "This proves only that simulated scenarios respect the defined boundary; it does not prove historical indoor conditions were compliant.",
        "ASSUMED + DERIVED", ("project_assumptions.json", "comfort_proxy_hourly.csv", "run_validation.json"),
        ("Install sensors in representative rooms and record actual holidays and event days.",),
    )


def _governance_tool(c: Mapping[str, object]) -> ToolResult:
    return ToolResult(
        "model_governance", "audit_decision_readiness", "Decisions the Model Can and Cannot Support",
        f"{c['model_version']} supports annual energy baselines, scenario screening, data-collection priorities, interpretation of installed PV and technical comparison of future storage strategies. "
        "It cannot directly support procurement commitments, equipment control, guaranteed savings, precise peak/demand estimates or conclusions about actual indoor comfort. The measured layer includes four monthly meters, monthly PV generation and part of the campus weather; "
        "8,760-hour load/PV profiles and self-consumption are derived; opening hours, the comfort proxy and CAPEX are assumed; the battery is a future sandbox. Zero monthly-reconciliation failures and a successful LP validate internal consistency, not site-validated hourly accuracy.",
        "MIXED · EXPLICIT EVIDENCE HIERARCHY", ("run_validation.json", "donor_profile_model_metrics.json", "source_lineage.csv", "data_quality_flags.csv"),
        ("Calculate CV(RMSE) and NMBE after high-frequency metering is available, then upgrade the calibration level.", "Register the source, time range and use boundary of every new dataset before modelling."),
    )


def _improvement_tool() -> ToolResult:
    return ToolResult(
        "model_improvement", "prioritize_model_upgrades", "Model-Upgrade Priorities and Achievable Boundary",
        "The next version should prioritise observations that enable site calibration, not a more complex algorithm. Priorities are: (1) 2–4 weeks of 15-minute reference case main/submeter data to replace cross-building reconstruction with a reference case-calibrated profile; "
        "(2) synchronous inverter and grid-point data to calibrate PV self-consumption and exports; (3) temperature, RH and CO₂ in representative rooms plus the actual operating calendar to replace the comfort proxy; "
        "(4) current HVAC nameplates, part-load COP and BMS states to improve the HVAC mechanism; and (5) supplier quotations and battery-degradation parameters to improve the financial model. The billing rule is already confirmed, so time-of-use and demand-charge inputs are unnecessary. "
        "Without new evidence, changing the machine-learning algorithm only adds complexity and cannot honestly improve site accuracy.",
        "MODEL READINESS REGISTER + VALUE-OF-INFORMATION",
        ("model_readiness_register.csv", "data_request_tracker.csv", "donor_profile_model_metrics.json", "source_lineage.csv"),
        ("Deploy temporary 15-minute loggers and create a holdout validation set first.", "Report CV(RMSE), NMBE, monthly conservation and evidence class for every upgrade.", "Keep the transparent calendar prior as the baseline every new algorithm must beat."),
        ("Release gate = improved site error + monthly conservation + an explainable evidence boundary; all three must pass.",),
    )


TOOL_BUILDERS = {
    "energy_baseline": lambda q, c, w: _energy_tool(c, w),
    "meter_anomaly": lambda q, c, w: _anomaly_tool(),
    "scenario_roi": _scenario_tool,
    "pv_status": lambda q, c, w: _pv_tool(c),
    "storage_sandbox": lambda q, c, w: _storage_tool(c),
    "data_gap": lambda q, c, w: _gap_tool(),
    "comfort_schedule": lambda q, c, w: _comfort_tool(c),
    "model_governance": lambda q, c, w: _governance_tool(c),
    "model_improvement": lambda q, c, w: _improvement_tool(),
}


TOOL_NAME_TO_INTENT = {
    "query_energy_baseline": "energy_baseline",
    "inspect_meter_quality_event": "meter_anomaly",
    "rank_and_recalculate_scenarios": "scenario_roi",
    "summarize_pv_operation": "pv_status",
    "compare_storage_strategies": "storage_sandbox",
    "prioritize_data_requests": "data_gap",
    "check_operating_constraints": "comfort_schedule",
    "audit_decision_readiness": "model_governance",
    "prioritize_model_upgrades": "model_improvement",
}


_TOOL_DESCRIPTIONS = {
    "query_energy_baseline": "Return reference case annual electricity, EUI, HVAC share and the cost baseline using the Ningbo reference-case tariff of CNY 0.538/kWh.",
    "inspect_meter_quality_event": "Explain the October 2024 aggregate anomaly and the valid public-use boundary.",
    "rank_and_recalculate_scenarios": "Recalculate and compare efficiency measures and payback using a user-defined tariff, savings change or CAPEX.",
    "summarize_pv_operation": "Describe the installed 106.14 kWp PV at grid connection point 2, measured generation and derived self-use relationships.",
    "compare_storage_strategies": "Compare future storage-sandbox strategies while making clear that reference case currently has no storage.",
    "prioritize_data_requests": "Rank missing data and practical substitutes by decision value.",
    "check_operating_constraints": "Check the 08:00–22:00 opening schedule and the valid use boundary of the comfort proxy.",
    "audit_decision_readiness": "Audit which decisions the model can and cannot support and the corresponding evidence classes.",
    "prioritize_model_upgrades": "Prioritise the next data and algorithm upgrades according to site-calibration value.",
}


OPENAI_TOOL_DEFINITIONS: tuple[dict[str, object], ...] = tuple(
    {
        "type": "function",
        "name": name,
        "description": description,
        "strict": True,
        "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
    }
    for name, description in _TOOL_DESCRIPTIONS.items()
)


def execute_energy_tool(
    tool_name: str,
    question: str,
    context: Mapping[str, object] | None = None,
    history: Sequence[str] | None = None,
) -> ToolResult:
    """Execute one approved deterministic project tool selected by an orchestrator."""
    if tool_name not in TOOL_NAME_TO_INTENT:
        raise ValueError(f"Unsupported Irene energy tool: {tool_name}")
    c = _context(context)
    history_context = _history_text(history)
    what_if = _what_if((question or "").strip(), history_context, c)
    intent = TOOL_NAME_TO_INTENT[tool_name]
    return TOOL_BUILDERS[intent](question, c, what_if)


def compose_enhanced_response(
    question: str,
    results: Sequence[ToolResult],
    answer: str,
    model: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
) -> AgentResponse:
    """Compose an auditable response from model prose and deterministic tool results."""
    if not results:
        raise ValueError("At least one deterministic tool result is required")
    primary = results[0]
    intents = tuple(dict.fromkeys(result.intent for result in results))
    sources = tuple(dict.fromkeys(source for result in results for source in result.sources))
    actions = tuple(dict.fromkeys(action for result in results for action in result.actions))
    calculations = tuple(item for result in results for item in result.calculations)
    evidence = " · ".join(dict.fromkeys(result.evidence for result in results))
    fallback_answer = "\n\n".join(f"【{result.title}】{result.body}" for result in results)
    follow_ups = tuple(dict.fromkeys(item for intent in intents for item in FOLLOW_UPS[intent]))[:3]
    readiness = " · ".join(dict.fromkeys(DECISION_READINESS[intent] for intent in intents))
    tool_names = tuple(result.tool for result in results)
    return AgentResponse(
        primary.intent,
        primary.tool if len(results) == 1 else "openai_multi_tool_orchestrator",
        primary.title if len(results) == 1 else f"{primary.title} ({len(results)} analyses combined)",
        answer.strip() or fallback_answer,
        evidence,
        sources,
        actions,
        "The model handles understanding and expression; project values come from deterministic tools, and reliability remains governed by evidence class and decision readiness.",
        intents,
        (
            "OpenAI interprets the question and selects project tools",
            "Run deterministic reference case tools: " + " → ".join(tool_names),
            "Compose the answer from tool outputs while preserving evidence boundaries",
        ),
        calculations,
        follow_ups,
        f"OPENAI RESPONSES · {model} · 9 AUDITABLE TOOLS",
        1.0,
        readiness,
        ("model-selected tool route",),
        (),
        "openai",
        "OpenAI Responses API",
        input_tokens,
        output_tokens,
        len(results),
        "",
    )


FOLLOW_UPS = {
    "energy_baseline": ("If the tariff rises by 20%, what will the annual electricity cost be?", "Which HVAC end use should be investigated first?"),
    "meter_anomaly": ("Does this anomaly affect the annual saving rate?", "If October must be estimated, what boundary should be applied?"),
    "scenario_roi": ("If the tariff falls by 10%, compare every measure again.", "What if the combined-package CAPEX becomes CNY 80,000?"),
    "pv_status": ("What share of annual use does PV generate, and why is it not the self-sufficiency ratio?", "How much further could storage reduce grid imports?"),
    "storage_sandbox": ("Why does the loss-aware strategy outperform the rule-based strategy?", "Which data are required before investing in storage?"),
    "data_gap": ("If only one dataset can be collected, which should it be?", "Which conclusions would each dataset change?"),
    "comfort_schedule": ("How can short-term monitoring validate the comfort proxy?", "What would change if opening hours were reduced by one hour?"),
    "model_governance": ("Which conclusion is currently the most mature?", "How can the model become procurement-ready?"),
    "model_improvement": ("If only one dataset can be added, what should be collected first?", "Which site-error metrics should be used after the upgrade?"),
}


def answer_energy_question(
    question: str,
    context: Mapping[str, object] | None = None,
    history: Sequence[str] | None = None,
) -> AgentResponse:
    """Plan and execute a bounded, offline energy-analysis turn."""
    c = _context(context)
    text = (question or "").strip()
    if not text:
        return AgentResponse(
            "help", "capability_router", "Enter a Project Question",
            "I can combine queries about energy, anomalies, scenarios, PV, storage, data gaps, model boundaries and the upgrade roadmap. I can also recalculate results for a user-defined tariff, savings change or investment amount.",
            "SYSTEM", ("Agent capability register",), ("Try a question containing 'what if' or 'compare'.",), "No project tool executed",
            follow_ups=QUICK_PROMPTS[:2], route_confidence=0.0,
        )

    intents, scores, contextual = _route(text, history)
    if not intents:
        return AgentResponse(
            "capability_help", "capability_router", "Question Outside the reference case Local-Model Evidence Boundary",
            "I understand that this is a new question, but the current local tools cover only Irene energy and decision analysis. To avoid fabrication, I will not invent operations or external facts that are not connected to the project.",
            "SYSTEM BOUNDARY", ("Agent capability register",), ("Relate the question to energy, equipment, scenarios, data or model reliability.",),
            "Intent match was insufficient, so the request was safely declined (heuristic score, not statistical confidence).", plan_steps=("Analyse the question", "Check tool coverage", "Apply the evidence-boundary guardrail"), route_confidence=max(scores.values()),
        )

    history_context = _history_text(history) if contextual else ""
    what_if = _what_if(text, history_context, c)
    results = [TOOL_BUILDERS[intent](text, c, what_if) for intent in intents]
    primary = results[0]
    multi = len(results) > 1
    answer_parts = [f"【{result.title}】{result.body}" for result in results]
    sources = tuple(dict.fromkeys(source for result in results for source in result.sources))
    actions = tuple(dict.fromkeys(action for result in results for action in result.actions))
    calculations = tuple(calculation for result in results for calculation in result.calculations)
    evidence = " · ".join(dict.fromkeys(result.evidence for result in results))
    top_score = scores[intents[0]]
    route_confidence = min(0.98, 0.42 + top_score * 0.56)
    confidence_level = "High" if route_confidence >= 0.80 else "Medium" if route_confidence >= 0.60 else "Limited"
    context_note = "; previous-question context was retained" if contextual else ""
    boundary = "; dynamic values belong to a user-defined scenario" if what_if["is_what_if"] else ""
    routing_text = f"{history_context} {text}" if contextual else text
    direct_hits = _direct_signal_hits(routing_text)
    matched_concepts = tuple(dict.fromkeys(signal for intent in intents for signal in direct_hits[intent]))
    readiness = " · ".join(dict.fromkeys(DECISION_READINESS[intent] for intent in intents))
    warnings = tuple(what_if.get("warnings", ()))
    follow_ups = tuple(dict.fromkeys(item for intent in intents for item in FOLLOW_UPS[intent]))[:3]
    plan_steps = (
        f"Interpret the question and extract conditions{' (including conversational context)' if contextual else ''}",
        f"Plan {len(results)} local tool call(s): " + " → ".join(result.tool for result in results),
        "Run deterministic calculations and verify evidence classes",
        "Combine conclusions, limitations and next actions",
    )
    return AgentResponse(
        primary.intent,
        primary.tool if not multi else "local_multi_tool_planner",
        primary.title if not multi else f"{primary.title} ({len(results)} analyses combined)",
        "\n\n".join(answer_parts),
        evidence,
        sources,
        actions,
        f"{confidence_level} match: intent score {route_confidence*100:.0f}% (heuristic, not statistical confidence){context_note}{boundary}. Conclusion reliability is governed by evidence class and decision readiness.",
        tuple(intents),
        plan_steps,
        calculations,
        follow_ups,
        "LOCAL DOMAIN PLANNER · NO EXTERNAL API",
        route_confidence,
        readiness,
        matched_concepts,
        warnings,
    )
