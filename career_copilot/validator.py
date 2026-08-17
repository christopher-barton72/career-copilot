from __future__ import annotations

from typing import Any

from .models import CareerProfile


def validate_fact_ids(profile: CareerProfile, used_fact_ids: list[str]) -> dict[str, Any]:
    valid = {fact.id for fact in profile.facts}
    unknown = sorted(set(used_fact_ids) - valid)
    return {"valid": not unknown, "unknown_fact_ids": unknown, "checked_fact_count": len(set(used_fact_ids)), "rule": "Every tailored claim must cite a verified career-truth fact ID."}

def validate_claims(profile: CareerProfile, claims: list[dict[str, str]]) -> dict[str, Any]:
    facts={f.id:f.text for f in profile.facts}; problems=[]
    for claim in claims:
        fid=claim.get("fact_id","")
        if fid not in facts: problems.append({"fact_id":fid,"reason":"unknown_fact_id"})
        elif claim.get("text","").strip()!=facts[fid]: problems.append({"fact_id":fid,"reason":"claim_does_not_match_source"})
    return {"valid":not problems,"problems":problems,"checked_claim_count":len(claims),"checked_fact_count":len(claims),"rule":"Every generated claim must exactly match its cited master-resume fact."}

