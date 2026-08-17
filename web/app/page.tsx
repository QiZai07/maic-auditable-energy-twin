"use client";

import { useEffect, useMemo, useState } from "react";
import { AgentResponse, answerEnergyQuestion, quickPrompts } from "./energy-agent";
import { AgentStatus, askEnhancedAgent, getAgentStatus } from "./openai-agent-client";
import {
  type ClientManifest,
  type CloudRecognition,
  assessClientReadiness,
  CLOUD_EXTENSIONS,
  downloadMapping,
  fieldLibrary,
  parseClientFile,
  recogniseClientDocument,
} from "./client-onboarding";
import { assessClientProject, downloadClientDeliverable, type ClientProjectProfile } from "./client-project";

type ModuleId = "overview" | "monthly" | "hourly" | "scenarios" | "storage" | "twin" | "agent" | "onboarding";

const modules: { id: ModuleId; number: string; label: string; eyebrow: string }[] = [
  { id: "overview", number: "01", label: "Project Overview", eyebrow: "Executive view" },
  { id: "monthly", number: "02", label: "Monthly Evidence", eyebrow: "Aggregate evidence" },
  { id: "hourly", number: "03", label: "Hourly Evidence", eyebrow: "Auditable estimation" },
  { id: "scenarios", number: "04", label: "Efficiency & ROI", eyebrow: "Scenario intelligence" },
  { id: "storage", number: "05", label: "PV & Future Storage", eyebrow: "PV now · storage future" },
  { id: "twin", number: "06", label: "Twin & Data", eyebrow: "Evidence governance" },
  { id: "agent", number: "07", label: "Analysis Agent", eyebrow: "Auditable analysis agent" },
  { id: "onboarding", number: "08", label: "Client Data Onboarding", eyebrow: "Client-owned evidence" },
];

const monthly = [
  ["2024-07", 57109.30], ["2024-08", 31727.36], ["2024-09", 22055.70],
  ["2024-10", 2633.67], ["2024-11", 50557.25], ["2024-12", 32469.77],
  ["2025-01", 21583.08], ["2025-02", 24317.63], ["2025-03", 26449.75],
  ["2025-04", 24710.53], ["2025-05", 27132.60], ["2025-06", 24930.05],
] as const;

const meters = [
  { name: "MTR-A", group: "Non-HVAC", annual: 137430.20, flag: "Synthetic public record" },
  { name: "MTR-B", group: "Non-HVAC", annual: 107980.88, flag: "Synthetic public record" },
  { name: "MTR-C", group: "Rooftop HVAC", annual: 53140.77, flag: "Synthetic public record" },
  { name: "MTR-D", group: "Rooftop HVAC", annual: 47124.84, flag: "Synthetic public record" },
];

const hourly = [
  [0, 14.40, 1.96], [1, 14.40, 1.96], [2, 14.40, 1.96], [3, 14.40, 1.96],
  [4, 14.40, 1.96], [5, 14.40, 1.96], [6, 14.40, 1.96], [7, 14.40, 1.96],
  [8, 56.33, 17.47], [9, 59.10, 19.77], [10, 62.53, 21.91], [11, 66.24, 23.75],
  [12, 69.73, 25.17], [13, 72.49, 26.05], [14, 74.09, 26.36], [15, 74.24, 26.05],
  [16, 72.90, 25.17], [17, 70.19, 23.75], [18, 66.48, 21.91], [19, 62.26, 19.77],
  [20, 58.09, 17.47], [21, 54.50, 15.17], [22, 14.40, 1.96], [23, 14.40, 1.96],
] as const;

const scenarios = [
  { id: "hvac", name: "Comfort-constrained HVAC optimisation", p10: 5369.11, p50: 7158.82, p90: 8948.52, rate: 2.07, saving: 3851.44, capex: 8000, payback: 2.08, carbon: 5.298 },
  { id: "schedule", name: "HVAC operating-hours optimisation", p10: 3758.38, p50: 5011.17, p90: 6263.96, rate: 1.45, saving: 2696.01, capex: 12000, payback: 4.45, carbon: 3.708 },
  { id: "led", name: "LED lighting retrofit", p10: 14724.66, p50: 19632.89, p90: 24541.11, rate: 5.68, saving: 10562.49, capex: 45000, payback: 4.26, carbon: 14.528 },
  { id: "plug", name: "Plug-load and standby management", p10: 7334.12, p50: 9778.82, p90: 12223.53, rate: 2.83, saving: 5261.01, capex: 18000, payback: 3.42, carbon: 7.236 },
  { id: "combo", name: "Combined package (HVAC + LED + operations)", p10: 31186.27, p50: 41581.69, p90: 51977.11, rate: 12.03, saving: 22370.95, capex: 62000, payback: 2.77, carbon: 30.770 },
];

const storage = [
  { name: "Current PV · no storage", grid: 230970.24, cost: 124261.99, loss: 0, throughput: 0, self: 33.18, pv: 90.87 },
  { name: "Future battery · rule-based", grid: 233924.17, cost: 125851.20, loss: 8473.55, throughput: 165342.79, self: 32.33, pv: 95.24 },
  { name: "Future battery · loss-aware", grid: 224486.41, cost: 120773.69, loss: 700.47, throughput: 13668.14, self: 35.06, pv: 96.56 },
];

const requests = [
  { priority: "P0", need: "Client 15-minute/hourly electricity", status: "Not included in public demo", action: "Upload through the governed onboarding workspace or use a temporary logger", impact: "Supports screening now and later calibration" },
  { priority: "P0", need: "Opening hours and comfort", status: "Defined assumption", action: "Daily 08:00–22:00; comfortable conditions use a synthetic proxy", impact: "Constrains operating periods and savings" },
  { priority: "P0", need: "HVAC equipment and COP", status: "Design records available", action: "18 outdoor and 80 indoor units; rated EER 3.59 with uncertainty", impact: "Calibrates HVAC capacity and controls" },
  { priority: "P0", need: "PV hourly and export data", status: "Approved aggregates · hourly synthetic", action: "Replace the public demo profile with authorized inverter and grid data", impact: "Calibrates self-consumption while preserving the metering boundary" },
  { priority: "P1", need: "Local weather", status: "Synthetic public profile", action: "Use an approved local station or client sensors", impact: "Normalises weather over the meter period" },
  { priority: "P1", need: "Supplier quotes and roof capacity", status: "Unavailable / cannot be inferred", action: "Use engineering screening bounds; require structural review for expansion", impact: "Preserves investment and safety boundaries" },
];

const qualityRows = [
  ["DQ-001", "HIGH", "Public aggregate · Oct 2024", "Approved aggregate contains a documented anomaly", "Retain only the aggregate; publish no original meter row"],
  ["DQ-002", "MEDIUM", "Weather", "No site weather rows are distributed", "Use a deterministic synthetic weather profile"],
  ["DQ-003", "HIGH", "Hourly load", "No original 15-minute/hourly meter rows are public", "Create monthly-constrained synthetic estimates only"],
  ["DQ-005", "MEDIUM", "PV hourly/export", "Only approved aggregate case values are public", "Synthetic hourly shape; self-consumption remains estimated"],
  ["DQ-006", "MEDIUM", "Indoor comfort", "No historical temperature, RH or CO₂", "08:00–22:00 comfort proxy, explicitly not measured"],
  ["QA-001", "PASS", "Monthly energy conservation", "0 reconciliation failures", "Every meter-month reconciles"],
];

const modelReadiness = [
  ["Monthly energy baseline", "Approved aggregate + synthetic", "Annual analysis", "Authorized client meter export"],
  ["8,760-hour load reconstruction", "Synthetic + derived", "Scenario screening", "2–4 weeks of authorized 15-minute metering"],
  ["Comfort constraint proxy", "Assumed + derived", "Constraint testing", "Temperature/RH/CO₂ in representative rooms"],
  ["Installed PV generation", "Approved aggregate", "Annual analysis", "Authorized hourly inverter and grid-point data"],
  ["PV self-consumption / grid import", "Derived", "Scenario screening", "Synchronous 15-minute import/export"],
  ["Efficiency and ROI", "Derived + assumed", "Scenario screening", "Supplier quotes and M&V"],
  ["Future storage dispatch", "Technology sandbox", "Not procurement-ready", "High-frequency data, quotes and degradation"],
  ["Local analysis Agent", "Deterministic + auditable", "Decision support", "Regression set from real questions"],
];

