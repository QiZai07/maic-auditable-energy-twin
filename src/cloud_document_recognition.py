from __future__ import annotations

import base64
import json
import mimetypes
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

from src.client_onboarding import MAX_FILE_BYTES, validate_upload


RESPONSES_URL = "https://api.openai.com/v1/responses"
CLOUD_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff"}
CLOUD_MAX_BYTES = min(MAX_FILE_BYTES, 12 * 1024 * 1024)
DEFAULT_MODEL = "gpt-5.6-luna"


EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "document_type": {"type": "string"},
        "summary": {"type": "string"},
        "facts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "field": {"type": "string"},
                    "value": {"type": ["string", "number", "null"]},
                    "unit": {"type": "string"},
                    "source_location": {"type": "string"},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                },
                "required": ["field", "value", "unit", "source_location", "confidence"],
                "additionalProperties": False,
            },
        },
        "equipment": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "identifier": {"type": "string"},
                    "type": {"type": "string"},
                    "capacity": {"type": ["string", "number", "null"]},
                    "unit": {"type": "string"},
                    "source_location": {"type": "string"},
                },
                "required": ["identifier", "type", "capacity", "unit", "source_location"],
                "additionalProperties": False,
            },
        },
        "review_items": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["document_type", "summary", "facts", "equipment", "review_items"],
    "additionalProperties": False,
}


def _default_transport(payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
    request = urllib.request.Request(
        RESPONSES_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        if error.code == 429:
            raise RuntimeError(
                "Document recognition is connected, but the current API quota or rate limit does not allow this request. Check platform billing and retry."
            ) from error
        try:
            message = json.loads(body).get("error", {}).get("message", body)
        except json.JSONDecodeError:
            message = body
        raise RuntimeError(f"Cloud recognition request failed ({error.code}): {message[:500]}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"Cloud recognition is unreachable: {error.reason}") from error


def _output_text(response: dict[str, Any]) -> str:
    if isinstance(response.get("output_text"), str):
        return response["output_text"]
    pieces: list[str] = []
    for item in response.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") == "output_text" and isinstance(content.get("text"), str):
                pieces.append(content["text"])
    return "\n".join(pieces)


def recognise_document(
    name: str,
    content: bytes,
    api_key: str,
    *,
    model: str = DEFAULT_MODEL,
    transport: Callable[[dict[str, Any], dict[str, str]], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    clean_name, _, _ = validate_upload(name, content)
    extension = Path(clean_name).suffix.lower()
    if extension not in CLOUD_EXTENSIONS:
        raise ValueError("Cloud recognition is limited to PDF and image files.")
    if len(content) > CLOUD_MAX_BYTES:
        raise ValueError(f"Cloud recognition accepts files up to {CLOUD_MAX_BYTES // 1024 // 1024} MB.")
    if not api_key or not api_key.strip():
        raise ValueError("Cloud recognition is not configured for this deployment.")

    mime_type = mimetypes.guess_type(clean_name)[0] or "application/octet-stream"
    data_url = f"data:{mime_type};base64,{base64.b64encode(content).decode('ascii')}"
    attachment = (
        {"type": "input_file", "filename": clean_name, "file_data": data_url}
        if extension == ".pdf"
        else {"type": "input_image", "image_url": data_url, "detail": "high"}
    )
    payload = {
        "model": model,
        "store": False,
        "input": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "Extract only visible, decision-relevant building and energy facts from this client document. "
                            "Prioritise dates, electricity use, demand, tariff, bill totals, floor area, operating hours, "
                            "equipment identifiers, equipment type and rated capacity. Preserve source units. Do not infer "
                            "missing values. Give a page, region or label in source_location and put uncertainty in review_items."
                        ),
                    },
                    attachment,
                ],
            }
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "client_energy_document_extraction",
                "strict": True,
                "schema": EXTRACTION_SCHEMA,
            }
        },
    }
    response = (transport or _default_transport)(
        payload,
        {"Authorization": f"Bearer {api_key.strip()}", "Content-Type": "application/json"},
    )
    text = _output_text(response)
    if not text:
        raise RuntimeError("Cloud recognition returned no structured result.")
    try:
        result = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Cloud recognition returned an invalid structured result.") from exc
    result["model"] = model
    result["request_id"] = response.get("id", "")
    result["retention"] = "store:false"
    return result
