from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .models import CareerProfile
from .validator import validate_fact_ids


API_URL = "https://api.openai.com/v1/responses"
OLLAMA_URL = "http://127.0.0.1:11434/api/chat"


class AIError(RuntimeError):
    """A safe, user-facing AI integration failure."""


@dataclass(frozen=True)
class AIConfig:
    enabled: bool
    model: str
    api_key: str
    provider: str = "openai"
    base_url: str = API_URL

    @classmethod
    def from_env(cls) -> "AIConfig":
        enabled = os.environ.get("CAREER_COPILOT_AI", "").lower() in {"1", "true", "yes", "on"}
        provider = os.environ.get("CAREER_COPILOT_AI_PROVIDER", "ollama").strip().lower()
        if provider not in {"ollama", "openai"}:
            provider = "invalid"
        default_model = "llama3.2" if provider == "ollama" else "gpt-5.2"
        base_url = os.environ.get("CAREER_COPILOT_OLLAMA_URL", OLLAMA_URL) if provider == "ollama" else API_URL
        return cls(enabled, os.environ.get("CAREER_COPILOT_AI_MODEL", default_model), os.environ.get("OPENAI_API_KEY", ""), provider, base_url)

    @property
    def ready(self) -> bool:
        return self.enabled and self.provider in {"ollama", "openai"} and (self.provider == "ollama" or bool(self.api_key))


Transport = Callable[[dict[str, Any], str], dict[str, Any]]


def status(config: AIConfig | None = None) -> dict[str, Any]:
    config = config or AIConfig.from_env()
    return {
        "enabled": config.enabled,
        "ready": config.ready,
        "provider": config.provider if config.enabled else None,
        "model": config.model if config.enabled else None,
        "privacy_notice": ("AI processing stays on this computer through Ollama." if config.provider == "ollama" else "The master resume and job posting are sent to OpenAI for processing."),
        "configuration_error": ("OPENAI_API_KEY is not set." if config.enabled and config.provider == "openai" and not config.api_key else "CAREER_COPILOT_AI_PROVIDER must be ollama or openai." if config.enabled and config.provider == "invalid" else None),
    }


def _http_transport(payload: dict[str, Any], api_key: str) -> dict[str, Any]:
    request = Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise AIError(f"AI request failed with HTTP {exc.code}.") from exc
    except (URLError, TimeoutError) as exc:
        raise AIError("AI service could not be reached.") from exc


def _ollama_transport(payload: dict[str, Any], base_url: str) -> dict[str, Any]:
    parsed = urlparse(base_url)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise AIError("Ollama URL must be a local HTTP address.")
    request = Request(base_url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(request, timeout=180) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise AIError(f"Ollama request failed with HTTP {exc.code}.") from exc
    except TimeoutError as exc:
        raise AIError("Ollama took too long to review the documents. Try again or select a faster local model.") from exc
    except URLError as exc:
        raise AIError("Ollama is not reachable. Start Ollama and confirm the selected model is installed.") from exc


def _request_json(
    name: str,
    instructions: str,
    input_data: dict[str, Any],
    schema: dict[str, Any],
    config: AIConfig,
    transport: Transport | None = None,
) -> dict[str, Any]:
    if not config.ready:
        raise AIError("AI is not configured.")
    if config.provider == "ollama":
        payload = {"model": config.model, "stream": False, "format": schema, "options": {"temperature": 0, "num_ctx": 8192, "num_predict": 1200}, "messages": [{"role": "system", "content": instructions}, {"role": "user", "content": json.dumps(input_data, ensure_ascii=False)}]}
        response = (transport or _ollama_transport)(payload, config.base_url)
        output_text = response.get("message", {}).get("content")
    else:
        payload = {"model": config.model, "store": False, "instructions": instructions, "input": json.dumps(input_data, ensure_ascii=False), "text": {"format": {"type": "json_schema", "name": name, "strict": True, "schema": schema}}}
        response = (transport or _http_transport)(payload, config.api_key)
        output_text = response.get("output_text")
    if not output_text:
        for item in response.get("output", []):
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    output_text = content.get("text")
                    break
    try:
        result = json.loads(output_text or "")
    except (json.JSONDecodeError, TypeError) as exc:
        raise AIError("AI returned an unreadable structured response.") from exc
    return result


def _facts(profile: CareerProfile) -> list[dict[str, str]]:
    return [{"fact_id": fact.id, "text": fact.text} for fact in profile.facts]


def assess_fit(profile: CareerProfile, analysis: dict[str, Any], config: AIConfig, transport: Transport | None = None) -> dict[str, Any]:
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["confidence_score", "recommendation", "rationale", "strengths", "concerns", "interview_questions"],
        "properties": {
            "confidence_score": {"type": "integer", "minimum": 0, "maximum": 100},
            "recommendation": {"type": "string", "enum": ["PRIORITY APPLY", "APPLY", "STRETCH", "SKIP"]},
            "rationale": {"type": "string"},
            "strengths": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["fact_id", "reason"], "properties": {"fact_id": {"type": "string"}, "reason": {"type": "string"}}}},
            "concerns": {"type": "array", "items": {"type": "string"}},
            "interview_questions": {"type": "array", "items": {"type": "string"}},
        },
    }
    result = _request_json(
        "headhunter_fit_assessment",
        "Act as a skeptical senior executive headhunter. Assess candidacy using only the supplied verified facts. Treat missing evidence as unknown, never infer credentials or achievements, and cite a fact_id for every strength. Return a realistic confidence score for interview competitiveness, not a probability of hiring.",
        {"job": analysis["job"], "deterministic_assessment": {key: analysis[key] for key in ("recommendation", "overall_score", "requirements", "preference_assessment", "disqualifiers", "gaps")}, "verified_facts": _facts(profile)},
        schema, config, transport,
    )
    validation = validate_fact_ids(profile, [item["fact_id"] for item in result["strengths"]])
    if not validation["valid"]:
        raise AIError("AI assessment cited evidence that is not in the master resume.")
    # AI judgment may add nuance, but it cannot erase deterministic eligibility blockers.
    if analysis["recommendation"] == "SKIP":
        result["recommendation"] = "SKIP"
        result["confidence_score"] = min(result["confidence_score"], 39)
    elif analysis["recommendation"] == "STRETCH":
        result["confidence_score"] = min(result["confidence_score"], 59)
        if result["recommendation"] in {"PRIORITY APPLY", "APPLY"}:
            result["recommendation"] = "STRETCH"
    result.update({"provider": "Ollama (local)" if config.provider == "ollama" else "OpenAI", "model": config.model, "evidence_validation": validation})
    return result


