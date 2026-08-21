from __future__ import annotations
import hashlib, re
from datetime import datetime, timezone
from .models import CareerFact, CareerProfile, Preferences

SKILL_TERMS = {"aws","azure","gcp","python","java","javascript","typescript","sql","kubernetes","docker","terraform","vmware","linux","windows","netapp","dell","pure","vast","nist","zero trust","s3","security","storage","architecture","leadership","agile","scrum","devops","networking"}
SECTIONS = {"PROFESSIONAL EXPERIENCE","EXPERIENCE","EDUCATION","EDUCATION & PROFESSIONAL DEVELOPMENT","CREDENTIALS","SKILLS","EXECUTIVE EXPERTISE","BUSINESS IMPACT","LEADERSHIP PHILOSOPHY"}
DATES = re.compile(r"(?P<start>(?:19|20)\d{2})\s*[-–—]\s*(?P<end>(?:19|20)\d{2}|present)", re.I)

def _fact_id(text: str) -> str:
    return "fact_" + hashlib.sha256(text.lower().strip().encode()).hexdigest()[:10]

def logical_lines(resume: str) -> list[str]:
    raw = [re.sub(r"^[\s•*\-–—]+", "", x).strip() for x in resume.splitlines()]
    out: list[str] = []
    for line in raw:
        if not line or re.fullmatch(r"page\s+\d+", line, re.I): continue
        boundary = line.upper() in SECTIONS or bool(DATES.search(line))
        if out and not boundary and (line[:1].islower() or (not re.search(r"[.!?:]$", out[-1]) and len(out[-1]) > 35)):
            out[-1] += " " + line
        else: out.append(line)
    return [re.sub(r"\s+", " ", x) for x in out]

def extract_facts(resume: str) -> list[CareerFact]:
    facts=[]; seen=set(); section=employer=role=""; start=end=None
    for line in logical_lines(resume):
        if line.upper() in SECTIONS:
            section=line.upper()
            if section not in {"PROFESSIONAL EXPERIENCE", "EXPERIENCE"}:
                employer=role=""; start=end=None
            continue
        match=DATES.search(line)
        if match:
            role=line; start=int(match.group("start")); end=None if match.group("end").lower()=="present" else int(match.group("end"))
        elif section in {"PROFESSIONAL EXPERIENCE","EXPERIENCE"} and len(line)<80 and not re.search(r"[.!]$",line):
            employer=line; role=""; start=end=None
        if len(line)<12 or len(line)>700 or line.lower() in seen: continue
        seen.add(line.lower()); key=line.lower(); kind="experience"
        if match: kind="employment"
        elif any(term in key for term in SKILL_TERMS): kind="skill_evidence"
        elif re.search(r"\b(certif|degree|bachelor|master|university|college)\b",key): kind="credential"
        facts.append(CareerFact(_fact_id(line),line,kind,section=section,employer=employer,role=role,start_year=start,end_year=end))
    return facts[:250]

def build_profile(payload: dict, existing: CareerProfile | None = None) -> CareerProfile:
    resume=payload.get("master_resume","").strip()
    if len(resume)<80: raise ValueError("Master resume must contain at least 80 characters.")
    now=datetime.now(timezone.utc).isoformat(); prefs=Preferences(**payload.get("preferences",{}))
    return CareerProfile(payload.get("name","").strip(),payload.get("headline","").strip(),resume,prefs,extract_facts(resume),existing.created_at if existing else now,now)
