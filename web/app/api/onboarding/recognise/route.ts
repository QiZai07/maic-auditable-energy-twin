import { runDocumentRecognition } from "../../../../worker/document-recognition";
import { isSameOrigin, jsonResponse, readAgentEnv, safetyIdentifier, withinRateLimit } from "../../agent/server";

export const runtime = "nodejs";
export const maxDuration = 60;

const MAX_BYTES = 3 * 1024 * 1024;
const allowedTypes = new Set(["application/pdf", "image/png", "image/jpeg"]);

function cleanName(value: string) {
  return value.split(/[\\/]/).at(-1)!.replace(/[^A-Za-z0-9._() -]/g, "_").slice(0, 160) || "upload";
}

function signatureMatches(mediaType: string, bytes: Uint8Array) {
  if (mediaType === "application/pdf") return new TextDecoder().decode(bytes.slice(0, 4)) === "%PDF";
  if (mediaType === "image/png") return bytes[0] === 0x89 && bytes[1] === 0x50 && bytes[2] === 0x4e && bytes[3] === 0x47;
  if (mediaType === "image/jpeg") return bytes[0] === 0xff && bytes[1] === 0xd8 && bytes[2] === 0xff;
  return false;
}

export async function POST(request: Request) {
  if (!isSameOrigin(request)) return jsonResponse({ error: "ORIGIN_NOT_ALLOWED" }, 403);
  if (!withinRateLimit(request)) return jsonResponse({ error: "RATE_LIMITED" }, 429);
  const declaredSize = Number(request.headers.get("content-length") ?? 0);
  if (declaredSize > MAX_BYTES + 200_000) return jsonResponse({ error: "FILE_TOO_LARGE" }, 413);
  const env = readAgentEnv();
  if (!env.OPENAI_API_KEY?.trim()) return jsonResponse({ error: "RECOGNITION_NOT_CONFIGURED" }, 503);
  try {
    const form = await request.formData();
    const file = form.get("file");
    if (!(file instanceof File)) return jsonResponse({ error: "FILE_REQUIRED" }, 400);
    if (!allowedTypes.has(file.type)) return jsonResponse({ error: "FILE_TYPE_NOT_ALLOWED" }, 415);
    if (!file.size || file.size > MAX_BYTES) return jsonResponse({ error: "FILE_SIZE_NOT_ALLOWED" }, 413);
    const bytes = new Uint8Array(await file.arrayBuffer());
    if (!signatureMatches(file.type, bytes)) return jsonResponse({ error: "FILE_SIGNATURE_MISMATCH" }, 400);
    const result = await runDocumentRecognition(
      { filename: cleanName(file.name), mediaType: file.type, base64: Buffer.from(bytes).toString("base64") },
      env,
      safetyIdentifier(request).replace("db-web", "irene-document"),
    );
    return jsonResponse(result);
  } catch (error) {
    const code = error instanceof Error && /^[A-Z0-9_]+$/.test(error.message) ? error.message : "RECOGNITION_TEMPORARILY_UNAVAILABLE";
    return jsonResponse({ error: code }, 502);
  }
}
