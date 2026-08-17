from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class CareerFact:
    id: str
    text: str
    kind: str
    confidence: str = "verified"
    source: str = "master_resume"
    section: str = ""
    employer: str = ""
    role: str = ""
    start_year: int | None = None
    end_year: int | None = None


@dataclass
class Preferences:
    target_roles: list[str] = field(default_factory=list)
    target_skills: list[str] = field(default_factory=list)
    location: str = ""
    work_modes: list[str] = field(default_factory=list)
    minimum_salary: int | None = None
    target_salary: int | None = None
    travel_max_percent: int | None = None
    employment_types: list[str] = field(default_factory=list)
    dealbreakers: list[str] = field(default_factory=list)


@dataclass
class CareerProfile:
    name: str
    headline: str
    master_resume: str
    preferences: Preferences
    facts: list[CareerFact]
    created_at: str
    updated_at: str
    schema_version: int = 1

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def profile_from_dict(data: dict[str, Any]) -> CareerProfile:
    return CareerProfile(
        name=data.get("name", ""),
        headline=data.get("headline", ""),
        master_resume=data.get("master_resume", ""),
        preferences=Preferences(**data.get("preferences", {})),
        facts=[CareerFact(**item) for item in data.get("facts", [])],
        created_at=data.get("created_at", ""),
        updated_at=data.get("updated_at", ""),
        schema_version=data.get("schema_version", 1),
    )
