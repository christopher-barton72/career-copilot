from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from .models import CareerFact, CareerProfile


STOP = {"and", "the", "with", "for", "that", "this", "from", "your", "you", "our", "are", "will", "have", "has", "into", "job", "role", "work", "team", "years", "experience", "skills", "required", "preferred", "to", "of", "in", "on", "a", "an", "by", "or", "as", "at", "be", "is"}
KNOWN_SKILLS = {"aws", "azure", "gcp", "python", "java", "javascript", "typescript", "sql", "kubernetes", "docker", "terraform", "vmware", "linux", "windows", "netapp", "dell", "pure", "vast", "nist", "zero trust", "s3", "devops", "security", "storage", "networking", "agile", "scrum", "salesforce", "splunk", "servicenow", "ansible", "cisco"}
REQUIRED_MARKERS = ("required", "must have", "must possess", "minimum qualification", "minimum requirement", "you have", "you bring")
PREFERRED_MARKERS = ("preferred", "nice to have", "bonus", "desirable", "a plus")
WORK_MODES = {"remote": ("remote", "work from home", "telework"), "hybrid": ("hybrid",), "onsite": ("on-site", "onsite", "in office", "in-office")}
EMPLOYMENT_TYPES = {"full-time": ("full-time", "full time"), "part-time": ("part-time", "part time"), "contract": ("contract", "contractor", "consulting engagement"), "temporary": ("temporary", "temp position", "fixed-term")}


def tokens(text: str) -> set[str]:
    return {word for word in re.findall(r"[a-zA-Z][a-zA-Z0-9+#.\-]{1,}", text.lower()) if word not in STOP}


