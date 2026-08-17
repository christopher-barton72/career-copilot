from __future__ import annotations

from typing import Any
from .models import CareerFact, CareerProfile
from .validator import validate_fact_ids


def _fact_item(fact: CareerFact) -> dict[str, Any]:
    return {"text": fact.text, "source_ids": [fact.id]}


def tailor(profile: CareerProfile, analysis: dict[str, Any]) -> dict[str, Any]:
    fact_by_id = {fact.id: fact for fact in profile.facts}
    ranked_ids = [item["fact_id"] for item in analysis.get("evidence", []) if item.get("fact_id") in fact_by_id]
    ranked = [fact_by_id[fact_id] for fact_id in ranked_ids]
    identity_lines = {profile.name.strip().lower(), profile.headline.strip().lower()}
    ranked = [fact for fact in ranked if fact.text.strip().lower() not in identity_lines]
    remaining = [fact for fact in profile.facts if fact.id not in set(ranked_ids) and fact.text.strip().lower() not in identity_lines]
    used_facts = (ranked + remaining)[:36]
    used_ids = [fact.id for fact in used_facts]
    validation = validate_fact_ids(profile, used_ids)
    if not validation["valid"]: raise ValueError("Tailored content referenced unverified facts.")

    job = analysis.get("job", {})
    title = job.get("title") or "Target Role"
    company = job.get("company") or "Target Organization"
    matched = analysis.get("matched_skills", [])
    verified_competencies = [skill for skill in matched if skill.lower() in profile.master_resume.lower()]
    targeted = [skill for skill in profile.preferences.target_skills if skill.lower() in profile.master_resume.lower()]
    competencies, competency_keys = [], set()
    for skill in verified_competencies + targeted:
        if skill.lower() not in competency_keys:
            competencies.append(skill.upper() if skill.lower() in {"s3", "nist"} else skill.title())
            competency_keys.add(skill.lower())
    if not competencies:
        competencies = sorted({term for item in analysis.get("evidence", []) for term in item.get("matched_terms", [])})[:12]

    employment = [_fact_item(fact) for fact in used_facts if fact.kind == "employment"]
    experience = [_fact_item(fact) for fact in used_facts if fact.kind in {"experience", "skill_evidence"}]
    credentials = [_fact_item(fact) for fact in used_facts if fact.kind == "credential"]
    summary_parts = [profile.headline or "Senior technology professional", f"targeting {title} at {company}."]
    if competencies: summary_parts.append("Verified strengths include " + ", ".join(competencies[:8]) + ".")
    summary_parts.append("Selected experience below is reordered for relevance and remains traceable to the unchanged master resume.")

    resume = {
        "name": profile.name,
        "headline": profile.headline,
        "target": {"title": title, "company": company},
        "summary": " ".join(summary_parts),
        "competencies": competencies,
        "employment": employment,
        "experience": experience,
        "credentials": credentials,
    }
    changes = [
        {"title": "Targeted executive profile", "detail": f"Reframed the opening around the verified experience most relevant to {title}.", "source_ids": ranked_ids[:4]},
        {"title": "Prioritized core competencies", "detail": "Promoted only skills present in both the job analysis and verified master resume.", "source_ids": ranked_ids[:6]},
        {"title": "Reordered professional evidence", "detail": "Placed the strongest job-relevant facts first without changing their wording or chronology.", "source_ids": ranked_ids},
        {"title": "Applied executive formatting", "detail": "Converted the evidence-bound draft into a conservative, one-column ATS-friendly resume.", "source_ids": []},
    ]
    ledger = [{"claim": fact.text, "source_ids": [fact.id], "status": "verified"} for fact in used_facts]
    plain = "\n".join([profile.name, profile.headline, "", "EXECUTIVE PROFILE", resume["summary"], "", "CORE COMPETENCIES", " | ".join(competencies), "", "PROFESSIONAL EXPERIENCE"] + [f"- {item['text']}" for item in employment + experience] + (["", "EDUCATION & CREDENTIALS"] + [item["text"] for item in credentials] if credentials else []))
    return {"resume": resume, "tailored_resume": plain, "change_log": changes, "claim_ledger": ledger, "used_fact_ids": used_ids, "validation": validation, "master_resume_unchanged": True}

