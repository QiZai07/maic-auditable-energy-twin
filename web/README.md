# Irene Web Application

**Team:** EnerGen AI
**Project:** Irene
**Track:** T1 — AI for Clean Energy

This directory contains the Next.js application deployed at **[irene-flax.vercel.app](https://irene-flax.vercel.app/)**.

Validated on a Ningbo reference case; designed for configurable deployment in Malaysia, pending local pilot validation.

## Local development

```bash
npm install
npm run dev
```

Open `http://localhost:3000`. The full dashboard and deterministic analysis engine work without an external API.

## Optional server-side model mode

Copy `.env.example` to `.env.local`, add a project API key locally, and keep that file out of Git:

```text
OPENAI_API_KEY=your_key_here
```

The key is read only by server routes. The browser can query whether enhanced analysis is configured, but no status response contains the key. Module 08 uses the same server credential for optional PDF/image recognition only after the user grants permission for that selected file. Recognition requests use `store: false`; local CSV, Excel, Word, DXF and IFC parsing does not call the provider.

Enhanced agent mode sends the question, the six most recent user questions and deterministic tool summaries rather than raw client files or unconfirmed rows. ChatGPT provides general-purpose language reasoning; Irene supplies approved project evidence, nine deterministic tools, evidence labels, approval gates, local fallback and the auditable delivery workflow. OpenAI API data is not used for training by default, although standard abuse-monitoring logs may be retained for up to 30 days. `store: false` is not the same as Zero Data Retention.

## Client data onboarding

Module 08 supports local CSV and Excel mapping, quality checks and readiness scoring; local PDF/Word fact review; explicit optional PDF/image recognition; local DXF and IFC structure review; and a clear DXF/converter gate for native DWG. After review, confirmed tables can be consolidated into a reporting-period energy, cost, emissions and EUI analysis. The downloadable ZIP contains project results, monthly baseline, mapping and quality registers, source fingerprints and an audit log. It excludes raw client rows and files. No uploaded client file is written into the public repository.

Irene can be introduced without replacing the client's BMS, EMS, metering, ERP or PV platforms. The working prototype starts with files and read-only exports, maps them to a confirmed data contract and keeps the original platform as the system of record. Production API, SQL-view, SFTP or site-gateway connectors are configured per client. The migration sequence is inventory → mapping → historical backfill → reconciliation → shadow run → client-approved cutover, with incremental synchronisation and rollback checkpoints. Prebuilt universal vendor connectors are not claimed.

## Verification

```bash
npm run lint
npm test
npm run build
```

## Vercel deployment

Import the repository in Vercel, set the Root Directory to `web`, and deploy. If enhanced mode is required, add `OPENAI_API_KEY` and the optional model settings from `.env.example` under Project Settings → Environment Variables, then redeploy.

The application falls back to its local deterministic engine when the provider is not configured or unavailable.

The first commercial entry is a file-based energy diagnosis and auditable report. The delivery path is file audit → temporary metering → calibration → savings verification → multi-site scale.
