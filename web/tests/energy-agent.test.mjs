import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { answerEnergyQuestion } from "../app/energy-agent.ts";
import { getAgentStatus, runOpenAIEnergyAgent } from "../worker/openai-agent.ts";

test("recalculates tariff scenarios with deterministic project tools", () => {
  const result = answerEnergyQuestion("If the electricity tariff rises by 20%, which measure has the fastest payback?");
  assert.equal(result.intent, "scenario_roi");
  assert.match(result.answer, /0\.646/);
  assert.match(result.answer, /1\.73 years/);
  assert.equal(result.calculations.length, 5);
});

test("combines installed PV and future-storage evidence without merging their status", () => {
  const result = answerEnergyQuestion("How do installed PV and future storage affect grid imports?");
  assert.equal(result.tool, "local_multi_tool_planner");
  assert.deepEqual(new Set(result.intents), new Set(["pv_status", "storage_sandbox"]));
  assert.match(result.answer, /currently has no battery storage/i);
});

test("uses recent context for a follow-up calculation", () => {
  const result = answerEnergyQuestion(
    "What if it falls by 10%?",
    ["If the electricity tariff rises by 20%, what is the combined package payback?"],
  );
  assert.match(result.answer, /0\.484/);
  assert.match(result.confidence, /previous-question context was retained/);
});

test("configuration status never returns the API key", () => {
  const status = getAgentStatus({ OPENAI_API_KEY: "test-only-secret" });
  assert.equal(status.configured, true);
  assert.equal(status.keyLocation, "server");
  assert.doesNotMatch(JSON.stringify(status), /test-only-secret/);
});

test("server orchestration grounds its answer in a project tool", async () => {
  const calls = [];
  const fetchStub = async (_input, init) => {
    const payload = JSON.parse(init.body);
    calls.push(payload);
    if (calls.length === 1) {
      return new Response(JSON.stringify({
        output: [{ type: "function_call", name: "query_energy_baseline", call_id: "call_1", arguments: "{}" }],
        usage: { input_tokens: 100, output_tokens: 12 },
      }), { status: 200, headers: { "content-type": "application/json" } });
    }
    return new Response(JSON.stringify({
      output: [{ type: "message", content: [{ type: "output_text", text: "The annual result is grounded in the baseline tool." }] }],
      usage: { input_tokens: 180, output_tokens: 24 },
    }), { status: 200, headers: { "content-type": "application/json" } });
  };

  const result = await runOpenAIEnergyAgent(
    { question: "How much electricity does the building use annually?", model: "gpt-5.6-terra", effort: "medium" },
    { OPENAI_API_KEY: "test-only-key" },
    fetchStub,
  );
  assert.equal(result.engine, "openai");
  assert.equal(result.tool, "query_energy_baseline");
  assert.equal(result.toolCallCount, 1);
  assert.equal(calls[0].store, false);
  assert.match(calls[1].input.at(-1).output, /345,676\.69/);
});

test("the public interface is English and contains no embedded secret", async () => {
  const [page, layout, statusRoute, onboarding, recognition] = await Promise.all([
    readFile(new URL("../app/page.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/layout.tsx", import.meta.url), "utf8"),
    readFile(new URL("../app/api/agent/status/route.ts", import.meta.url), "utf8"),
    readFile(new URL("../app/client-onboarding.ts", import.meta.url), "utf8"),
    readFile(new URL("../worker/document-recognition.ts", import.meta.url), "utf8"),
  ]);
  const source = `${page}\n${layout}\n${statusRoute}\n${onboarding}\n${recognition}`;
  assert.doesNotMatch(source, /[\u3400-\u9fff]/u);
  assert.doesNotMatch(source, /sk-(?:proj-)?[A-Za-z0-9_-]{10,}/);
  assert.match(layout, /<html lang="en">/);
  assert.match(page, /106\.14 kWp/);
});