function format(value: number, digits = 1) {
  return value.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

function MetricCard({ label, value, unit, note, tone = "cyan" }: { label: string; value: string; unit?: string; note: string; tone?: string }) {
  return (
    <article className={`metric-card tone-${tone}`}>
      <p>{label}</p>
      <div className="metric-value">{value}<small>{unit}</small></div>
      <span>{note}</span>
    </article>
  );
}

function PageHeader({ number, title, description, code }: { number: string; title: string; description: string; code: string }) {
  return (
    <header className="page-header">
      <div><span>MODULE {number}</span><h2>{title}</h2><p>{description}</p></div>
      <b>{code}</b>
    </header>
  );
}

function Notice({ tone = "info", title, children }: { tone?: "info" | "warning" | "danger" | "success"; title: string; children: React.ReactNode }) {
  return <div className={`notice ${tone}`}><strong>{title}</strong><span>{children}</span></div>;
}

function SectionTitle({ kicker, title, detail }: { kicker: string; title: string; detail?: string }) {
  return <div className="section-title"><div><span>{kicker}</span><h3>{title}</h3></div>{detail && <p>{detail}</p>}</div>;
}

function MonthlyBars({ compact = false }: { compact?: boolean }) {
  const max = Math.max(...monthly.map((item) => item[1]));
  return (
    <div className={`vertical-chart ${compact ? "compact" : ""}`} role="img" aria-label="Reference monthly electricity chart">
      <div className="chart-grid"><i/><i/><i/><i/></div>
      {monthly.map(([month, value]) => (
        <div className="bar-slot" key={month} title={`${month}: ${format(value / 1000, 2)} MWh`}>
          <div className={`vbar ${month === "2024-10" ? "incident" : ""}`} style={{ height: `${Math.max(5, (value / max) * 100)}%` }}><em>{format(value / 1000, 1)}</em></div>
          <label>{month.slice(5)}</label>
        </div>
      ))}
    </div>
  );
}

function Overview() {
  return <>
    <PageHeader number="01" title="Project Overview" description="T1 clean-energy decision support from approved aggregate evidence to investment-screening results, with a governed path from client files to verified savings." code="T1 · AI FOR CLEAN ENERGY" />
    <Notice title="Malaysia deployment pathway">Validated on a Ningbo reference case; designed for configurable deployment in Malaysia, pending local pilot validation.</Notice>
    <div className="metric-grid">
      <MetricCard label="Annual electricity" value="345.7" unit="MWh" note="Total from four meters over 12 months" />
      <MetricCard label="Energy intensity" value="55.47" unit="kWh/m²·year" note="Gross floor area: 6,231.26 m²" tone="blue" />
      <MetricCard label="HVAC share" value="29.01" unit="%" note="HVAC electricity: 100.3 MWh" tone="amber" />
      <MetricCard label="Installed PV" value="106.14" unit="kWp" note="Approved aggregate generation: 126.23 MWh · no storage" tone="green" />
    </div>
    <div className="evidence-strip">
      <div><i className="measured"/><b>AGGREGATE</b><span>Approved monthly energy and PV results</span></div>
      <div><i className="derived"/><b>SYNTHETIC</b><span>Public row-level load, weather and PV profiles</span></div>
      <div><i className="assumed"/><b>ASSUMED</b><span>08:00–22:00 schedule and CAPEX</span></div>
      <div><i className="sandbox"/><b>SANDBOX</b><span>Future storage dispatch</span></div>
    </div>
    <div className="split overview-split">
      <section className="panel chart-panel">
        <SectionTitle kicker="Approved aggregate baseline" title="Reference Monthly Electricity Profile" detail="Jul 2024–Jun 2025 · MWh" />
        <MonthlyBars compact />
        <div className="incident-key"><i/> Approved aggregate anomaly retained; original meter rows excluded</div>
      </section>
      <section className="panel decision-panel">
        <SectionTitle kicker="Decision snapshot" title="Current Screening Results" />
        <div className="decision-list">
          <div><span>Combined package P50 savings</span><strong>41.6 MWh<small>12.03% of baseline</small></strong></div>
          <div><span>Annual cost savings</span><strong>CNY 22.4k<small>Ningbo case: saved kWh × CNY 0.538</small></strong></div>
          <div><span>Simple payback</span><strong>2.77 years<small>CAPEX is assumed</small></strong></div>
          <div><span>Parameterized Malaysia carbon scenario</span><strong>30.8 tCO₂e<small>assumption · not a field result</small></strong></div>
          <div><span>Future loss-aware grid-import reduction</span><strong className="positive">−4.03%<small>vs future rule-based battery</small></strong></div>
        </div>
      </section>
    </div>
    <section className="panel table-panel">
      <SectionTitle kicker="Commercial pathway" title="A file-based diagnosis opens the customer relationship" detail="Policy signal, not a market-size claim" />
      <div className="table-wrap"><table><tbody>
        <tr><th>Target customers</th><td>Commercial buildings · campuses · industrial parks · energy service companies (ESCOs)</td></tr>
        <tr><th>First paid product</th><td>File-based energy diagnosis · confirmed baseline · auditable report · action shortlist</td></tr>
        <tr><th>Revenue</th><td>One-off diagnosis fee · annual subscription · implementation and M&amp;V service fees</td></tr>
        <tr><th>Competitive edge</th><td>Client-data intake · confirmation gate · evidence chain · deterministic calculations · privacy-safe delivery</td></tr>
        <tr><th>Pilot path</th><td>File audit → temporary metering → calibration → savings verification → multi-site scale</td></tr>
      </tbody></table></div>
      <p>Malaysia&apos;s EECA 2024 has been in force since 1 January 2025, while the National Energy Transition Roadmap identifies audits and ESCO delivery as transition priorities. <a href="https://www.st.gov.my/stakeholders/energy-efficiency/energy-efficiency-and-conservation-act-eeca-2024" target="_blank" rel="noreferrer">Energy Commission</a> · <a href="https://ekonomi.gov.my/sites/default/files/2023-09/National%20Energy%20Transition%20Roadmap_0.pdf" target="_blank" rel="noreferrer">Ministry of Economy</a></p>
    </section>
  </>;
}

function Monthly() {
  const maxMeter = Math.max(...meters.map((item) => item.annual));
  return <>
    <PageHeader number="02" title="Reference Monthly Case" description="Break down four generic meter series while retaining the approved aggregate anomaly in a privacy-safe audit view." code="AGGREGATE + SYNTHETIC" />
    <Notice tone="danger" title="Aggregate anomaly retained">The approved October 2024 aggregate is retained as a documented case-study anomaly. Public meter rows and identifiers are deterministic synthetic records; no original meter record is distributed.</Notice>
    <section className="panel chart-panel">
      <SectionTitle kicker="Monthly profile" title="Twelve Months of Electricity Evidence" detail="Hover over bars for exact values" />
      <MonthlyBars />
    </section>
    <div className="split equal">
      <section className="panel">
        <SectionTitle kicker="Meter contribution" title="Annual Meter Contribution" detail="MWh" />
        <div className="hbar-chart">
          {meters.map((meter) => <div className="hbar-row" key={meter.name}>
            <div><b>{meter.name}</b><span>{meter.group}</span></div>
            <div className="hbar-track"><i className={meter.group === "Rooftop HVAC" ? "hvac" : "non-hvac"} style={{ width: `${(meter.annual / maxMeter) * 100}%` }}/></div>
            <strong>{format(meter.annual / 1000, 1)}</strong>
          </div>)}
        </div>
      </section>
      <section className="panel table-panel">
        <SectionTitle kicker="Data-quality register" title="Quality Flags" />
        <div className="table-wrap"><table><thead><tr><th>ID</th><th>Severity</th><th>Scope</th><th>Handling</th></tr></thead><tbody>
          {qualityRows.map((row) => <tr key={row[0]}><td>{row[0]}</td><td><span className={`severity ${row[1].toLowerCase()}`}>{row[1]}</span></td><td>{row[2]}</td><td>{row[4]}</td></tr>)}
        </tbody></table></div>
      </section>
    </div>
  </>;
}

function Hourly() {
  const max = Math.max(...hourly.map((item) => item[1]));
  return <>
    <PageHeader number="03" title="Hourly Estimate & Evidence" description="Expose the sources, validation gate and monthly reconciliation of the 8,760-hour estimate without presenting estimates as measurements." code="AUDITABLE ESTIMATION" />
    <div className="metric-grid">
      <MetricCard label="Estimated profile" value="8,760" unit="hours" note="Monthly-constrained synthetic public profile" />
      <MetricCard label="Reference weather" value="4,416" unit="hours" note="Deterministic synthetic reference coverage" tone="green" />
      <MetricCard label="Synthetic extension" value="4,344" unit="hours" note="Every synthetic hour is labelled" tone="amber" />
      <MetricCard label="Reconciliation failures" value="0" unit="months" note="Hourly totals reconciled to monthly meters" tone="green" />
    </div>
    <Notice title="Candidate-model performance gate enforced">The HistGradientBoosting candidate did not outperform the transparent calendar prior and was rejected. The selected method&apos;s validation NMAE is 14.36%. Public validation uses deterministic synthetic temporal shapes and does not claim site-hourly accuracy.</Notice>
    <Notice tone="success" title="Opening and comfort constraints enforced">Classrooms are assumed open daily from 08:00 to 22:00. During opening, the proxy enforces 20–26°C, 40–60% RH and CO₂ ≤ 1,000 ppm. These indoor values are simulation assumptions, not sensor measurements.</Notice>
    <div className="split hourly-split">
      <section className="panel chart-panel">
        <SectionTitle kicker="Representative weekday" title="Monthly-Constrained Hourly Load" detail="7 Aug 2024 · derived, not measured" />
        <div className="hour-chart" role="img" aria-label="Representative estimated hourly load">
          {hourly.map(([hour, total, hvac]) => <div className="hour-slot" key={hour} title={`${hour}:00 · Total load ${format(total, 2)} kWh · HVAC ${format(hvac, 2)} kWh`}>
            <div className="hour-stack" style={{ height: `${(total / max) * 100}%` }}><i style={{ height: `${((total - hvac) / total) * 100}%` }}/><b style={{ height: `${(hvac / total) * 100}%` }}/></div>
            <span>{hour % 3 === 0 ? `${String(hour).padStart(2, "0")}:00` : ""}</span>
          </div>)}
        </div>
        <div className="legend"><span><i className="non"/>Non-HVAC</span><span><i className="hvac"/>HVAC</span></div>
      </section>
      <section className="panel gate-panel">
        <SectionTitle kicker="Model gate" title="Transparent Method Selected" />
        <div className="gate-score"><span>SELECTED</span><strong>14.36%</strong><p>Holdout NMAE of synthetic shape</p></div>
        <div className="gate-flow"><div><b>Calendar prior</b><span>transparent baseline</span></div><i>beats</i><div className="rejected"><b>ML candidate</b><span>rejected by gate</span></div></div>
        <p className="boundary-copy">Scope: validation of a normalised synthetic temporal shape. It must never be interpreted as measured site-hourly accuracy.</p>
      </section>
    </div>
  </>;
}

function Scenarios() {
  const [selectedId, setSelectedId] = useState("combo");
  const selected = scenarios.find((item) => item.id === selectedId) ?? scenarios[4];
  const maxP90 = Math.max(...scenarios.map((item) => item.p90));
  return <>
    <PageHeader number="04" title="Efficiency Scenarios & Investment Screening" description="Express uncertainty through low/base/high engineering-screening bounds while keeping CAPEX assumptions beside investment results." code="SCENARIO INTELLIGENCE" />
    <div className="scenario-tabs" role="tablist" aria-label="Efficiency scenarios">
      {scenarios.map((item) => <button key={item.id} role="tab" aria-selected={selectedId === item.id} onClick={() => setSelectedId(item.id)}>{item.name.replace(" (HVAC + LED + operations)", "")}</button>)}
    </div>
    <div className="metric-grid">
      <MetricCard label="P50 annual saving" value={format(selected.p50 / 1000, 1)} unit="MWh" note={`P10 ${format(selected.p10 / 1000, 1)} · P90 ${format(selected.p90 / 1000, 1)}`} />
      <MetricCard label="Saving rate" value={format(selected.rate, 2)} unit="%" note="Relative to the annual baseline" tone="blue" />
      <MetricCard label="Annual cost saving" value={`CNY ${format(selected.saving / 1000, 1)}k`} unit="" note="Ningbo reference case: saved kWh × CNY 0.538" tone="green" />
      <MetricCard label="Simple payback" value={format(selected.payback, 2)} unit="years" note="Assumed CAPEX requires supplier quotations" tone="amber" />
    </div>
    <div className="split scenario-split">
      <section className="panel">
        <SectionTitle kicker="Engineering screening bounds" title="Scenario Savings Range" detail="P10/P50/P90 labels · MWh/year" />
        <div className="range-chart">
          {scenarios.map((item) => <button className={selectedId === item.id ? "selected" : ""} onClick={() => setSelectedId(item.id)} key={item.id}>
            <span>{item.name}</span><div><i style={{ width: `${(item.p90 / maxP90) * 100}%` }}/><b style={{ width: `${(item.p50 / maxP90) * 100}%` }}/><em style={{ left: `${(item.p10 / maxP90) * 100}%` }}/></div><strong>{format(item.p50 / 1000, 1)}</strong>
          </button>)}
        </div>
      </section>
      <section className="panel decision-panel">
        <SectionTitle kicker="Investment evidence" title="Decision Readiness" />
        <div className="decision-list compact-list">
          <div><span>Assumed CAPEX</span><strong>CNY {format(selected.capex, 0)}<small>screening only</small></strong></div>
          <div><span>Parameterized Malaysia carbon scenario</span><strong>{format(selected.carbon, 2)} tCO₂e<small>assumption · not a field result</small></strong></div>
          <div><span>Quotation status</span><strong className="caution">Not obtained<small>supplier quote needed</small></strong></div>
          <div><span>Next decision gate</span><strong>Site verification<small>schedule + equipment</small></strong></div>
        </div>
      </section>
    </div>
    <Notice tone="warning" title="Investment conclusion boundary">The Ningbo reference-case billing rule is electricity bill = kWh × CNY 0.538, with no time-of-use, demand or other charge components. The Malaysia carbon output is a parameterized scenario assumption, not a Malaysia field result. P10/P50/P90 use 0.75/1.00/1.25 engineering-screening multipliers, not probability quantiles calibrated from site data. Supplier quotations and post-implementation M&amp;V are still required before procurement or guaranteed-savings decisions.</Notice>
  </>;
}

function Storage() {
  const maxGrid = Math.max(...storage.map((item) => item.grid));
  const maxThroughput = Math.max(...storage.map((item) => item.throughput));
  return <>
    <PageHeader number="05" title="Installed PV & Future Storage" description="Use the installed 106.14 kWp PV system at grid connection point 2 as the current case, then compare no storage with two future battery strategies." code="PV NOW · STORAGE FUTURE" />
    <Notice tone="warning" title="Current assets and future scenarios are strictly separated">The anonymized reference case includes an approved aggregate 126.23 MWh of annual PV generation and currently has no battery storage. The 300 kWh / 120 kW battery is used only in a future loss-aware technology sandbox.</Notice>
    <div className="metric-grid">
      <MetricCard label="Aggregate PV generation" value="126.23" unit="MWh" note="Twelve approved aggregate monthly anchors" tone="green" />
      <MetricCard label="Estimated self-sufficiency" value="33.18" unit="%" note="Screening estimate from synthetic hourly profiles" />
      <MetricCard label="Grid import vs rule-based" value="−4.03" unit="%" note="Loss-aware strategy reduces grid import to 224.5 MWh" tone="green" />
      <MetricCard label="Battery loss vs rule-based" value="−91.73" unit="%" note="Future storage sandbox only" tone="amber" />
    </div>
    <div className="strategy-grid">
      {storage.map((item, index) => <article className={`strategy-card ${index === 2 ? "winner" : ""}`} key={item.name}>
        <div className="strategy-head"><span>0{index + 1}</span><h3>{item.name}</h3>{index === 2 && <b>SELECTED</b>}</div>
        <p>Grid import</p><strong>{format(item.grid / 1000, 1)} <small>MWh</small></strong>
        <div className="strategy-bar"><i style={{ width: `${(item.grid / maxGrid) * 100}%` }}/></div>
        <dl><div><dt>Annual cost</dt><dd>¥{format(item.cost / 1000, 1)}k</dd></div><div><dt>Self sufficiency</dt><dd>{format(item.self, 2)}%</dd></div><div><dt>PV self-use estimate</dt><dd>{format(item.pv, 2)}%</dd></div><div><dt>Battery loss</dt><dd>{format(item.loss / 1000, 2)} MWh</dd></div></dl>
        {item.throughput > 0 && <div className="throughput"><span>Battery throughput</span><i><b style={{ width: `${(item.throughput / maxThroughput) * 100}%` }}/></i><strong>{format(item.throughput / 1000, 1)} MWh</strong></div>}
      </article>)}
    </div>
    <div className="balance-band"><span>ENERGY BALANCE</span><b>Monthly conservation for current PV · SOC conservation for future batteries</b><p>The linear programme uses the Ningbo reference-case tariff of CNY 0.538/kWh and constrains power, efficiency and terminal SOC = 0. Procurement still requires quotations, maintenance and lifetime data.</p><i>LP SOLVED · REFERENCE TARIFF</i></div>
  </>;
}

function Twin() {
  const [filter, setFilter] = useState<"ALL" | "P0" | "P1">("P0");
  const visible = useMemo(() => filter === "ALL" ? requests : requests.filter((item) => item.priority === filter), [filter]);
  return <>
    <PageHeader number="06" title="Digital Twin & Missing Evidence" description="Bring the building–floor–system–meter/model relationships and next data-collection tasks into one evidence-governance view." code="EVIDENCE GOVERNANCE" />
    <div className="metric-grid">
      <MetricCard label="Twin entities" value="15" unit="objects" note="Building, floors, systems, meters and models" />
      <MetricCard label="Installed PV" value="106.14" unit="kWp" note="Grid connection point 2 · no storage" tone="green" />
      <MetricCard label="Opening hours" value="08—22" unit="daily" note="Comfort proxy covers all opening hours" tone="amber" />
      <MetricCard label="Source lineage" value="12+" unit="sources" note="Provenance, availability and use boundaries" tone="blue" />
    </div>
    <section className="panel topology-panel">
      <SectionTitle kicker="Twin topology" title="Traceable Entity Relationships" detail="Building → Floor → System → Meter / Model" />
      <div className="topology">
        <article><span>BUILDING</span><h3>Ningbo Reference Building</h3><p>6,231.26 m² · 3 floors · identity anonymized</p><b>● approved aggregate</b></article>
        <i>→</i><article><span>FLOORS</span><h3>1F · 2F · 3F</h3><p>Assumed open daily 08:00–22:00; comfort values are a synthetic proxy</p><b>● documented + assumed</b></article>
        <i>→</i><article><span>SYSTEMS</span><h3>Metering · HVAC · PV</h3><p>Four monthly meters, VRF design schedule and 106.14 kWp PV</p><b>● measured + design</b></article>
        <i>→</i><article><span>MODELS</span><h3>8,760 · Comfort · Loss-aware</h3><p>Monthly-constrained hourly estimates; storage is a future scenario only</p><b>● derived + sandbox</b></article>
      </div>
    </section>
    <section className="panel table-panel">
      <SectionTitle kicker="Decision readiness register" title="Model Readiness & Highest-Value Upgrades" detail="Not a single accuracy score" />
      <div className="table-wrap"><table><thead><tr><th>Submodel</th><th>Evidence</th><th>Current readiness</th><th>Highest-value upgrade</th></tr></thead><tbody>
        {modelReadiness.map((row) => <tr key={row[0]}><td>{row[0]}</td><td>{row[1]}</td><td>{row[2]}</td><td>{row[3]}</td></tr>)}
      </tbody></table></div>
    </section>
    <div className="request-head"><SectionTitle kicker="Next evidence actions" title="Next Data Collection" detail={`${visible.length} items shown`} /><div>{(["ALL", "P0", "P1"] as const).map((item) => <button key={item} className={filter === item ? "active" : ""} onClick={() => setFilter(item)}>{item}</button>)}</div></div>
    <div className="request-grid">
      {visible.map((item) => <article key={item.need}><div><b>{item.priority}</b><span>{item.status}</span></div><h3>{item.need}</h3><p>{item.action}</p><footer><span>WHY IT MATTERS</span>{item.impact}</footer></article>)}
    </div>
    <Notice title="Screening-stage substitutes exist for every critical gap">Use a monthly-constrained 8,760-hour estimate when high-frequency meters are unavailable; a comfort proxy when indoor records are missing; approved aggregate PV anchors with a synthetic intraday shape; and engineering-screening bounds when quotations are missing. Substitutes are not site calibration, and any additional rooftop capacity still requires structural-engineer review.</Notice>
  </>;
}

type AgentMessage = {
  id: number;
  role: "user" | "assistant";
  content?: string;
  response?: AgentResponse;
};

const welcomeMessage: AgentMessage = {
  id: 0,
  role: "assistant",
  content: "Hello, I am the Irene hybrid energy-analysis Agent. In both local and OpenAI-enhanced modes, the same auditable tools calculate every project number. Enhanced mode improves understanding, tool orchestration and answer composition. Try: ‘If the tariff rises by 20%, which measure pays back fastest and which saves the most energy?’ Then ask ‘What if it falls by 10%?’ and I will retain the context.",
};

const initialAgentStatus: AgentStatus = {
  configured: false,
  provider: "OpenAI",
  defaultModel: "gpt-5.6-terra",
  allowedModels: ["gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.6-sol"],
  defaultEffort: "medium",
  keyLocation: "missing",
  fallback: "local",
};

function Agent() {
  const [messages, setMessages] = useState<AgentMessage[]>([welcomeMessage]);
  const [input, setInput] = useState("");
  const [engine, setEngine] = useState<"local" | "openai">("local");
  const [status, setStatus] = useState<AgentStatus>(initialAgentStatus);
  const [model, setModel] = useState(initialAgentStatus.defaultModel);
  const [effort, setEffort] = useState(initialAgentStatus.defaultEffort);
  const [loading, setLoading] = useState(false);
  const [statusChecked, setStatusChecked] = useState(false);
  const latest = [...messages].reverse().find((message) => message.response)?.response;

  const refreshStatus = async () => {
    const nextStatus = await getAgentStatus();
    setStatus(nextStatus);
    setModel((current) => nextStatus.allowedModels.includes(current) ? current : nextStatus.defaultModel);
    setEffort(nextStatus.defaultEffort);
    setStatusChecked(true);
  };

  useEffect(() => {
    const controller = new AbortController();
    void getAgentStatus(controller.signal).then((nextStatus) => {
      setStatus(nextStatus);
      setModel((current) => nextStatus.allowedModels.includes(current) ? current : nextStatus.defaultModel);
      setEffort(nextStatus.defaultEffort);
      setStatusChecked(true);
    });
    return () => controller.abort();
  }, []);

  const ask = async (rawQuestion: string) => {
    const question = rawQuestion.trim();
    if (!question || loading) return;
    const history = messages.filter((message) => message.role === "user" && message.content).map((message) => message.content!);
    const userId = Math.max(0, ...messages.map((message) => message.id)) + 1;
    setMessages((current) => [...current, { id: userId, role: "user", content: question }]);
    setInput("");
    setLoading(true);
    let response: AgentResponse;
    try {
      if (engine === "openai") {
        if (!status.configured) throw new Error("OPENAI_NOT_CONFIGURED");
        response = await askEnhancedAgent(question, history, model, effort);
      } else {
        response = answerEnergyQuestion(question, history);
      }
    } catch (error) {
      response = answerEnergyQuestion(question, history);
      response.engine = "fallback";
      response.provider = "Local deterministic engine";
      response.modelMode = "LOCAL FALLBACK · 9 AUDITABLE TOOLS";
      response.fallbackReason = error instanceof Error && error.message === "OPENAI_NOT_CONFIGURED"
        ? "The server does not have an OpenAI API key, so the auditable local mode was used automatically."
        : "OpenAI enhancement is temporarily unavailable, so the auditable local mode was used automatically.";
    } finally {
      setLoading(false);
    }
    setMessages((current) => [...current, { id: userId + 1, role: "assistant", response }]);
  };

  return <>
    <PageHeader number="07" title="Hybrid Energy Analysis Agent" description="Deterministic local tools produce project numbers; optional OpenAI orchestration improves understanding, planning and expression, with automatic local fallback." code="HYBRID AGENT · 9 AUDITABLE TOOLS" />
    <section className="panel agent-settings" aria-label="Agent engine settings">
      <div className="engine-switch" role="group" aria-label="Agent engine">
        <button className={engine === "local" ? "active" : ""} onClick={() => setEngine("local")}><b>LOCAL</b><span>Auditable offline mode</span></button>
        <button className={engine === "openai" ? "active" : ""} onClick={() => setEngine("openai")}><b>OPENAI</b><span>Enhanced orchestration</span></button>
      </div>
      <label><span>MODEL</span><select value={model} onChange={(event) => setModel(event.target.value)} disabled={engine === "local"}>{status.allowedModels.map((item) => <option key={item}>{item}</option>)}</select></label>
      <label><span>REASONING</span><select value={effort} onChange={(event) => setEffort(event.target.value)} disabled={engine === "local"}>{["low", "medium", "high"].map((item) => <option key={item}>{item}</option>)}</select></label>
      <div className="server-key-status"><span>SERVER KEY</span><b className={status.configured ? "ready" : "missing"}>{status.configured ? "CONFIGURED" : "NOT CONFIGURED"}</b><button onClick={() => void refreshStatus()}>Refresh</button></div>
      <p>The API key is stored only in the deployment server environment and is never exposed to the browser. Customers can replace the key and allowed-model list in their own deployment. Only the question, the six most recent user questions and tool summaries are sent.</p>
    </section>
    <div className="agent-status-band">
      <div><i/><span><b>AGENT ONLINE</b>{engine === "openai" && status.configured ? "OpenAI orchestration + 9 deterministic tools" : "local planner + 9 deterministic tools"}</span></div>
      <p>{engine === "openai" ? `${model} · ${status.configured ? "server key ready" : "local fallback ready"}` : "Fully offline · no external API"}</p>
    </div>
    {engine === "openai" && statusChecked && !status.configured ? <div className="agent-fallback-banner"><b>Enhanced interface is ready</b><span>This deployment has no server API key, so requests automatically use the local Agent. No front-end changes are required after the environment variable is configured.</span></div> : null}
    <div className="agent-layout">
      <section className="panel agent-console">
        <div className="agent-console-head">
          <div><span>CONVERSATION</span><h3>Irene Energy Copilot</h3></div>
          <button onClick={() => setMessages([welcomeMessage])}>Clear conversation</button>
        </div>
        <div className="agent-messages" aria-live="polite">
          {messages.map((message) => <article className={`agent-message ${message.role}`} key={message.id}>
            <div className="agent-avatar">{message.role === "assistant" ? "IR" : "YOU"}</div>
            <div className="agent-bubble">
              {message.response ? <>
                <span className="answer-label">ANALYSIS RESULT</span>
                <h4>{message.response.title}</h4>
                <p className="agent-answer-copy">{message.response.answer}</p>
                {message.response.fallbackReason ? <p className="inline-fallback">{message.response.fallbackReason}</p> : null}
                <div className="inline-trace">
                  <span>TOOL · {message.response.tool}</span>
                  <span>INTENTS · {message.response.intents.join(" + ") || message.response.intent}</span>
                  {message.response.engine === "openai" ? <span>ENGINE · OPENAI + IRENE TOOLS</span> : <span>INTENT MATCH · {(message.response.routeConfidence * 100).toFixed(0)}%</span>}
                  <span>EVIDENCE · {message.response.evidence}</span>
                  <span>READINESS · {message.response.decisionReadiness}</span>
                </div>
              </> : <p>{message.content}</p>}
            </div>
          </article>)}
        </div>
        {latest?.followUps.length ? <div className="context-prompts">
          <span>CONTEXT-AWARE FOLLOW-UPS</span>
          <div>{latest.followUps.map((prompt) => <button key={prompt} onClick={() => ask(prompt)}>{prompt}<i>↗</i></button>)}</div>
        </div> : null}
        <div className="quick-prompts">
          <span>REASONING CHALLENGES</span>
          <div>{quickPrompts.map((prompt) => <button key={prompt} onClick={() => ask(prompt)}>{prompt}</button>)}</div>
        </div>
        {loading ? <div className="agent-thinking"><i/><span>Planning and running Irene project tools…</span></div> : null}
        <form className="agent-input" onSubmit={(event) => { event.preventDefault(); void ask(input); }}>
          <label htmlFor="agent-question">Ask the Irene Energy Agent</label>
          <div><input id="agent-question" value={input} onChange={(event) => setInput(event.target.value)} placeholder="For example: Which missing data should be collected first, and what substitutes are available?" autoComplete="off" disabled={loading}/><button type="submit" disabled={!input.trim() || loading}>Send <span>↗</span></button></div>
        </form>
      </section>
      <aside className="agent-inspector">
        <section className="panel agent-core">
          <div className="agent-orbit"><i/><b>IR</b><span/><em/></div>
          <span>HYBRID ANALYSIS CORE</span><h3>Model-guided, tool-grounded planner</h3>
          <dl><div><dt>Project tools</dt><dd>9 deterministic</dd></div><div><dt>Context</dt><dd>Last 6 questions</dd></div><div><dt>Scenario engine</dt><dd className="online">ACTIVE</dd></div><div><dt>External API</dt><dd>{engine === "openai" && status.configured ? "SERVER-SIDE" : "OFF / FALLBACK"}</dd></div></dl>
        </section>
        <section className="panel trace-panel">
          <div className="trace-head"><span>LAST TOOL TRACE</span><i className={latest ? "active" : ""}/></div>
          {latest ? <>
            <code>{latest.tool}</code>
            <div className="trace-field"><span>Routed intents</span><b>{latest.intents.join(" → ") || latest.intent}</b></div>
            {latest.engine === "openai" ? <><div className="trace-field"><span>Orchestration engine</span><b>{latest.provider} · {latest.toolCallCount} tool call(s)</b></div><div className="trace-field"><span>Token usage</span><b>{latest.usage?.inputTokens ?? 0} in · {latest.usage?.outputTokens ?? 0} out</b></div></> : <div className="trace-field"><span>Intent match score</span><b>{(latest.routeConfidence * 100).toFixed(0)}% · heuristic, not probability</b></div>}
            <div className="trace-field"><span>Matched concepts</span><b>{latest.matchedConcepts.join(" · ") || "text-similarity features"}</b></div>
            <div className="trace-field"><span>Evidence boundary</span><b>{latest.evidence}</b></div>
            <div className="trace-field"><span>Decision readiness</span><b>{latest.decisionReadiness}</b></div>
            <div className="trace-field"><span>Interpretation boundary</span><p>{latest.confidence}</p></div>
            {latest.warnings.length ? <div className="trace-field"><span>Input warnings</span>{latest.warnings.map((item) => <p key={item}>{item}</p>)}</div> : null}
            <div className="trace-plan"><span>EXECUTION PLAN</span><ol>{latest.planSteps.map((step) => <li key={step}>{step}</li>)}</ol></div>
            {latest.calculations.length ? <div className="trace-calculations"><span>SCENARIO CALCULATIONS</span>{latest.calculations.map((item) => <p key={item}>{item}</p>)}</div> : null}
            <div className="trace-sources"><span>SOURCES</span>{latest.sources.map((source) => <p key={source}><i/>{source}</p>)}</div>
            <div className="trace-next"><span>NEXT BEST ACTIONS</span><ol>{latest.nextSteps.map((step) => <li key={step}>{step}</li>)}</ol></div>
          </> : <p className="trace-empty">After you send a question, this panel will show the routed tools, evidence classes, source files and next actions.</p>}
        </section>
      </aside>
    </div>
    <Notice tone="warning" title="Hybrid Agent safety boundary">Local mode is fully offline. Enhanced mode lets OpenAI select and combine project tools, while deterministic tools still produce every number. Neither mode connects to or controls the BMS or makes procurement commitments. Facilities personnel must review procurement and equipment actions.</Notice>
  </>;
}

type UploadState = {
  file: File;
  manifest?: ClientManifest;
  error?: string;
  confirmed: boolean;
  consent: boolean;
  recognising: boolean;
  recognition?: CloudRecognition;
};

function ClientOnboarding() {
  const [uploads, setUploads] = useState<UploadState[]>([]);
  const [dragging, setDragging] = useState(false);
  const [projectProfile, setProjectProfile] = useState({
    projectName: "Client energy review", clientReference: "", siteName: "", countryOrRegion: "", currency: "MYR",
    tariffPerKwh: "", gridEmissionFactorKgCo2eKwh: "", grossFloorAreaM2: "",
  });
  const manifests = uploads.flatMap((item) => item.manifest ? [item.manifest] : []);
  const confirmedManifests = uploads.flatMap((item) => item.confirmed && item.manifest ? [item.manifest] : []);
  const readiness = assessClientReadiness(manifests);
  const numericOrNull = (value: string) => value.trim() && Number(value) > 0 ? Number(value) : null;
  const analysisProfile: Partial<ClientProjectProfile> = {
    ...projectProfile,
    tariffPerKwh: numericOrNull(projectProfile.tariffPerKwh),
    gridEmissionFactorKgCo2eKwh: numericOrNull(projectProfile.gridEmissionFactorKgCo2eKwh),
    grossFloorAreaM2: numericOrNull(projectProfile.grossFloorAreaM2),
  };
  const projectAnalysis = assessClientProject(confirmedManifests, analysisProfile);

  async function addFiles(source: FileList | File[]) {
    const incoming = Array.from(source).map((file) => ({ file, confirmed: false, consent: false, recognising: false } as UploadState));
    setUploads((current) => [...current, ...incoming]);
    for (const item of incoming) {
      try {
        const manifest = await parseClientFile(item.file);
        setUploads((current) => current.map((candidate) => candidate === item ? { ...candidate, manifest } : candidate));
      } catch (error) {
        setUploads((current) => current.map((candidate) => candidate === item ? { ...candidate, error: error instanceof Error ? error.message : "The file could not be processed." } : candidate));
      }
    }
  }

  function update(index: number, value: Partial<UploadState>) {
    setUploads((current) => current.map((item, itemIndex) => itemIndex === index ? { ...item, ...value } : item));
  }

  function updateMapping(fileIndex: number, tableIndex: number, mappingIndex: number, target: string) {
    setUploads((current) => current.map((item, itemIndex) => {
      if (itemIndex !== fileIndex || !item.manifest) return item;
      const manifest = structuredClone(item.manifest);
      const mapping = manifest.tables[tableIndex].mappings[mappingIndex];
      mapping.target = target;
      mapping.unit = target === "unmapped" ? "" : fieldLibrary[target]?.unit ?? mapping.unit;
      mapping.review = true;
      return { ...item, manifest, confirmed: false };
    }));
  }

  function updateTable(fileIndex: number, tableIndex: number, includedForProject: boolean) {
    setUploads((current) => current.map((item, itemIndex) => {
      if (itemIndex !== fileIndex || !item.manifest) return item;
      const manifest = structuredClone(item.manifest);
      manifest.tables[tableIndex].includedForProject = includedForProject;
      return { ...item, manifest, confirmed: false };
    }));
  }

  async function recognise(index: number) {
    const item = uploads[index];
    if (!item?.manifest || !item.consent) return;
    update(index, { recognising: true, error: undefined });
    try {
      const recognition = await recogniseClientDocument(item.file);
      update(index, { recognition, recognising: false, confirmed: false });
    } catch (error) {
      update(index, { recognising: false, error: error instanceof Error ? error.message : "Recognition failed." });
    }
  }

  return <>
    <PageHeader number="08" title="Client Data Onboarding" description="Bring client-owned meters, workbooks, documents and building files into a controlled review flow before any value is admitted to the energy model." code="SESSION-ONLY · HUMAN-CONFIRMED" />
    <Notice tone="success" title="Local processing is the default">CSV, Excel, text-bearing PDF and Word files, DXF and IFC are inspected in this browser session. Raw uploads are not stored by Irene, committed to GitHub or admitted to the model automatically.</Notice>
    <div className="onboarding-phases">
      <article><b>01</b><span>PHASE 1 · DATA</span><h3>Meter and workbook intake</h3><p>CSV and Excel mapping, unit review, quality checks and readiness scoring.</p></article>
      <article><b>02</b><span>PHASE 2 · DOCUMENTS</span><h3>Bills and schedules</h3><p>Local PDF and Word text extraction; scans use explicit optional recognition.</p></article>
      <article><b>03</b><span>PHASE 3 · BIM / CAD</span><h3>Building structure</h3><p>IFC entities and DXF layers, blocks and labels; DWG passes through a conversion gate.</p></article>
      <article><b>✓</b><span>CONTROL GATE</span><h3>Human confirmation</h3><p>Mappings, units, quality findings and extracted facts require client review.</p></article>
    </div>
    <section className="panel client-project-panel">
      <SectionTitle kicker="CLIENT PROJECT" title="Project assumptions and reporting boundary" detail="No jurisdictional default is inserted automatically" />
      <div className="client-project-form">
        <label><span>Project name</span><input value={projectProfile.projectName} onChange={(event) => setProjectProfile((current) => ({ ...current, projectName: event.target.value }))}/></label>
        <label><span>Client reference</span><input placeholder="Optional internal reference" value={projectProfile.clientReference} onChange={(event) => setProjectProfile((current) => ({ ...current, clientReference: event.target.value }))}/></label>
        <label><span>Site name</span><input placeholder="Client site or portfolio" value={projectProfile.siteName} onChange={(event) => setProjectProfile((current) => ({ ...current, siteName: event.target.value }))}/></label>
        <label><span>Country or region</span><input placeholder="Reporting jurisdiction" value={projectProfile.countryOrRegion} onChange={(event) => setProjectProfile((current) => ({ ...current, countryOrRegion: event.target.value }))}/></label>
        <label><span>Currency</span><input maxLength={16} value={projectProfile.currency} onChange={(event) => setProjectProfile((current) => ({ ...current, currency: event.target.value }))}/></label>
        <label><span>Tariff per kWh</span><input type="number" min="0" step="0.001" placeholder="Not supplied" value={projectProfile.tariffPerKwh} onChange={(event) => setProjectProfile((current) => ({ ...current, tariffPerKwh: event.target.value }))}/></label>
        <label><span>Grid factor · kgCO₂e/kWh</span><input type="number" min="0" step="0.001" placeholder="Not supplied" value={projectProfile.gridEmissionFactorKgCo2eKwh} onChange={(event) => setProjectProfile((current) => ({ ...current, gridEmissionFactorKgCo2eKwh: event.target.value }))}/></label>
        <label><span>Gross floor area · m²</span><input type="number" min="0" step="1" placeholder="Not supplied" value={projectProfile.grossFloorAreaM2} onChange={(event) => setProjectProfile((current) => ({ ...current, grossFloorAreaM2: event.target.value }))}/></label>
      </div>
      <p className="client-input-note">Tariff, grid factor and floor area remain explicit client inputs unless the same field is present in a confirmed source file. Every result retains its evidence basis.</p>
    </section>
    <label
      className={`upload-zone ${dragging ? "dragging" : ""}`}
      onDragOver={(event) => { event.preventDefault(); setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={(event) => { event.preventDefault(); setDragging(false); void addFiles(event.dataTransfer.files); }}
    >
      <input type="file" multiple accept=".csv,.xlsx,.xlsm,.pdf,.docx,.png,.jpg,.jpeg,.tif,.tiff,.dxf,.ifc,.dwg" onChange={(event) => { if (event.target.files) void addFiles(event.target.files); event.target.value = ""; }} />
      <i>↥</i><b>Drop client files here or browse</b><span>CSV · Excel · PDF · Word · images · DXF · IFC · DWG · maximum 25 MB per file</span>
    </label>

    {manifests.length ? <>
      <div className="metric-grid onboarding-metrics">
        <MetricCard label="Accepted files" value={String(manifests.length)} unit="session" note="Held in browser memory" tone="green" />
        <MetricCard label="Mapped tables" value={String(manifests.reduce((sum, item) => sum + item.tables.length, 0))} unit="review" note="Every field remains editable" />
        <MetricCard label="Readiness" value={String(readiness.score)} unit="/ 100" note={readiness.path} tone="blue" />
        <MetricCard label="Approved files" value={String(uploads.filter((item) => item.confirmed).length)} unit="gate" note="Human-confirmed only" tone="amber" />
      </div>
      <section className="panel readiness-panel">
        <SectionTitle kicker="MODEL ADMISSION" title="Client analysis readiness" detail={readiness.path} />
        <div className="readiness-grid">{readiness.capabilities.map((item) => <article className={item.ready ? "ready" : "pending"} key={item.name}><i>{item.ready ? "READY" : "NEEDS DATA"}</i><b>{item.name}</b><p>{item.needs}</p></article>)}</div>
      </section>
    </> : null}

    <div className="upload-results">
      {uploads.map((item, fileIndex) => <section className="panel upload-card" key={`${item.file.name}-${item.file.lastModified}-${fileIndex}`}>
        <header><div><span>{item.manifest?.phase ?? "VALIDATING"}</span><h3>{item.manifest?.filename ?? item.file.name}</h3><p>{item.manifest ? `${item.manifest.kind} · ${(item.manifest.size / 1024).toFixed(1)} KB · ${item.manifest.status.replaceAll("_", " ")}` : "Inspecting file locally…"}</p></div><button aria-label={`Remove ${item.file.name}`} onClick={() => setUploads((current) => current.filter((_, index) => index !== fileIndex))}>×</button></header>
        {item.error ? <div className="upload-error">{item.error}</div> : null}
        {!item.manifest && !item.error ? <div className="upload-loading"><i/> Reading the selected file locally…</div> : null}
        {item.manifest ? <>
          <ul className="upload-notes">{item.manifest.notes.map((note) => <li key={note}>{note}</li>)}</ul>
          {item.manifest.tables.map((source, tableIndex) => <div className="table-review" key={source.name}>
            <div className="table-review-head"><div><span>DATA TABLE</span><h4>{source.name}</h4></div><dl><div><dt>Rows</dt><dd>{source.rowCount.toLocaleString()}</dd></div><div><dt>Quality</dt><dd>{source.quality.score}/100</dd></div><div><dt>Granularity</dt><dd>{source.quality.granularity}</dd></div></dl></div>
            <label className="table-admission"><input type="checkbox" checked={source.includedForProject} onChange={(event) => updateTable(fileIndex, tableIndex, event.target.checked)}/><span><b>Include in consolidated analysis</b>Turn this off for cover sheets, lookup tabs or duplicate summaries.</span></label>
            <div className="table-wrap preview-table"><table><thead><tr>{source.columns.map((column) => <th key={column}>{column}</th>)}</tr></thead><tbody>{source.rows.slice(0, 8).map((row, rowIndex) => <tr key={rowIndex}>{row.map((value, cellIndex) => <td key={cellIndex}>{value instanceof Date ? value.toISOString() : String(value ?? "")}</td>)}</tr>)}</tbody></table></div>
            <div className="mapping-grid"><div className="mapping-head"><span>SOURCE FIELD</span><span>MODEL FIELD</span><span>UNIT</span><span>MATCH</span></div>{source.mappings.map((mapping, mappingIndex) => <div className="mapping-row" key={mapping.source}><b>{mapping.source}</b><select value={mapping.target} onChange={(event) => updateMapping(fileIndex, tableIndex, mappingIndex, event.target.value)}><option value="unmapped">Not mapped</option>{Object.entries(fieldLibrary).map(([field, definition]) => <option value={field} key={field}>{definition.label}</option>)}</select><span>{mapping.unit || "—"}</span><em className={mapping.review ? "review" : "good"}>{Math.round(mapping.confidence * 100)}%</em></div>)}</div>
            {source.quality.issues.length ? <div className="quality-list">{source.quality.issues.map((issue, index) => <p className={issue.severity} key={`${issue.check}-${index}`}><b>{issue.check}</b>{issue.detail}</p>)}</div> : <p className="quality-pass">No row-level quality exception was found in the parsed table.</p>}
          </div>)}
          {item.manifest.facts.length ? <div className="facts-review"><h4>Locally extracted facts</h4><div className="table-wrap"><table><thead><tr><th>Field</th><th>Value</th><th>Unit</th><th>Source context</th></tr></thead><tbody>{item.manifest.facts.map((fact, index) => <tr key={`${fact.field}-${index}`}><td>{fact.field}</td><td>{fact.value}</td><td>{fact.unit}</td><td>{fact.source}</td></tr>)}</tbody></table></div></div> : null}
          {CLOUD_EXTENSIONS.has(item.manifest.extension) ? <div className="cloud-review"><label><input type="checkbox" checked={item.consent} onChange={(event) => update(fileIndex, { consent: event.target.checked })}/><span><b>Optional document recognition</b>I have permission to send this selected PDF or image to Irene&apos;s configured recognition service for this request.</span></label><p>Use this for scans or ambiguous pages only. The server request uses <code>store:false</code>. Files over 3 MB remain local and should be reviewed in Streamlit.</p><button disabled={!item.consent || item.recognising || item.file.size > 3 * 1024 * 1024} onClick={() => void recognise(fileIndex)}>{item.recognising ? "Reading document…" : "Run optional recognition"}</button></div> : null}
          {item.recognition ? <div className="recognition-result"><span>DOCUMENT RECOGNITION · {item.recognition.retention}</span><h4>{item.recognition.summary}</h4>{item.recognition.facts.length ? <div className="table-wrap"><table><thead><tr><th>Field</th><th>Value</th><th>Unit</th><th>Source</th><th>Confidence</th></tr></thead><tbody>{item.recognition.facts.map((fact, index) => <tr key={`${fact.field}-${index}`}><td>{fact.field}</td><td>{fact.value ?? "—"}</td><td>{fact.unit}</td><td>{fact.sourceLocation}</td><td>{Math.round(fact.confidence * 100)}%</td></tr>)}</tbody></table></div> : null}{item.recognition.reviewItems.map((review) => <p key={review}>Review: {review}</p>)}</div> : null}
          {Object.keys(item.manifest.details).length ? <details className="technical-details"><summary>Technical extraction details</summary><pre>{JSON.stringify(item.manifest.details, null, 2)}</pre></details> : null}
          <div className="admission-gate"><label><input type="checkbox" checked={item.confirmed} onChange={(event) => update(fileIndex, { confirmed: event.target.checked })}/><span><b>I reviewed this file.</b>Field mappings, source units, quality findings and extracted facts are correct for model use.</span></label><button onClick={() => downloadMapping(item.manifest!, item.confirmed)}>Download mapping record</button><strong className={item.confirmed ? "passed" : "blocked"}>{item.confirmed ? "CONTROL GATE PASSED" : "OUTSIDE MODEL PIPELINE"}</strong></div>
        </> : null}
      </section>)}
    </div>
    {confirmedManifests.length ? <section className="panel client-results-panel">
      <SectionTitle kicker="CONFIRMED RESULTS" title="Client reporting-period baseline" detail={`${projectAnalysis.controlGate.approvedFiles} approved file(s) · ${projectAnalysis.sourceTables.length} included table(s)`} />
      <div className="metric-grid onboarding-metrics">
        <MetricCard label="Electricity" value={projectAnalysis.results.electricityKwh !== null ? format(projectAnalysis.results.electricityKwh / 1_000, 2) : "—"} unit="MWh" note="Confirmed reporting period" tone="green" />
        <MetricCard label="Energy cost" value={projectAnalysis.results.reportingCost !== null ? format(projectAnalysis.results.reportingCost, 2) : "—"} unit={projectAnalysis.project.currency} note={projectAnalysis.results.costBasis} />
        <MetricCard label="Operational emissions" value={projectAnalysis.results.emissionsTco2e !== null ? format(projectAnalysis.results.emissionsTco2e, 3) : "—"} unit="tCO₂e" note="Client-supplied grid factor" tone="blue" />
        <MetricCard label="Reporting-period EUI" value={projectAnalysis.results.reportingPeriodEuiKwhM2 !== null ? format(projectAnalysis.results.reportingPeriodEuiKwhM2, 2) : "—"} unit="kWh/m²" note="Not silently annualised" tone="amber" />
      </div>
      <div className="client-result-register">
        <div><span>Coverage</span><b>{projectAnalysis.coverage.start?.slice(0, 10) ?? "Undated"} → {projectAnalysis.coverage.end?.slice(0, 10) ?? "Undated"}</b></div>
        <div><span>Data quality</span><b>{projectAnalysis.results.qualityScore !== null ? `${projectAnalysis.results.qualityScore}/100` : "—"}</b></div>
        <div><span>Tariff basis</span><b>{projectAnalysis.results.tariffSource}</b></div>
        <div><span>Area basis</span><b>{projectAnalysis.results.areaSource}</b></div>
      </div>
      {projectAnalysis.monthly.length ? <div className="table-wrap client-monthly-table"><table><thead><tr><th>Period</th><th>Electricity</th><th>Cost</th><th>Emissions</th></tr></thead><tbody>{projectAnalysis.monthly.map((row) => <tr key={row.period}><td>{row.period}</td><td>{row.electricityKwh !== undefined ? `${format(row.electricityKwh, 2)} kWh` : "—"}</td><td>{row.cost !== undefined ? format(row.cost, 2) : row.calculatedCost !== undefined ? format(row.calculatedCost, 2) : "—"}</td><td>{row.emissionsTco2e !== undefined ? `${format(row.emissionsTco2e, 3)} tCO₂e` : "—"}</td></tr>)}</tbody></table></div> : null}
      <div className="client-warning-list">{projectAnalysis.warnings.map((warning) => <p key={warning}>{warning}</p>)}</div>
      <div className="client-deliverable"><div><b>Audit-ready client deliverable</b><span>Project summary, monthly baseline, mapping and quality registers, source fingerprints and audit log. Raw uploads are excluded.</span></div><button onClick={() => downloadClientDeliverable(confirmedManifests, projectAnalysis)}>Download .zip</button></div>
      <p className="client-boundary">{projectAnalysis.evidenceBoundary}</p>
    </section> : manifests.length ? <Notice tone="warning" title="Project analysis locked">Confirm at least one reviewed file to calculate client results and create the audit-ready deliverable pack.</Notice> : null}
    <Notice tone="warning" title="Scope boundary">Native DWG is never treated as parsed data in the browser. Export to DXF or use the workstation converter adapter. IFC review extracts structure and entity counts; procurement geometry still requires authoring-tool validation.</Notice>
  </>;
}

export default function Home() {
  const [active, setActive] = useState<ModuleId>("overview");
  const [navOpen, setNavOpen] = useState(false);
  const [methodOpen, setMethodOpen] = useState(false);
  const activeModule = modules.find((item) => item.id === active) ?? modules[0];

  const goTo = (id: ModuleId) => {
    setActive(id);
    setNavOpen(false);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  return (
    <div className="app-shell">
      <button className="mobile-menu" aria-label="Open navigation" aria-expanded={navOpen} onClick={() => setNavOpen((value) => !value)}><i/><i/><i/></button>
      {navOpen && <button className="nav-backdrop" aria-label="Close navigation" onClick={() => setNavOpen(false)}/>}
      <aside className={navOpen ? "open" : ""}>
        <div className="brand"><b>IR</b><div><h1>NEXUS ENERGY OS</h1><p>Evidence-led digital twin<br/>T1 — AI for Clean Energy<br/>Team EnerGen AI · Project Irene</p></div></div>
        <div className="side-rule"/>
        <span className="nav-label">COMMAND MODULES</span>
        <nav aria-label="Command modules">
          {modules.map((item) => <button key={item.id} className={active === item.id ? "active" : ""} onClick={() => goTo(item.id)}><span>{item.number}</span>{item.label}</button>)}
        </nav>
        <div className="facts"><span className="nav-label">REFERENCE FACTS</span><dl><div><dt>Building</dt><dd>Ningbo Reference</dd></div><div><dt>Gross area</dt><dd>6,231.26 m²</dd></div><div><dt>Ningbo tariff</dt><dd>kWh × CNY 0.538</dd></div><div><dt>Opening</dt><dd>08:00—22:00</dd></div><div><dt>PV / storage</dt><dd>106.14 kWp / none</dd></div></dl></div>
        <div className="model-health"><span className="nav-label">MODEL HEALTH</span><p><i/> Integrity checks passed</p></div>
        <footer>IRENE · ENERGEN AI · MAIC 2026</footer>
      </aside>

      <main>
        <section className="hero">
          <div className="hero-grid"/>
          <div className="hero-kicker">MAIC NEXUS CHALLENGE 2026 · T1 — AI FOR CLEAN ENERGY</div>
          <h1>AI-assisted Digital Twin<br/><span>Energy Command Center</span></h1>
          <p>Using an anonymized Ningbo reference case, Irene connects approved aggregate evidence, synthetic public demo profiles, auditable hourly estimates and loss-aware optimisation into one traceable decision chain.</p>
          <div className="hero-meta"><span><i/>Reference case · Ningbo</span><span><i/>Malaysia local pilot · pending</span><span className="ok"><i/>Integrity checks pass</span><span><i/>Team EnerGen AI · Project Irene</span></div>
          <div className="hero-actions"><button onClick={() => window.print()}>Export Brief</button><button className="ghost" onClick={() => setMethodOpen(true)}>View Evidence Boundaries</button></div>
        </section>
        <div className="module-crumb"><span>{activeModule.eyebrow}</span><b>{activeModule.number} / 08</b></div>
        <div className="page-content" key={active}>
          {active === "overview" && <Overview/>}
          {active === "monthly" && <Monthly/>}
          {active === "hourly" && <Hourly/>}
          {active === "scenarios" && <Scenarios/>}
          {active === "storage" && <Storage/>}
          {active === "twin" && <Twin/>}
          {active === "agent" && <Agent/>}
          {active === "onboarding" && <ClientOnboarding/>}
        </div>
        <footer className="app-footer"><span>TEAM ENERGEN AI · PROJECT IRENE · T1 — AI FOR CLEAN ENERGY</span><span>Approved Aggregate → Synthetic → Derived → Assumed → Sandbox</span></footer>
      </main>

      {methodOpen && <div className="modal-layer" role="dialog" aria-modal="true" aria-labelledby="boundary-title"><button className="modal-backdrop-button" aria-label="Close evidence-boundary dialog" onClick={() => setMethodOpen(false)}/><section>
        <button className="modal-close" aria-label="Close" onClick={() => setMethodOpen(false)}>×</button>
        <span>EVIDENCE BOUNDARY</span><h2 id="boundary-title">Every conclusion retains its provenance</h2>
        <div className="boundary-list"><article><i className="measured"/><div><b>Approved aggregate</b><p>Selected monthly energy, PV and screening outputs cleared for public display.</p></div></article><article><i className="derived"/><div><b>Synthetic public demo</b><p>Generated meter, weather, load, PV and comfort rows constrained to approved aggregates.</p></div></article><article><i className="assumed"/><div><b>Assumed</b><p>Daily 08:00–22:00 opening, comfortable conditions and retrofit CAPEX.</p></div></article><article><i className="sandbox"/><div><b>Sandbox</b><p>Battery dispatch is a future strategy simulation; the reference case has no storage.</p></div></article></div>
        <button className="primary" onClick={() => setMethodOpen(false)}>Understood</button>
      </section></div>}
    </div>
  );
}
