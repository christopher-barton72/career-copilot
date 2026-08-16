from __future__ import annotations

import re
from dataclasses import asdict
from typing import Any

from .models import CareerFact, CareerProfile


STOP = {"and", "the", "with", "for", "that", "this", "from", "your", "you", "our", "are", "will", "have", "has", "into", "job", "role", "work", "team", "years", "experience", "skills", "required", "preferred"}
KNOWN_SKILLS = {"aws", "azure", "gcp", "python", "java", "javascript", "typescript", "sql", "kubernetes", "docker", "terraform", "vmware", "linux", "windows", "netapp", "dell", "pure", "vast", "nist", "zero trust", "s3", "devops", "security", "storage", "networking", "agile", "scrum", "salesforce", "splunk", "servicenow", "ansible", "cisco"}


def tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-zA-Z][a-zA-Z0-9+#.\-]{1,}", text.lower()) if w not in STOP}


def extract_salary(text: str) -> dict[str, Any] | None:
    values = []
    for amount, suffix in re.findall(r"\$\s?([0-9]{2,3}(?:,[0-9]{3})?|[0-9]{2,3})([kK]?)", text):
        number = int(amount.replace(",", "")) * (1000 if suffix else 1)
        if 30_000 <= number <= 1_000_000:
            values.append(number)
    if not values:
        return None
    return {"source": "employer_posted", "minimum": min(values), "maximum": max(values), "confidence": "high", "note": "Extracted from the supplied job posting; verify against the original listing."}


def _evidence(job_terms: set[str], facts: list[CareerFact]) -> list[dict[str, Any]]:
    ranked = []
    for fact in facts:
        overlap = job_terms & tokens(fact.text)
        if overlap:
            ranked.append((len(overlap), {"fact_id": fact.id, "fact": fact.text, "matched_terms": sorted(overlap)[:8], "source": fact.source, "confidence": fact.confidence}))
    return [item for _, item in sorted(ranked, key=lambda x: x[0], reverse=True)[:10]]


def analyze(profile: CareerProfile, payload: dict) -> dict[str, Any]:
    description = payload.get("description", "").strip()
    if len(description) < 100:
        raise ValueError("Job description must contain at least 100 characters.")
    job_terms = tokens(description)
    resume_terms = tokens(profile.master_resume)
    evidence = _evidence(job_terms, profile.facts)
    job_skills = {s for s in KNOWN_SKILLS if s in description.lower()}
    resume_skills = {s for s in KNOWN_SKILLS if s in profile.master_resume.lower()}
    matched_skills = sorted(job_skills & resume_skills)
    missing_skills = sorted(job_skills - resume_skills)
    skills_score = round(100 * len(matched_skills) / max(1, len(job_skills))) if job_skills else 70
    lexical = round(100 * len(job_terms & resume_terms) / max(1, min(len(job_terms), 80)))
    experience_score = min(100, round(lexical * 1.6 + min(30, len(evidence) * 3)))

    title = payload.get("title", "").strip()
    target_roles = profile.preferences.target_roles
    title_terms = tokens(title)
    role_overlap = max((len(title_terms & tokens(role)) for role in target_roles), default=0)
    seniority_score = 90 if role_overlap else (70 if not target_roles else 55)
    mode_text = description.lower()
    modes = profile.preferences.work_modes
    preference_hits = [m for m in modes if m.lower() in mode_text]
    preference_score = 90 if preference_hits else (70 if not modes else 55)

    posted = extract_salary(description)
    minimum = profile.preferences.minimum_salary
    compensation_score = 70
    disqualifiers = []
    if posted and minimum and posted["maximum"] < minimum:
        compensation_score = 20
        disqualifiers.append(f"Posted maximum ${posted['maximum']:,} is below your minimum ${minimum:,}.")
    elif posted and minimum and posted["minimum"] >= minimum:
        compensation_score = 100
    market = None
    if not posted:
        target = profile.preferences.target_salary or minimum
        if target:
            market = {"source": "candidate_target_proxy", "minimum": round(target * .9), "maximum": round(target * 1.1), "confidence": "low", "note": "Not market research. Planning range derived from your target and must be externally verified."}

    for item in profile.preferences.dealbreakers:
        if item and item.lower() in mode_text:
            disqualifiers.append(f"Posting appears to include your dealbreaker: {item}.")
    travel = re.search(r"(\d{1,3})\s*%\s*travel", mode_text)
    if travel and profile.preferences.travel_max_percent is not None and int(travel.group(1)) > profile.preferences.travel_max_percent:
        disqualifiers.append(f"Posting requires {travel.group(1)}% travel; your maximum is {profile.preferences.travel_max_percent}%.")

    overall = round(experience_score * .35 + skills_score * .30 + seniority_score * .15 + preference_score * .12 + compensation_score * .08)
    if disqualifiers:
        recommendation = "SKIP"
    elif overall >= 85 and not missing_skills:
        recommendation = "PRIORITY APPLY"
    elif overall >= 72:
        recommendation = "APPLY"
    elif overall >= 55:
        recommendation = "STRETCH"
    else:
        recommendation = "SKIP"
    gaps = [f"No verified evidence found for requested skill: {skill}." for skill in missing_skills]
    if not evidence:
        gaps.append("The posting has little direct overlap with verified career facts.")

    return {
        "schema_version": 1,
        "job": {"title": title, "company": payload.get("company", "").strip(), "source_url": payload.get("source_url", "").strip(), "description": description},
        "overall_score": overall,
        "recommendation": recommendation,
        "score_breakdown": {"experience": experience_score, "skills": skills_score, "seniority": seniority_score, "preferences": preference_score, "compensation": compensation_score},
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
        "evidence": evidence,
        "gaps": gaps,
        "disqualifiers": disqualifiers,
        "compensation": {"employer_posted": posted, "market_estimate": market},
        "explanation": f"{recommendation}: score {overall}/100 based on verified resume evidence and saved preferences. Review gaps and source facts before deciding.",
        "safety": {"applies_to_jobs": False, "master_resume_modified": False, "evidence_required": True},
    }
