import {
  type AgentRequestBody,
  runOpenAIEnergyAgent,
} from "../../../worker/openai-agent";
import {
  isSameOrigin,
  jsonResponse,
  readAgentEnv,
  safetyIdentifier,
  withinRateLimit,
} from "./server";

export const runtime = "nodejs";
export const maxDuration = 60;

export async function POST(request: Request) {
  if (!isSameOrigin(request)) return jsonResponse({ error: "ORIGIN_NOT_ALLOWED" }, 403);
  if (!withinRateLimit(request)) return jsonResponse({ error: "RATE_LIMITED" }, 429);

  const agentEnv = readAgentEnv();
  if (!agentEnv.OPENAI_API_KEY?.trim()) {
    return jsonResponse({ error: "OPENAI_NOT_CONFIGURED", fallback: "local" }, 503);
  }

  const declaredSize = Number(request.headers.get("content-length") ?? 0);
  if (declaredSize > 32_768) return jsonResponse({ error: "REQUEST_TOO_LARGE" }, 413);

  try {
    const body = (await request.json()) as AgentRequestBody;
    if (typeof body.question !== "string" || !body.question.trim() || body.question.length > 1200) {
      return jsonResponse({ error: "INVALID_QUESTION" }, 400);
    }
    const response = await runOpenAIEnergyAgent(
      { ...body, safetyIdentifier: safetyIdentifier(request) },
      agentEnv,
    );
    return jsonResponse(response);
  } catch (error) {
    const code =
      error instanceof Error && error.message.startsWith("OPENAI_HTTP_")
        ? error.message
        : "OPENAI_TEMPORARILY_UNAVAILABLE";
    return jsonResponse({ error: code, fallback: "local" }, 502);
  }
}
