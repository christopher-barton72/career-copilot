from __future__ import annotations

import hashlib
import re
from collections import OrderedDict
from typing import Any

from .ai import AIConfig, plan_materials, review_materials
from .models import CareerFact, CareerProfile
from .profile import extract_facts
from .validator import validate_claims


def _contact_line(profile: CareerProfile) -> str:
    values = []
    for line in profile.master_resume.splitlines()[:15]:
        cleaned = " ".join(line.split()).strip(" |")
        if cleaned and ("@" in cleaned or re.search(r"\d{3}[-.) ]+\d{3}[- ]+\d{4}", cleaned) or "linkedin.com" in cleaned.lower()):
            values.append(cleaned)
    return " | ".join(dict.fromkeys(values))


def _clean_role(fact: CareerFact) -> str:
    role = re.sub(r"\s*[|,-]?\s*(?:19|20)\d{2}\s*[-–—]\s*(?:(?:19|20)\d{2}|present).*", "", fact.role or "", flags=re.I)
    return role.strip(" |,-")


def _period(fact: CareerFact) -> str:
    return "" if not fact.start_year else f"{fact.start_year} - {'Present' if fact.end_year is None else fact.end_year}"


def _fallback_evidence(profile: CareerProfile, analysis: dict[str, Any]) -> list[dict[str, str]]:
    by_id = {fact.id: fact for fact in extract_facts(profile.master_resume)}
    ids = [item["fact_id"] for item in analysis.get("evidence", []) if item.get("fact_id") in by_id]
    matched = [skill.lower() for skill in analysis.get("matched_skills", [])]
    for fact in profile.facts:
        text = fact.text.lower()
        if any(re.search(rf"(?<![a-z0-9]){re.escape(skill)}(?![a-z0-9])", text) for skill in matched):
            ids.append(fact.id)
    return [{"fact_id": fact_id, "fact": by_id[fact_id].text} for fact_id in list(dict.fromkeys(ids)) if _is_content_fact(profile, by_id[fact_id])][:18]


def _is_content_fact(profile: CareerProfile, fact: CareerFact) -> bool:
    text = re.sub(r"\s+", " ", fact.text).strip()
    if text.lower() == profile.name.lower() or (fact.employer and text.lower() == fact.employer.lower()):
        return False
    return len(text.split()) >= 4


def _expertise(profile: CareerProfile, analysis: dict[str, Any], plan: dict[str, Any] | None, selected_ids: set[str]) -> list[str]:
    if plan and plan.get("expertise"):
        return list(dict.fromkeys(item["label"].strip() for item in plan["expertise"] if item.get("label") and set(item.get("fact_ids", [])) <= selected_ids))[:12]
    fact_text = " ".join(fact.text.lower() for fact in profile.facts if fact.id in selected_ids)
    return [skill.title() for skill in analysis.get("matched_skills", []) if re.search(rf"(?<![a-z0-9]){re.escape(skill.lower())}(?![a-z0-9])", fact_text)][:12]


def _experience_sections(facts: list[CareerFact], highlight_ids: set[str]) -> str:
    grouped: OrderedDict[tuple[str, str, str], list[CareerFact]] = OrderedDict()
    for fact in facts:
        if not fact.employer or fact.employer.upper() in {"LEADERSHIP PHILOSOPHY", "EDUCATION", "EDUCATION & PROFESSIONAL DEVELOPMENT", "CREDENTIALS"}:
            continue
        if re.match(r"^(EDUCATION|CREDENTIALS|LEADERSHIP PHILOSOPHY)\b", fact.text, re.I):
            continue
        grouped.setdefault((fact.employer, _clean_role(fact), _period(fact)), []).append(fact)
    lines: list[str] = []
    for (employer, role, period), group in grouped.items():
        lines.append(f"EMPLOYER: {employer}")
        if role or period:
            lines.append(f"ROLE: {role}{' | ' if role and period else ''}{period}")
        for fact in group:
            if fact.kind != "employment":
                lines.append(f"- {fact.text} [{fact.id}]")
                continue
            trailing = re.sub(r"^.*?(?:19|20)\d{2}\s*[-–—]\s*(?:(?:19|20)\d{2}|present)\s*", "", fact.text, flags=re.I).strip()
            if trailing and trailing != fact.text:
                lines.append(f"- {trailing} [{fact.id}]")
    return "\n".join(lines)


def _cover_paragraphs(title: str, company: str, evidence: list[dict[str, str]], plan: dict[str, Any] | None, conservative: bool) -> list[str]:
    claims = evidence[:6]
    paragraphs = [f"I am writing to express interest in the {title} opportunity at {company}. My background includes experience that aligns with several of the role's priorities."]
    if claims:
        paragraphs.append("In my recent work, " + claims[0]["fact"] + f" [{claims[0]['fact_id']}]")
    if len(claims) > 1:
        paragraphs.append("That foundation is reinforced by the following experience: " + " ".join(f"{item['fact']} [{item['fact_id']}]" for item in claims[1:3]))
    if len(claims) > 3:
        paragraphs.append("Across other assignments, " + " ".join(f"{item['fact']} [{item['fact_id']}]" for item in claims[3:5]))
    if len(claims) > 4:
        paragraphs.append("I would also bring this supporting experience: " + " ".join(f"{item['fact']} [{item['fact_id']}]" for item in claims[4:]))
    paragraphs.append("I would welcome the opportunity to discuss how this experience could support your team's goals. Thank you for your consideration.")
    return paragraphs


