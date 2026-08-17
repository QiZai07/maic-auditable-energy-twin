import {
  type AgentResponse,
  type ToolResult,
  composeEnhancedResponse,
  executeEnergyTool,
  openAIToolDefinitions,
} from "../app/energy-agent.ts";

export interface AgentEnv {
  OPENAI_API_KEY?: string;
  OPENAI_MODEL?: string;
  OPENAI_ALLOWED_MODELS?: string;
  OPENAI_REASONING_EFFORT?: string;
  OPENAI_BASE_URL?: string;
}

export type AgentRequestBody = {
  question: string;
  history?: string[];
  model?: string;
  effort?: string;
  safetyIdentifier?: string;
};

export type AgentStatus = {
  configured: boolean;
  provider: "OpenAI";
  defaultModel: string;
  allowedModels: string[];
  defaultEffort: string;
  keyLocation: "server" | "missing";
  fallback: "local";
};

const DEFAULT_MODELS = ["gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.6-sol"];
const ALLOWED_EFFORTS = ["low", "medium", "high"];
const MAX_TOOL_ROUNDS = 3;
const MAX_TOOL_CALLS = 6;

const instructions = `You are the energy-decision orchestrator for the anonymized Ningbo reference case in Project Irene.
Call at least one provided Irene project tool before answering. You may combine tools, but do not call the same tool more than once.
The model is responsible only for understanding, planning and expression. Every project number must come directly from tool output; never calculate or invent project values independently.
Clearly distinguish APPROVED AGGREGATE, SYNTHETIC PUBLIC DEMO, DERIVED, ASSUMED and SANDBOX evidence. The reference case currently has no battery storage. Its approved aggregate PV capacity is 106.14 kWp.
The Ningbo reference-case electricity-billing rule is kWh × CNY 0.538 only. Never claim to connect to, control or modify the BMS, and never make procurement commitments. Treat the Malaysia carbon factor as a parameterized scenario assumption, not a field result.
Answer in clear competition-ready English. Lead with the direct answer, then state the evidence boundary and recommended next action.`;

function allowedModels(env: AgentEnv) {
  const configured = (env.OPENAI_ALLOWED_MODELS ?? "").split(",").map((item) => item.trim()).filter(Boolean);
  return configured.length ? configured : DEFAULT_MODELS;
}

function selectedModel(env: AgentEnv, requested?: string) {
  const models = allowedModels(env);
  const defaultModel = models.includes(env.OPENAI_MODEL ?? "") ? env.OPENAI_MODEL! : (models.includes("gpt-5.6-terra") ? "gpt-5.6-terra" : models[0]);
  return requested && models.includes(requested) ? requested : defaultModel;
}

function selectedEffort(env: AgentEnv, requested?: string) {
  if (requested && ALLOWED_EFFORTS.includes(requested)) return requested;
  return ALLOWED_EFFORTS.includes(env.OPENAI_REASONING_EFFORT ?? "") ? env.OPENAI_REASONING_EFFORT! : "medium";
}

export function getAgentStatus(env: AgentEnv): AgentStatus {
  return {
    configured: Boolean(env.OPENAI_API_KEY?.trim()),
    provider: "OpenAI",
    defaultModel: selectedModel(env),
    allowedModels: allowedModels(env),
    defaultEffort: selectedEffort(env),
    keyLocation: env.OPENAI_API_KEY?.trim() ? "server" : "missing",
    fallback: "local",
  };
}

function outputItems(response: Record<string, unknown>) {
  return Array.isArray(response.output) ? response.output.filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object") : [];
}

function toolCalls(response: Record<string, unknown>) {
  return outputItems(response).filter((item) => item.type === "function_call");
}

function outputText(response: Record<string, unknown>) {
  if (typeof response.output_text === "string" && response.output_text.trim()) return response.output_text.trim();
  const parts: string[] = [];
  for (const item of outputItems(response)) {
    if (!Array.isArray(item.content)) continue;
    for (const block of item.content) {
      if (block && typeof block === "object" && (block as Record<string, unknown>).type === "output_text" && typeof (block as Record<string, unknown>).text === "string") {
        parts.push((block as Record<string, unknown>).text as string);
      }
    }
  }
  return parts.join("\n").trim();
}

