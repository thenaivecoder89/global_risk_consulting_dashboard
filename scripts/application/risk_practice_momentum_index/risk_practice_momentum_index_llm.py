import json
import os
from typing import Any

from scripts.application.risk_practice_momentum_index import risk_practice_momentum_index_api as rpmi_api
from dotenv import load_dotenv
from openai import OpenAI

DEFAULT_MODEL = "gpt-5.5"

LLM_OUTPUT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "executive_summary": {
            "type": "string",
            "description": "Concise management-level summary of risk consulting momentum.",
        },
        "leaderboard_insights": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "firm_name": {"type": "string"},
                    "positioning": {"type": "string"},
                    "key_momentum_drivers": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "management_implication": {"type": "string"},
                },
                "required": [
                    "firm_name",
                    "positioning",
                    "key_momentum_drivers",
                    "management_implication",
                ],
            },
        },
        "cross_firm_themes": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Common themes visible across the firms in the supplied LLM context.",
        },
        "risks_and_caveats": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Important limitations, caveats, and interpretation risks.",
        },
        "recommended_management_actions": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Actionable recommendations for management.",
        },
    },
    "required": [
        "executive_summary",
        "leaderboard_insights",
        "cross_firm_themes",
        "risks_and_caveats",
        "recommended_management_actions",
    ],
}


def parse_json_value(value: Any) -> Any:
    if isinstance(value, str):
        stripped_value = value.strip()
        if stripped_value.startswith("{") or stripped_value.startswith("["):
            try:
                return parse_json_value(json.loads(stripped_value))
            except json.JSONDecodeError:
                return value
    if isinstance(value, list):
        return [parse_json_value(item) for item in value]
    if isinstance(value, dict):
        return {key: parse_json_value(inner_value) for key, inner_value in value.items()}
    return value


def load_risk_practice_momentum_json() -> list[dict[str, Any]]:
    raw_json = rpmi_api.risk_practice_momentum_data_call()
    parsed_json = parse_json_value(raw_json)

    if not isinstance(parsed_json, list):
        raise ValueError("Expected risk practice momentum API output to be a list of records.")

    return parsed_json


def build_llm_payload(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    llm_payload = []
    for record in records:
        llm_payload.append(
            {
                "firm_name": record.get("firm_name", ""),
                "llm_context": parse_json_value(record.get("llm_context", {})),
                "llm_summary": record.get("llm_summary", ""),
            }
        )
    return llm_payload


def extract_response_text(response: Any) -> str:
    response_text = getattr(response, "output_text", "")
    if response_text:
        return response_text

    output_items = getattr(response, "output", []) or []
    text_parts = []
    for output_item in output_items:
        for content_item in getattr(output_item, "content", []) or []:
            text_value = getattr(content_item, "text", None)
            if text_value:
                text_parts.append(text_value)
    return "\n".join(text_parts)


def parse_llm_json(response_text: str) -> dict[str, Any]:
    try:
        parsed_output = json.loads(response_text)
    except json.JSONDecodeError as exc:
        raise ValueError("OpenAI response was not valid JSON.") from exc

    if not isinstance(parsed_output, dict):
        raise ValueError("OpenAI response JSON must be an object.")

    return parsed_output


def call_risk_practice_momentum_llm(
    model: str | None = None,
    max_output_tokens: int = 2000,
) -> dict[str, Any]:
    load_dotenv()

    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY or OPENAI_KEY must be set before calling the OpenAI API.")

    selected_model = model or os.getenv("OPENAI_MODEL") or DEFAULT_MODEL
    records = load_risk_practice_momentum_json()
    llm_payload = build_llm_payload(records)

    prompt = {
        "task": "Analyze risk consulting practice momentum for management.",
        "instructions": [
            "Use only the supplied llm_context and llm_summary fields.",
            "Do not infer from evidence_items, source URLs, raw scores, or any omitted fields.",
            "Treat the supplied scoring as directional public-signal evidence, not confirmed market share, revenue, or commercial performance.",
            "Return concise management-ready insights in the requested JSON schema.",
        ],
        "risk_practice_momentum_records": llm_payload,
    }

    client = OpenAI(api_key=api_key)
    response = client.responses.create(
        model=selected_model,
        input=[
            {
                "role": "system",
                "content": "You are a strategy analyst producing management-ready JSON insights from structured risk consulting momentum summaries.",
            },
            {
                "role": "user",
                "content": json.dumps(prompt, ensure_ascii=False),
            },
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "risk_practice_momentum_management_insights",
                "schema": LLM_OUTPUT_SCHEMA,
                "strict": True,
            }
        },
        max_output_tokens=max_output_tokens,
    )

    return {
        "model": selected_model,
        "input_record_count": len(llm_payload),
        "llm_input_fields": ["firm_name", "llm_context", "llm_summary"],
        "management_insights": parse_llm_json(extract_response_text(response)),
    }


if __name__ == "__main__":
    result = call_risk_practice_momentum_llm()
    print(json.dumps(result, indent=4, ensure_ascii=False))
