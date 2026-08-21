from __future__ import annotations
import hashlib
import re
from typing import Any
from .models import CareerProfile
from .validator import validate_claims
from .ai import AIConfig, plan_materials, review_materials

def _contact_line(profile: CareerProfile) -> str:
    values=[]
    for line in profile.master_resume.splitlines()[:15]:
        cleaned=" ".join(line.split()).strip(" |")
        if cleaned and ("@" in cleaned or re.search(r"\d{3}[-.) ]+\d{3}[- ]+\d{4}", cleaned) or "linkedin.com" in cleaned.lower()):
            values.append(cleaned)
    return " | ".join(dict.fromkeys(values))

def _documents(profile: CareerProfile, analysis: dict[str, Any], evidence: list[dict[str, str]], ai_plan: dict[str, Any] | None, conservative: bool = False) -> dict[str, str]:
    title=analysis["job"].get("title") or "the target role"; company=analysis["job"].get("company") or "the organization"
    bullets="\n".join(f"- {x['fact']} [{x['fact_id']}]" for x in evidence)
    skills=", ".join(analysis.get("matched_skills",[])) or "See verified experience below"
    if conservative:
        summary=f"Evidence-selected application for {title} at {company}."
        opening=f"Please accept my application for the {title} opportunity at {company}."
        closing="Thank you for your consideration."
    else:
        summary = ai_plan["resume_summary"]["text"] if ai_plan else profile.headline
        opening = ai_plan["cover_letter_opening"]["text"] if ai_plan else f"I am writing to express interest in the {title} opportunity at {company}. The role's priorities align with several areas of my verified career history."
        closing="I would welcome the opportunity to discuss how this background could support your team's goals and priorities."
    contact=_contact_line(profile); contact_row=f"\nCONTACT: {contact}" if contact else ""
    resume=f"{profile.name}\n{profile.headline}{contact_row}\n\nPROFESSIONAL SUMMARY\n{summary}\n\nTARGET\n{title} at {company}\n\nRELEVANT SKILLS\n{skills}\n\nSELECTED VERIFIED EXPERIENCE (REVERSE CHRONOLOGICAL)\n{bullets}\n\nSOURCE NOTE\nThis draft is derived only from the unchanged master resume."
    highlights="\n".join(f"- {x['fact']} [{x['fact_id']}]" for x in evidence[:3])
    cover=f"CONTACT: {contact}\nPOSITION: {title} - {company}\n\nDear Hiring Team,\n\n{opening}\n\nSelected verified experience:\n{highlights}\n\n{closing}\n\nSincerely,\n{profile.name}"
    return {"tailored_resume": resume, "cover_letter": cover}

def tailor(profile: CareerProfile, analysis: dict[str, Any], config: AIConfig | None = None, transport=None) -> dict[str, Any]:
    config = config or AIConfig.from_env(); by_id={f.id:f for f in profile.facts}; ai_plan = None
    if config.ready:
        ai_plan = plan_materials(profile, analysis, config, transport)
        evidence = [{"fact_id": fact_id, "fact": by_id[fact_id].text} for fact_id in ai_plan["selected_fact_ids"]]
    else:
        evidence=analysis.get("evidence",[])[:8]
    evidence=sorted(evidence,key=lambda x:(by_id[x["fact_id"]].start_year or 0),reverse=True)
    claims=[{"fact_id":x["fact_id"],"text":x["fact"]} for x in evidence]; validation=validate_claims(profile,claims)
    if not validation["valid"]: raise ValueError("Tailored content referenced unsupported or altered claims.")
    materials=_documents(profile, analysis, evidence, ai_plan)
    digest=hashlib.sha256(profile.master_resume.encode()).hexdigest(); report={"before_sha256":digest,"after_sha256":hashlib.sha256(profile.master_resume.encode()).hexdigest(),"unchanged":True,"selected_fact_ids":[x["fact_id"] for x in evidence],"selected_claim_count":len(evidence)}
    ai_review = review_materials(profile, analysis, materials, config, transport) if config.ready else None
    initial_review = None; revision_applied = False
    if ai_review and (not ai_review["passed"] or ai_review["unsupported_claims"]):
        initial_review = ai_review
        materials = _documents(profile, analysis, evidence, ai_plan, conservative=True)
        ai_review = review_materials(profile, analysis, materials, config, transport)
        revision_applied = True
        if not ai_review["passed"] or ai_review["unsupported_claims"]:
            details = "; ".join(ai_review["unsupported_claims"][:3]) or "review did not pass"
            raise ValueError(f"AI review rejected both the original and conservative drafts: {details}")
    return {**materials,"used_fact_ids":report["selected_fact_ids"],"validation":validation,"master_resume_unchanged":report["unchanged"],"change_report":report,"ai_generated":bool(ai_plan),"ai_plan":ai_plan,"ai_review":ai_review,"ai_initial_review":initial_review,"ai_revision_applied":revision_applied}
