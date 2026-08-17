import { getAgentStatus } from "../../../../worker/openai-agent";
import { jsonResponse, readAgentEnv } from "../server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export function GET() {
  return jsonResponse(getAgentStatus(readAgentEnv()));
}
