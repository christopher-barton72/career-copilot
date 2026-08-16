from __future__ import annotations

from typing import Any

from .models import CareerProfile
from .validator import validate_fact_ids


def tailor(profile: CareerProfile, analysis: dict[str, Any]) -> dict[str, Any]:
    evidence = analysis.get("evidence", [])[:8]
    ids = [item["fact_id"] for item in evidence]
    validation = validate_fact_ids(profile, ids)
    if not validation["valid"]:
        raise ValueError("Tailored content referenced unverified facts.")
    title = analysis["job"].get("title") or "the target role"
    company = analysis["job"].get("company") or "the organization"
    bullets = "\n".join(f"- {item['fact']} [{item['fact_id']}]" for item in evidence)
    skills = ", ".join(analysis.get("matched_skills", [])) or "See verified experience below"
    resume = f"""{profile.name}\n{profile.headline}\n\nTARGET\n{title} at {company}\n\nRELEVANT SKILLS\n{skills}\n\nSELECTED VERIFIED EXPERIENCE\n{bullets}\n\nSOURCE NOTE\nThis tailored draft is derived only from the unchanged master resume. Bracketed IDs map each claim to the career-truth profile."""
    top = evidence[:3]
    proof = "\n".join(f"- {item['fact']} [{item['fact_id']}]" for item in top)
    cover = f"""Dear Hiring Team,\n\nI am interested in the {title} opportunity at {company}. My background aligns with several priorities in the role, supported by these verified examples:\n\n{proof}\n\nI would welcome a conversation about how this experience could support your team. I have intentionally kept this letter grounded in my verified career history and would be glad to add context in an interview.\n\nSincerely,\n{profile.name}"""
    return {"tailored_resume": resume, "cover_letter": cover, "used_fact_ids": ids, "validation": validation, "master_resume_unchanged": True}
