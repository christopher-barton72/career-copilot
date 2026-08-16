from __future__ import annotations

from typing import Any

from .models import CareerProfile


def validate_fact_ids(profile: CareerProfile, used_fact_ids: list[str]) -> dict[str, Any]:
    valid = {fact.id for fact in profile.facts}
    unknown = sorted(set(used_fact_ids) - valid)
    return {"valid": not unknown, "unknown_fact_ids": unknown, "checked_fact_count": len(set(used_fact_ids)), "rule": "Every tailored claim must cite a verified career-truth fact ID."}