def plan_materials(profile: CareerProfile, analysis: dict[str, Any], config: AIConfig, transport: Transport | None = None) -> dict[str, Any]:
    schema = {
        "type": "object", "additionalProperties": False,
        "required": ["selected_fact_ids", "resume_summary", "cover_letter_opening"],
        "properties": {
            "selected_fact_ids": {"type": "array", "minItems": 1, "maxItems": 10, "items": {"type": "string"}},
            "resume_summary": {"type": "object", "additionalProperties": False, "required": ["text", "fact_ids"], "properties": {"text": {"type": "string"}, "fact_ids": {"type": "array", "items": {"type": "string"}}}},
            "cover_letter_opening": {"type": "object", "additionalProperties": False, "required": ["text", "fact_ids"], "properties": {"text": {"type": "string"}, "fact_ids": {"type": "array", "items": {"type": "string"}}}},
        },
    }
    result = _request_json(
        "application_material_plan",
        "Act as a senior headhunter creating a concise, professional, ATS-friendly application. Select and order only fact_ids that best support this job. Draft a two-sentence resume summary and a short cover-letter opening. Every factual statement must be directly supported by the cited fact_ids. Never infer or embellish skills, scope, seniority, metrics, credentials, employers, or experience. Avoid generic superlatives.",
        {"job": analysis["job"], "assessment": analysis.get("ai_assessment"), "verified_facts": _facts(profile)},
        schema, config, transport,
    )
    cited_ids = result["selected_fact_ids"] + result["resume_summary"]["fact_ids"] + result["cover_letter_opening"]["fact_ids"]
    validation = validate_fact_ids(profile, cited_ids)
    if not validation["valid"]:
        raise AIError("AI drafting plan selected evidence that is not in the master resume.")
    result["selected_fact_ids"] = list(dict.fromkeys(result["selected_fact_ids"]))
    return result


def review_materials(profile: CareerProfile, analysis: dict[str, Any], materials: dict[str, str], config: AIConfig, transport: Transport | None = None) -> dict[str, Any]:
    schema = {
        "type": "object", "additionalProperties": False,
        "required": ["passed", "unsupported_claims", "professionalism_score", "review_notes"],
        "properties": {
            "passed": {"type": "boolean"},
            "unsupported_claims": {"type": "array", "maxItems": 10, "items": {"type": "string", "maxLength": 300}},
            "professionalism_score": {"type": "integer", "minimum": 0, "maximum": 100},
            "review_notes": {"type": "array", "maxItems": 10, "items": {"type": "string", "maxLength": 300}},
        },
    }
    cited_ids = set()
    for text in materials.values():
        cited_ids.update(re.findall(r"\[(fact_[a-f0-9]+)\]", text))
    listed_skills = analysis.get("matched_skills", [])
    def supports_listed_skill(text: str) -> bool:
        return any(re.search(rf"(?<![a-z0-9]){re.escape(skill)}(?![a-z0-9])", text, re.I) for skill in listed_skills)
    def is_contact_fact(text: str) -> bool:
        return "@" in text or "linkedin.com" in text.lower() or bool(re.search(r"\d{3}[-.) ]+\d{3}[- ]+\d{4}", text))
    review_facts = [{"fact_id": fact.id, "text": fact.text} for fact in profile.facts if fact.id in cited_ids or supports_listed_skill(fact.text) or is_contact_fact(fact.text)]
    result = _request_json(
        "application_material_review",
        "Act as a meticulous senior headhunter and factual reviewer. Compare every candidate claim with the verified facts. Fail if anything is invented, embellished, materially paraphrased beyond the evidence, or misleading. Exact text copied from a verified fact is supported. Job titles, company names, and neutral application language are not candidate claims. Keep every unsupported-claim excerpt and review note under 200 characters; never repeat a whole document.",
        {"job": {key: analysis["job"].get(key, "") for key in ("title", "company")}, "verified_facts": review_facts, "materials": materials},
        schema, config, transport,
    )
    def normalized(value: str) -> str:
        return re.sub(r"\s+", " ", value.lower().strip(" .-"))
    fact_texts = [normalized(item["text"]) for item in review_facts]
    false_positives=[]; unsupported=[]
    for claim in result["unsupported_claims"]:
        candidate=normalized(claim)
        if candidate and any(candidate in fact or fact in candidate for fact in fact_texts): false_positives.append(claim)
        else: unsupported.append(claim)
    result["unsupported_claims"] = unsupported
    result["evidence_reconciled_claims"] = len(false_positives)
    if not unsupported and false_positives: result["passed"] = True
    return result
