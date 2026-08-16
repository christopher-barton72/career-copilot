from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone

from .models import CareerFact, CareerProfile, Preferences


SKILL_TERMS = {
    "aws", "azure", "gcp", "python", "java", "javascript", "typescript", "sql",
    "kubernetes", "docker", "terraform", "vmware", "linux", "windows", "netapp",
    "dell", "pure", "vast", "nist", "zero trust", "s3", "security", "storage",
    "architecture", "leadership", "agile", "scrum", "devops", "networking",
}


def _fact_id(text: str) -> str:
    return "fact_" + hashlib.sha256(text.lower().strip().encode()).hexdigest()[:10]


def extract_facts(resume: str) -> list[CareerFact]:
    facts: list[CareerFact] = []
    seen: set[str] = set()
    lines = [re.sub(r"^[\s•*\-–—]+", "", line).strip() for line in resume.splitlines()]
    for line in lines:
        if len(line) < 12 or len(line) > 420:
            continue
        normalized = re.sub(r"\s+", " ", line)
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        kind = "experience"
        if re.search(r"\b(19|20)\d{2}\b|\bpresent\b", key):
            kind = "employment"
        elif any(term in key for term in SKILL_TERMS):
            kind = "skill_evidence"
        elif re.search(r"\b(certif|degree|bachelor|master|university|college)\b", key):
            kind = "credential"
        facts.append(CareerFact(id=_fact_id(normalized), text=normalized, kind=kind))
    return facts[:250]


def build_profile(payload: dict, existing: CareerProfile | None = None) -> CareerProfile:
    resume = payload.get("master_resume", "").strip()
    if len(resume) < 80:
        raise ValueError("Master resume must contain at least 80 characters.")
    now = datetime.now(timezone.utc).isoformat()
    prefs = Preferences(**payload.get("preferences", {}))
    return CareerProfile(
        name=payload.get("name", "").strip(),
        headline=payload.get("headline", "").strip(),
        master_resume=resume,
        preferences=prefs,
        facts=extract_facts(resume),
        created_at=existing.created_at if existing else now,
        updated_at=now,
    )
