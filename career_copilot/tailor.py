from __future__ import annotations
import hashlib
from typing import Any
from .models import CareerProfile
from .validator import validate_claims
from .ai import AIConfig, plan_materials, review_materials

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
    title=analysis["job"].get("title") or "the target role"; company=analysis["job"].get("company") or "the organization"
    bullets="\n".join(f"- {x['fact']} [{x['fact_id']}]" for x in evidence)
    skills=", ".join(analysis.get("matched_skills",[])) or "See verified experience below"
    summary = ai_plan["resume_summary"]["text"] if ai_plan else profile.headline
    resume=f"{profile.name}\n{profile.headline}\n\nPROFESSIONAL SUMMARY\n{summary}\n\nTARGET\n{title} at {company}\n\nRELEVANT SKILLS\n{skills}\n\nSELECTED VERIFIED EXPERIENCE (REVERSE CHRONOLOGICAL)\n{bullets}\n\nSOURCE NOTE\nThis draft is derived only from the unchanged master resume."
    highlights="\n".join(f"- {x['fact']} [{x['fact_id']}]" for x in evidence[:3])
    opening = ai_plan["cover_letter_opening"]["text"] if ai_plan else f"I am writing to express interest in the {title} opportunity at {company}. The role's priorities align with several areas of my verified career history."
    cover=f"Dear Hiring Team,\n\n{opening}\n\nHighlights of the experience I would bring include:\n{highlights}\n\nI would welcome the opportunity to discuss how this background could support your team's goals and priorities.\n\nSincerely,\n{profile.name}"
    digest=hashlib.sha256(profile.master_resume.encode()).hexdigest(); report={"before_sha256":digest,"after_sha256":hashlib.sha256(profile.master_resume.encode()).hexdigest(),"unchanged":True,"selected_fact_ids":[x["fact_id"] for x in evidence],"selected_claim_count":len(evidence)}
    materials={"tailored_resume":resume,"cover_letter":cover}
    ai_review = review_materials(profile, analysis, materials, config, transport) if config.ready else None
    if ai_review and (not ai_review["passed"] or ai_review["unsupported_claims"]):
        raise ValueError("AI review rejected the draft because it may contain unsupported claims.")
    return {**materials,"used_fact_ids":report["selected_fact_ids"],"validation":validation,"master_resume_unchanged":report["unchanged"],"change_report":report,"ai_generated":bool(ai_plan),"ai_plan":ai_plan,"ai_review":ai_review}
