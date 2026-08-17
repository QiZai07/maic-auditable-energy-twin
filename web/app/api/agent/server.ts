import { createHash } from "node:crypto";
import type { AgentEnv } from "../../../worker/openai-agent";

const rateBuckets = new Map<string, { count: number; resetAt: number }>();

export function readAgentEnv(): AgentEnv {
  return {
    OPENAI_API_KEY: process.env.OPENAI_API_KEY,
    OPENAI_MODEL: process.env.OPENAI_MODEL,
    OPENAI_ALLOWED_MODELS: process.env.OPENAI_ALLOWED_MODELS,
    OPENAI_REASONING_EFFORT: process.env.OPENAI_REASONING_EFFORT,
    OPENAI_BASE_URL: process.env.OPENAI_BASE_URL,
  };
}

export function jsonResponse(value: unknown, status = 200) {
  return Response.json(value, {
    status,
    headers: { "cache-control": "no-store" },
  });
}

export function isSameOrigin(request: Request) {
  const origin = request.headers.get("origin");
  if (!origin) return true;

  const host = request.headers.get("x-forwarded-host") ?? request.headers.get("host");
  if (!host) return false;

  try {
    return new URL(origin).host === host;
  } catch {
    return false;
  }
}

export function withinRateLimit(request: Request) {
  const now = Date.now();
  const forwardedFor = request.headers.get("x-forwarded-for")?.split(",")[0]?.trim();
  const key = forwardedFor || "local";
  const current = rateBuckets.get(key);
  if (!current || current.resetAt <= now) {
    rateBuckets.set(key, { count: 1, resetAt: now + 60_000 });
    return true;
  }
  if (current.count >= 12) return false;
  current.count += 1;
  return true;
}

export function safetyIdentifier(request: Request) {
  const forwardedFor = request.headers.get("x-forwarded-for")?.split(",")[0]?.trim();
  const source = `${forwardedFor || "local"}|${request.headers.get("user-agent") ?? "browser"}`;
  return `db-web-${createHash("sha256").update(source).digest("hex").slice(0, 24)}`;
}