def _documents(profile: CareerProfile, analysis: dict[str, Any], evidence: list[dict[str, str]], ai_plan: dict[str, Any] | None, conservative: bool = False) -> dict[str, str]:
    title = analysis["job"].get("title") or "this role"
    company = analysis["job"].get("company") or "your organization"
    by_id = {fact.id: fact for fact in extract_facts(profile.master_resume)}
    selected_facts = sorted((by_id[item["fact_id"]] for item in evidence), key=lambda fact: (fact.start_year or 0), reverse=True)
    selected_ids = {fact.id for fact in selected_facts}
    requested = ai_plan.get("career_highlight_ids", []) if ai_plan and not conservative else []
    highlight_ids = [fact_id for fact_id in requested if fact_id in selected_ids][:4]
    if not highlight_ids:
        highlight_ids = [fact.id for fact in selected_facts if fact.kind != "employment"][:3]
    # Candidate-facing summary text remains an exact user-provided headline. The AI
    # influences evidence selection and ordering, but cannot introduce a new claim.
    summary = profile.headline
    expertise = _expertise(profile, analysis, ai_plan if not conservative else None, selected_ids)
    highlights = "\n".join(f"- {by_id[fact_id].text} [{fact_id}]" for fact_id in highlight_ids)
    experience = _experience_sections(selected_facts, set(highlight_ids))
    contact = _contact_line(profile)
    contact_row = f"\nCONTACT: {contact}" if contact else ""
    resume_parts = [f"{profile.name}\n{profile.headline}{contact_row}", "PROFESSIONAL PROFILE\n" + summary]
    if expertise:
        resume_parts.append("CORE EXPERTISE\n" + " | ".join(expertise))
    if highlights:
        resume_parts.append("CAREER HIGHLIGHTS\n" + highlights)
    if experience:
        resume_parts.append("PROFESSIONAL EXPERIENCE\n" + experience)
    resume = "\n\n".join(resume_parts)
    cover = f"CONTACT: {contact}\nPOSITION: {title} - {company}\n\nDear Hiring Team,\n\n" + "\n\n".join(_cover_paragraphs(title, company, evidence, ai_plan, conservative)) + f"\n\nSincerely,\n{profile.name}"
    return {"tailored_resume": resume, "cover_letter": cover}


def tailor(profile: CareerProfile, analysis: dict[str, Any], config: AIConfig | None = None, transport=None) -> dict[str, Any]:
    config = config or AIConfig.from_env()
    by_id = {fact.id: fact for fact in profile.facts}
    ai_plan = None
    if config.ready:
        ai_plan = plan_materials(profile, analysis, config, transport)
        selected = [fact_id for fact_id in ai_plan["selected_fact_ids"] if _is_content_fact(profile, by_id[fact_id])]
        selected += [item["fact_id"] for item in _fallback_evidence(profile, analysis)]
        evidence = [{"fact_id": fact_id, "fact": by_id[fact_id].text} for fact_id in list(dict.fromkeys(selected))[:18]]
    else:
        evidence = _fallback_evidence(profile, analysis)
    evidence = sorted(evidence, key=lambda item: (by_id[item["fact_id"]].start_year or 0), reverse=True)
    validation = validate_claims(profile, [{"fact_id": item["fact_id"], "text": item["fact"]} for item in evidence])
    if not validation["valid"]:
        raise ValueError("Tailored content referenced unsupported or altered claims.")
    materials = _documents(profile, analysis, evidence, ai_plan)
    digest = hashlib.sha256(profile.master_resume.encode()).hexdigest()
    report = {"before_sha256": digest, "after_sha256": hashlib.sha256(profile.master_resume.encode()).hexdigest(), "unchanged": True, "selected_fact_ids": [item["fact_id"] for item in evidence], "selected_claim_count": len(evidence)}
    ai_review = review_materials(profile, analysis, materials, config, transport) if config.ready else None
    initial_review = None
    revision_applied = False
    if ai_review and (not ai_review["passed"] or ai_review["unsupported_claims"]):
        initial_review = ai_review
        materials = _documents(profile, analysis, evidence, ai_plan, conservative=True)
        ai_review = review_materials(profile, analysis, materials, config, transport)
        revision_applied = True
        if not ai_review["passed"] or ai_review["unsupported_claims"]:
            details = "; ".join(ai_review["unsupported_claims"][:3]) or "review did not pass"
            raise ValueError(f"AI review rejected both the original and conservative drafts: {details}")
    return {**materials, "used_fact_ids": report["selected_fact_ids"], "validation": validation, "master_resume_unchanged": report["unchanged"], "change_report": report, "ai_generated": bool(ai_plan), "ai_plan": ai_plan, "ai_review": ai_review, "ai_initial_review": initial_review, "ai_revision_applied": revision_applied}
