import type { AgentResponse } from "./energy-agent";

export type AgentStatus = {
  configured: boolean;
  provider: "OpenAI";
  defaultModel: string;
  allowedModels: string[];
  defaultEffort: string;
  keyLocation: "server" | "missing";
  fallback: "local";
};

const fallbackStatus: AgentStatus = {
  configured: false,
  provider: "OpenAI",
  defaultModel: "gpt-5.6-terra",
  allowedModels: ["gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.6-sol"],
  defaultEffort: "medium",
  keyLocation: "missing",
  fallback: "local",
};

export async function getAgentStatus(signal?: AbortSignal): Promise<AgentStatus> {
  try {
    const response = await fetch("/api/agent/status", { signal, cache: "no-store" });
    if (!response.ok) return fallbackStatus;
    const value = await response.json() as Partial<AgentStatus>;
    return { ...fallbackStatus, ...value };
  } catch {
    return fallbackStatus;
  }
}

export async function askEnhancedAgent(
  question: string,
  history: string[],
  model: string,
  effort: string,
): Promise<AgentResponse> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 40_000);
  try {
    const response = await fetch("/api/agent", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ question, history: history.slice(-6), model, effort }),
      signal: controller.signal,
    });
    if (!response.ok) {
      const problem = await response.json().catch(() => ({})) as { error?: string };
      throw new Error(problem.error ?? `AGENT_HTTP_${response.status}`);
    }
    return await response.json() as AgentResponse;
  } finally {
    window.clearTimeout(timeout);
  }
}
