from __future__ import annotations

import re
from textwrap import wrap
from typing import Any


def _ascii(value: str) -> str:
    value = value.replace("â€“", "-").replace("â€”", "-").replace("â€¢", "-")
    return value.encode("latin-1", "replace").decode("latin-1").replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _lines(text: str, width: int) -> list[str]:
    return wrap(re.sub(r"\s+", " ", text).strip(), width=width, break_long_words=False) or [""]


def build_resume_pdf(materials: dict[str, Any]) -> bytes:
    resume = materials["resume"]
    pages, commands, y = [], [], 748

    def new_page():
        nonlocal commands, y
        if commands: pages.append(commands)
        commands, y = [], 748

    def text(value, x=54, size=9, bold=False, color="0.13 0.19 0.27", leading=None):
        nonlocal y
        leading = leading or size * 1.35
        for line in _lines(value, max(25, int((504 / (size * .52))))):
            if y < 58: new_page()
            commands.append(f"BT /{'F2' if bold else 'F1'} {size} Tf {color} rg {x} {y:.1f} Td ({_ascii(line)}) Tj ET")
            y -= leading

    def section(title):
        nonlocal y
        if y < 92: new_page()
        y -= 7; text(title.upper(), size=9.5, bold=True, color="0.09 0.22 0.34", leading=13)
        commands.append(f"0.17 0.45 0.50 RG 0.8 w 54 {y+8:.1f} m 558 {y+8:.1f} l S")
        y -= 3

    text(resume["name"], size=22, bold=True, color="0.09 0.22 0.34", leading=26)
    text(resume.get("headline") or resume["target"]["title"], size=10.5, bold=True, color="0.17 0.45 0.50", leading=16)
    section("Executive Profile"); text(resume["summary"], size=9, leading=12)
    if resume["competencies"]:
        section("Core Competencies"); text(" | ".join(resume["competencies"]), size=8.8, bold=True, leading=12)
    section("Professional Experience")
    for item in resume["employment"] + resume["experience"]:
        if y < 82: new_page()
        text("- " + item["text"], x=60, size=8.7, leading=11.5); y -= 2
    if resume["credentials"]:
        section("Education & Credentials")
        for item in resume["credentials"]: text(item["text"], size=8.8, leading=12)
    pages.append(commands)

    objects = []
    def add(data): objects.append(data); return len(objects)
    font1=add("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    font2=add("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>")
    page_ids=[]
    contents=[]
    for page in pages:
        stream="\n".join(page).encode("latin-1","replace")
        contents.append(add(b"<< /Length %d >>\nstream\n"%len(stream)+stream+b"\nendstream"))
        page_ids.append(add("PENDING"))
    pages_id=len(objects)+1; add("PAGES_PENDING")
    catalog_id=len(objects)+1; add(f"<< /Type /Catalog /Pages {pages_id} 0 R >>")
    for pid,cid in zip(page_ids,contents): objects[pid-1]=f"<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 {font1} 0 R /F2 {font2} 0 R >> >> /Contents {cid} 0 R >>"
    objects[pages_id-1]=f"<< /Type /Pages /Kids [{' '.join(f'{x} 0 R' for x in page_ids)}] /Count {len(page_ids)} >>"
    out=bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"); offsets=[0]
    for i,obj in enumerate(objects,1):
        offsets.append(len(out)); out.extend(f"{i} 0 obj\n".encode()); out.extend(obj if isinstance(obj,bytes) else obj.encode()); out.extend(b"\nendobj\n")
    xref=len(out); out.extend(f"xref\n0 {len(objects)+1}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]: out.extend(f"{offset:010d} 00000 n \n".encode())
    out.extend(f"trailer << /Size {len(objects)+1} /Root {catalog_id} 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return bytes(out)

