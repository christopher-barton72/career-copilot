from __future__ import annotations
import hashlib
from typing import Any
from .models import CareerProfile
from .validator import validate_claims

def tailor(profile: CareerProfile, analysis: dict[str, Any]) -> dict[str, Any]:
    evidence=analysis.get("evidence",[])[:8]; by_id={f.id:f for f in profile.facts}
    evidence=sorted(evidence,key=lambda x:(by_id[x["fact_id"]].start_year or 0),reverse=True)
    claims=[{"fact_id":x["fact_id"],"text":x["fact"]} for x in evidence]; validation=validate_claims(profile,claims)
    if not validation["valid"]: raise ValueError("Tailored content referenced unsupported or altered claims.")
    title=analysis["job"].get("title") or "the target role"; company=analysis["job"].get("company") or "the organization"
    bullets="\n".join(f"- {x['fact']} [{x['fact_id']}]" for x in evidence)
    skills=", ".join(analysis.get("matched_skills",[])) or "See verified experience below"
    resume=f"{profile.name}\n{profile.headline}\n\nTARGET\n{title} at {company}\n\nRELEVANT SKILLS\n{skills}\n\nSELECTED VERIFIED EXPERIENCE (REVERSE CHRONOLOGICAL)\n{bullets}\n\nSOURCE NOTE\nThis draft is derived only from the unchanged master resume."
    highlights="\n".join(f"- {x['fact']} [{x['fact_id']}]" for x in evidence[:3])
    cover=f"Dear Hiring Team,\n\nI am writing to express interest in the {title} opportunity at {company}. The role's priorities align with several areas of my verified career history.\n\nHighlights of the experience I would bring include:\n{highlights}\n\nI would welcome the opportunity to discuss how this background could support your team's goals and priorities.\n\nSincerely,\n{profile.name}"
    digest=hashlib.sha256(profile.master_resume.encode()).hexdigest(); report={"before_sha256":digest,"after_sha256":hashlib.sha256(profile.master_resume.encode()).hexdigest(),"unchanged":True,"selected_fact_ids":[x["fact_id"] for x in evidence],"selected_claim_count":len(evidence)}
    return {"tailored_resume":resume,"cover_letter":cover,"used_fact_ids":report["selected_fact_ids"],"validation":validation,"master_resume_unchanged":report["unchanged"],"change_report":report}