def _contains_term(text: str, term: str) -> bool:
    return bool(re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", text, re.I))


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+|[\r\n]+", text) if part.strip()]


def _skills_in(text: str) -> set[str]:
    return {skill for skill in KNOWN_SKILLS if _contains_term(text, skill)}


def extract_salary(text: str) -> dict[str, Any] | None:
    values = []
    for match in re.finditer(r"\$\s?(?P<amount>[0-9]{2,3}(?:,[0-9]{3})*(?:\.[0-9]{1,2})?)(?P<suffix>[kK]?)", text):
        amount = float(match.group("amount").replace(",", "")); suffix = match.group("suffix")
        number = amount * (1000 if suffix else 1)
        context = text[max(0, match.start() - 30):min(len(text), match.end() + 45)]
        if 15 <= number <= 500 and re.search(r"(?:per\s+|/)\s*(?:hour|hr)\b|\b(?:hourly|hour|hr)\b", context, re.I):
            number = number * 2080
        number = round(number)
        if 30_000 <= number <= 1_000_000:
            values.append(number)
    if not values:
        return None
    return {"source": "employer_posted", "minimum": min(values), "maximum": max(values), "confidence": "high", "note": "Extracted from the supplied posting and annualized at 2,080 hours when explicitly hourly; verify against the original listing."}


def _extract_requirements(description: str, resume: str, facts: list[CareerFact]) -> dict[str, Any]:
    required_text = " ".join(sentence for sentence in _sentences(description) if any(marker in sentence.lower() for marker in REQUIRED_MARKERS))
    preferred_text = " ".join(sentence for sentence in _sentences(description) if any(marker in sentence.lower() for marker in PREFERRED_MARKERS))
    all_job_skills = _skills_in(description)
    required_skills = _skills_in(required_text)
    preferred_skills = _skills_in(preferred_text) - required_skills
    general_skills = all_job_skills - required_skills - preferred_skills
    resume_skills = _skills_in(resume)

    minimum_years = None
    years_match = re.search(r"(?:minimum(?:\s+of)?|at least|requires?|must have)?\s*(\d{1,2})\+?\s+years?(?:\s+of)?\s+(?:relevant\s+)?experience", description, re.I)
    if years_match: minimum_years = int(years_match.group(1))
    explicit_resume_years = [int(value) for value in re.findall(r"\b(\d{1,2})\+?\s+years?(?:\s+of)?\s+experience", resume, re.I)]
    start_years = [fact.start_year for fact in facts if fact.start_year]
    career_span = datetime.now(timezone.utc).year - min(start_years) if start_years else None
    supported_years = max(explicit_resume_years + ([career_span] if career_span is not None else []), default=None)

    degree_required = bool(re.search(r"(?:required|must have|minimum qualifications?)[^\n.]{0,100}\b(?:bachelor'?s?|undergraduate|college degree)\b|\b(?:bachelor'?s?|undergraduate|college degree)\b[^\n.]{0,60}(?:required|minimum)", description, re.I))
    degree_supported = bool(re.search(r"\b(bachelor'?s?|master'?s?|ph\.?d|degree)\b", resume, re.I))
    unmet = []
    for skill in sorted(required_skills - resume_skills): unmet.append({"type": "required_skill", "value": skill, "message": f"No verified evidence for required skill: {skill}."})
    if minimum_years is not None and (supported_years is None or supported_years < minimum_years):
        detail = "not established" if supported_years is None else f"approximately {supported_years}"
        unmet.append({"type": "minimum_experience", "value": minimum_years, "message": f"Posting requires {minimum_years}+ years of experience; verified history supports {detail}."})
    if degree_required and not degree_supported:
        unmet.append({"type": "required_education", "value": "degree", "message": "Posting explicitly requires a degree; no degree is verified in the master resume."})

    requirement_count = len(required_skills) + (1 if minimum_years is not None else 0) + (1 if degree_required else 0)
    score = round(100 * (requirement_count - len(unmet)) / requirement_count) if requirement_count else 70
    return {"required_skills": sorted(required_skills), "preferred_skills": sorted(preferred_skills), "general_skills": sorted(general_skills), "matched_required_skills": sorted(required_skills & resume_skills), "missing_required_skills": sorted(required_skills - resume_skills), "missing_preferred_skills": sorted(preferred_skills - resume_skills), "minimum_years": minimum_years, "supported_years": supported_years, "degree_required": degree_required, "degree_supported": degree_supported, "unmet": unmet, "score": score}


def _extract_location(payload: dict, description: str) -> str:
    supplied = payload.get("location", "").strip()
    if supplied: return supplied
    for pattern in (r"(?:job\s+)?location\s*[:\-]\s*([^\n|;]{2,80})", r"(?:based|located)\s+in\s+([A-Z][A-Za-z .'-]+(?:,\s*[A-Z]{2})?)"):
        match = re.search(pattern, description, re.I)
        if match: return match.group(1).strip().rstrip(".")
    return ""


def _location_terms(value: str) -> set[str]:
    return {term for term in re.findall(r"[a-z]{2,}", value.lower()) if len(term) > 2 and term not in {"area", "greater", "metro", "metropolitan", "united", "states", "usa"}}


def _preference_assessment(profile: CareerProfile, payload: dict, description: str) -> dict[str, Any]:
    lower = description.lower()
    job_modes = {mode for mode, phrases in WORK_MODES.items() if any(_contains_term(lower, phrase) for phrase in phrases)}
    if "remote" in job_modes and re.search(r"remote\s+(?:within|in|from)\s+", lower):
        job_modes.add("restricted_remote")
    preferred_modes = {mode.lower().replace("on-site", "onsite") for mode in profile.preferences.work_modes}
    mode_match = not preferred_modes or not job_modes or bool(preferred_modes & job_modes)

    job_location = _extract_location(payload, description)
    candidate_location = profile.preferences.location.strip()
    location_match = None
    if job_location and candidate_location and not (job_modes == {"remote"}):
        job_location_terms, candidate_location_terms = _location_terms(job_location), _location_terms(candidate_location)
        if job_location_terms and candidate_location_terms: location_match = bool(job_location_terms & candidate_location_terms)

    job_types = {kind for kind, phrases in EMPLOYMENT_TYPES.items() if any(_contains_term(lower, phrase) for phrase in phrases)}
    preferred_types = {value.lower().replace("full time", "full-time").replace("part time", "part-time") for value in profile.preferences.employment_types}
    employment_match = not preferred_types or not job_types or bool(preferred_types & job_types)

    issues = []
    if job_modes and preferred_modes and not mode_match: issues.append(f"Posting work mode ({', '.join(sorted(job_modes))}) does not match your preference ({', '.join(sorted(preferred_modes))}).")
    if location_match is False and job_modes & {"onsite", "hybrid"}: issues.append(f"Posting location ({job_location}) does not match your saved location ({candidate_location}) for an on-site or hybrid role.")
    if job_types and preferred_types and not employment_match: issues.append(f"Posting employment type ({', '.join(sorted(job_types))}) does not match your preference ({', '.join(sorted(preferred_types))}).")
    score = 100 if not issues and (job_modes or job_location or job_types) else (70 if not issues else max(10, 100 - 35 * len(issues)))
    return {"job_location": job_location, "candidate_location": candidate_location, "location_match": location_match, "job_work_modes": sorted(job_modes), "preferred_work_modes": sorted(preferred_modes), "work_mode_match": mode_match, "job_employment_types": sorted(job_types), "preferred_employment_types": sorted(preferred_types), "employment_type_match": employment_match, "issues": issues, "score": score}


def _evidence(job_terms: set[str], facts: list[CareerFact]) -> list[dict[str, Any]]:
    ranked = []
    for fact in facts:
        overlap = job_terms & tokens(fact.text)
        if overlap: ranked.append((len(overlap), len(fact.text), {"fact_id": fact.id, "fact": fact.text, "matched_terms": sorted(overlap)[:8], "source": fact.source, "confidence": fact.confidence}))
    return [item for _, _, item in sorted(ranked, key=lambda item: (item[0], item[1]), reverse=True)[:10]]


def analyze(profile: CareerProfile, payload: dict) -> dict[str, Any]:
    description = payload.get("description", "").strip()
    if len(description) < 100: raise ValueError("Job description must contain at least 100 characters.")
    job_terms, resume_terms = tokens(description), tokens(profile.master_resume)
    evidence = _evidence(job_terms, profile.facts)
    requirements = _extract_requirements(description, profile.master_resume, profile.facts)
    preference = _preference_assessment(profile, payload, description)

    job_skills = set(requirements["required_skills"] + requirements["preferred_skills"] + requirements["general_skills"])
    resume_skills = _skills_in(profile.master_resume)
    matched_skills, missing_skills = sorted(job_skills & resume_skills), sorted(job_skills - resume_skills)
    skills_score = round(100 * len(matched_skills) / len(job_skills)) if job_skills else 70
    lexical = round(100 * len(job_terms & resume_terms) / max(1, min(len(job_terms), 80)))
    experience_score = min(100, round(lexical * 1.35 + min(25, len(evidence) * 2.5)))

    title = payload.get("title", "").strip(); title_terms = tokens(title)
    role_scores = [len(title_terms & tokens(role)) / max(1, len(title_terms | tokens(role))) for role in profile.preferences.target_roles]
    best_role = max(role_scores, default=0)
    seniority_score = round(50 + 50 * best_role) if profile.preferences.target_roles else 70

    posted = extract_salary(description); minimum = profile.preferences.minimum_salary; compensation_score = 70; disqualifiers = []
    if posted and minimum and posted["maximum"] < minimum:
        compensation_score = 20; disqualifiers.append(f"Posted maximum ${posted['maximum']:,} is below your minimum ${minimum:,}.")
    elif posted and minimum and posted["minimum"] >= minimum: compensation_score = 100
    market = None
    if not posted:
        target = profile.preferences.target_salary or minimum
        if target: market = {"source": "candidate_target_proxy", "minimum": round(target * .9), "maximum": round(target * 1.1), "confidence": "low", "note": "Not market research. Planning range derived from your target and must be externally verified."}

    lower = description.lower()
    for item in profile.preferences.dealbreakers:
        if item and _contains_term(lower, item): disqualifiers.append(f"Posting appears to include your dealbreaker: {item}.")
    travel = re.search(r"(\d{1,3})\s*%\s*travel", lower)
    if travel and profile.preferences.travel_max_percent is not None and int(travel.group(1)) > profile.preferences.travel_max_percent:
        disqualifiers.append(f"Posting requires {travel.group(1)}% travel; your maximum is {profile.preferences.travel_max_percent}%.")
    disqualifiers.extend(preference["issues"])

    overall = round(experience_score * .25 + skills_score * .20 + requirements["score"] * .25 + seniority_score * .10 + preference["score"] * .12 + compensation_score * .08)
    unmet_count = len(requirements["unmet"])
    if disqualifiers or unmet_count >= 2 or any(item["type"] == "required_education" for item in requirements["unmet"]): recommendation = "SKIP"
    elif unmet_count == 1: recommendation = "STRETCH"
    elif overall >= 85 and not requirements["missing_required_skills"] and not requirements["missing_preferred_skills"]: recommendation = "PRIORITY APPLY"
    elif overall >= 72: recommendation = "APPLY"
    elif overall >= 55: recommendation = "STRETCH"
    else: recommendation = "SKIP"

    gaps = [item["message"] for item in requirements["unmet"]]
    gaps.extend(f"No verified evidence found for preferred skill: {skill}." for skill in requirements["missing_preferred_skills"])
    gaps.extend(f"No verified evidence found for mentioned skill: {skill}." for skill in sorted(set(missing_skills) - set(requirements["missing_required_skills"]) - set(requirements["missing_preferred_skills"])))
    if not evidence: gaps.append("The posting has little direct overlap with verified career facts.")

    return {"schema_version": 2, "job": {"title": title, "company": payload.get("company", "").strip(), "location": preference["job_location"], "source_url": payload.get("source_url", "").strip(), "description": description}, "overall_score": overall, "recommendation": recommendation, "score_breakdown": {"experience": experience_score, "skills": skills_score, "requirements": requirements["score"], "seniority": seniority_score, "preferences": preference["score"], "compensation": compensation_score}, "matched_skills": matched_skills, "missing_skills": missing_skills, "requirements": requirements, "preference_assessment": preference, "evidence": evidence, "gaps": gaps, "disqualifiers": disqualifiers, "compensation": {"employer_posted": posted, "market_estimate": market}, "explanation": f"{recommendation}: score {overall}/100 after checking verified evidence, explicit requirements, location/work-mode compatibility, employment type, and compensation.", "safety": {"applies_to_jobs": False, "master_resume_modified": False, "evidence_required": True}}

