import type { AgentEnv } from "./openai-agent.ts";

export type DocumentRecognition = {
  documentType: string;
  summary: string;
  facts: Array<{ field: string; value: string | number | null; unit: string; sourceLocation: string; confidence: number }>;
  equipment: Array<{ identifier: string; type: string; capacity: string | number | null; unit: string; sourceLocation: string }>;
  reviewItems: string[];
  retention: "store:false";
};

type RawRecognition = {
  document_type: string;
  summary: string;
  facts: Array<{ field: string; value: string | number | null; unit: string; source_location: string; confidence: number }>;
  equipment: Array<{ identifier: string; type: string; capacity: string | number | null; unit: string; source_location: string }>;
  review_items: string[];
};

const schema = {
  type: "object",
  properties: {
    document_type: { type: "string" },
    summary: { type: "string" },
    facts: {
      type: "array",
      items: {
        type: "object",
        properties: {
          field: { type: "string" },
          value: { anyOf: [{ type: "string" }, { type: "number" }, { type: "null" }] },
          unit: { type: "string" },
          source_location: { type: "string" },
          confidence: { type: "number", minimum: 0, maximum: 1 },
        },
        required: ["field", "value", "unit", "source_location", "confidence"],
        additionalProperties: false,
      },
    },
    equipment: {
      type: "array",
      items: {
        type: "object",
        properties: {
          identifier: { type: "string" },
          type: { type: "string" },
          capacity: { anyOf: [{ type: "string" }, { type: "number" }, { type: "null" }] },
          unit: { type: "string" },
          source_location: { type: "string" },
        },
        required: ["identifier", "type", "capacity", "unit", "source_location"],
        additionalProperties: false,
      },
    },
    review_items: { type: "array", items: { type: "string" } },
  },
  required: ["document_type", "summary", "facts", "equipment", "review_items"],
  additionalProperties: false,
} as const;

function outputText(response: Record<string, unknown>) {
  if (typeof response.output_text === "string") return response.output_text;
  const output = Array.isArray(response.output) ? response.output : [];
  return output.flatMap((item) => {
    if (!item || typeof item !== "object" || !Array.isArray((item as Record<string, unknown>).content)) return [];
    return ((item as Record<string, unknown>).content as unknown[]).flatMap((content) =>
      content && typeof content === "object" && (content as Record<string, unknown>).type === "output_text" && typeof (content as Record<string, unknown>).text === "string"
        ? [(content as Record<string, unknown>).text as string]
        : [],
    );
  }).join("\n");
}

function chooseModel(env: AgentEnv) {
  const allowed = (env.OPENAI_ALLOWED_MODELS ?? "gpt-5.6-luna,gpt-5.6-terra,gpt-5.6-sol").split(",").map((item) => item.trim()).filter(Boolean);
  const requested = process.env.OPENAI_ONBOARDING_MODEL?.trim();
  return requested && allowed.includes(requested) ? requested : allowed.includes("gpt-5.6-luna") ? "gpt-5.6-luna" : allowed[0];
}

export async function runDocumentRecognition(
  file: { filename: string; mediaType: string; base64: string },
  env: AgentEnv,
  safetyIdentifier: string,
  fetchImpl: typeof fetch = fetch,
): Promise<DocumentRecognition> {
  if (!env.OPENAI_API_KEY?.trim()) throw new Error("RECOGNITION_NOT_CONFIGURED");
  const dataUrl = `data:${file.mediaType};base64,${file.base64}`;
  const attachment = file.mediaType === "application/pdf"
    ? { type: "input_file", filename: file.filename, file_data: dataUrl }
    : { type: "input_image", image_url: dataUrl, detail: "high" };
  const response = await fetchImpl(`${(env.OPENAI_BASE_URL ?? "https://api.openai.com/v1").replace(/\/$/, "")}/responses`, {
    method: "POST",
    headers: { authorization: `Bearer ${env.OPENAI_API_KEY}`, "content-type": "application/json" },
    body: JSON.stringify({
      model: chooseModel(env),
      store: false,
      safety_identifier: safetyIdentifier.slice(0, 64),
      max_output_tokens: 1_800,
      input: [{ role: "user", content: [
        { type: "input_text", text: "Extract only visible, decision-relevant building and energy facts from this client document. Prioritise dates, electricity use, demand, tariff, bill totals, floor area, operating hours, equipment identifiers, equipment type and rated capacity. Preserve source units. Do not infer missing values. Give a page, region or label in source_location and put uncertainty in review_items." },
        attachment,
      ] }],
      text: { format: { type: "json_schema", name: "client_energy_document_extraction", strict: true, schema } },
    }),
  });
  if (!response.ok) throw new Error(`RECOGNITION_HTTP_${response.status}`);
  const rawResponse = await response.json() as Record<string, unknown>;
  const text = outputText(rawResponse);
  if (!text) throw new Error("RECOGNITION_EMPTY_RESULT");
  const parsed = JSON.parse(text) as RawRecognition;
  return {
    documentType: parsed.document_type,
    summary: parsed.summary,
    facts: parsed.facts.map((item) => ({ ...item, sourceLocation: item.source_location })),
    equipment: parsed.equipment.map((item) => ({ ...item, sourceLocation: item.source_location })),
    reviewItems: parsed.review_items,
    retention: "store:false",
  };
}