function usage(response: Record<string, unknown>) {
  const value = response.usage && typeof response.usage === "object" ? response.usage as Record<string, unknown> : {};
  return { inputTokens: Number(value.input_tokens ?? 0), outputTokens: Number(value.output_tokens ?? 0) };
}

function toolOutput(result: ToolResult) {
  return JSON.stringify({
    intent: result.intent,
    tool: result.tool,
    title: result.title,
    answer: result.body,
    evidence: result.evidence,
    sources: result.sources,
    next_steps: result.actions,
    calculations: result.calculations ?? [],
  });
}

async function requestResponse(
  env: AgentEnv,
  payload: Record<string, unknown>,
  fetchImpl: typeof fetch,
) {
  const endpoint = `${(env.OPENAI_BASE_URL ?? "https://api.openai.com/v1").replace(/\/$/, "")}/responses`;
  const response = await fetchImpl(endpoint, {
    method: "POST",
    headers: { authorization: `Bearer ${env.OPENAI_API_KEY}`, "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error(`OPENAI_HTTP_${response.status}`);
  return await response.json() as Record<string, unknown>;
}

export async function runOpenAIEnergyAgent(
  body: AgentRequestBody,
  env: AgentEnv,
  fetchImpl: typeof fetch = fetch,
): Promise<AgentResponse> {
  if (!env.OPENAI_API_KEY?.trim()) throw new Error("OPENAI_NOT_CONFIGURED");
  const question = body.question.trim().slice(0, 1200);
  if (!question) throw new Error("EMPTY_QUESTION");
  const history = (body.history ?? []).filter((item): item is string => typeof item === "string" && Boolean(item.trim())).slice(-6).map((item) => item.trim().slice(0, 1200));
  const model = selectedModel(env, body.model);
  const effort = selectedEffort(env, body.effort);
  const inputItems: Record<string, unknown>[] = [
    ...history.map((content) => ({ role: "user", content })),
    { role: "user", content: question },
  ];
  const results: ToolResult[] = [];
  const seenTools = new Set<string>();
  let inputTokens = 0;
  let outputTokens = 0;

  for (let round = 0; round < MAX_TOOL_ROUNDS; round += 1) {
    const response = await requestResponse(env, {
      model,
      instructions,
      input: inputItems,
      tools: openAIToolDefinitions,
      tool_choice: round === 0 ? "required" : "auto",
      parallel_tool_calls: true,
      reasoning: { effort },
      text: { verbosity: "medium" },
      max_output_tokens: 1000,
      store: false,
      safety_identifier: (body.safetyIdentifier ?? "db-web-session").slice(0, 64),
    }, fetchImpl);
    const turnUsage = usage(response);
    inputTokens += turnUsage.inputTokens;
    outputTokens += turnUsage.outputTokens;
    const calls = toolCalls(response);
    if (!calls.length) {
      if (!results.length) throw new Error("OPENAI_NO_TOOL_CALL");
      return composeEnhancedResponse(results, outputText(response), model, { inputTokens, outputTokens });
    }

    inputItems.push(...outputItems(response));
    for (const call of calls) {
      const name = typeof call.name === "string" ? call.name : "";
      const callId = typeof call.call_id === "string" ? call.call_id : "";
      if (!name || !callId) throw new Error("OPENAI_INVALID_TOOL_CALL");
      let output: string;
      if (seenTools.has(name)) {
        output = JSON.stringify({ status: "skipped", reason: "tool already executed" });
      } else if (results.length >= MAX_TOOL_CALLS) {
        output = JSON.stringify({ status: "skipped", reason: "tool call limit reached" });
      } else {
        const result = executeEnergyTool(name, question, history);
        seenTools.add(name);
        results.push(result);
        output = toolOutput(result);
      }
      inputItems.push({ type: "function_call_output", call_id: callId, output });
    }
  }

  if (results.length) return composeEnhancedResponse(results, "", model, { inputTokens, outputTokens });
  throw new Error("OPENAI_ORCHESTRATION_FAILED");
}
