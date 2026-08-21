from __future__ import annotations

import re
from io import BytesIO

PAGE_WIDTH, PAGE_HEIGHT = 612, 792
LEFT, RIGHT, TOP, BOTTOM = 50, 50, 46, 76
INK = (0.09, 0.12, 0.16)
NAVY = (0.08, 0.31, 0.49)
MUTED = (0.35, 0.40, 0.48)
RULE = (0.66, 0.76, 0.85)
PANEL = (0.93, 0.95, 0.97)


def _clean(text: str) -> str:
    text = re.sub(r"\s*\[fact_[0-9a-f]+\]", "", text, flags=re.I)
    return text.replace("–", "-").replace("—", "-").replace("’", "'").replace("•", "-")


def _escape(text: str) -> str:
    return _clean(text).encode("latin-1", "replace").decode("latin-1").replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _width(text: str, size: float, bold: bool = False) -> float:
    return len(_clean(text)) * size * (0.55 if bold else 0.50)


def _wrap(text: str, size: float, width: float, bold: bool = False) -> list[str]:
    words = _clean(text).split()
    if not words:
        return [""]
    lines: list[str] = []; current = words[0]
    for word in words[1:]:
        candidate = current + " " + word
        if _width(candidate, size, bold) <= width:
            current = candidate
        else:
            lines.append(current); current = word
    lines.append(current)
    return lines


def _text(command: list[str], x: float, y: float, value: str, size: float = 10, bold: bool = False, italic: bool = False, color=INK, center: bool = False) -> None:
    font = "/F3" if italic else "/F2" if bold else "/F1"
    if center:
        x = max(LEFT, (PAGE_WIDTH - _width(value, size, bold)) / 2)
    command.extend(["BT", f"{color[0]} {color[1]} {color[2]} rg", f"{font} {size} Tf", f"1 0 0 1 {x:.1f} {y:.1f} Tm", f"({_escape(value)}) Tj", "ET"])


def _line(command: list[str], x1: float, y: float, x2: float, color=RULE, width: float = 0.65) -> None:
    command.extend([f"{color[0]} {color[1]} {color[2]} RG", f"{width} w", f"{x1:.1f} {y:.1f} m {x2:.1f} {y:.1f} l S"])


def _rect(command: list[str], x: float, y: float, width: float, height: float, color=PANEL) -> None:
    command.extend([f"{color[0]} {color[1]} {color[2]} rg", f"{x:.1f} {y:.1f} {width:.1f} {height:.1f} re f"])


def _blocks(title: str, content: str, kind: str) -> list[dict]:
    lines = [_clean(line.strip()) for line in content.splitlines()]
    blocks: list[dict] = []
    if kind == "resume":
        blocks.extend([{"type": "name", "text": lines[0] if lines else title}, {"type": "headline", "text": lines[1] if len(lines) > 1 else ""}])
        pending = ""
        for line in lines[2:]:
            if not line: blocks.append({"type": "space"}); continue
            if line.startswith("CONTACT: "): blocks.append({"type": "contact", "text": line[9:]}); continue
            if line == "SOURCE NOTE" or line.startswith("This draft is derived"): continue
            if line.isupper() and len(line) < 70:
                pending = line.replace(" (REVERSE CHRONOLOGICAL)", "")
                blocks.append({"type": "section", "text": pending}); continue
            if line.startswith("- "): blocks.append({"type": "bullet", "text": line[2:]}); continue
            block_type = {"PROFESSIONAL SUMMARY": "profile", "TARGET": "target", "RELEVANT SKILLS": "skillbox"}.get(pending, "body")
            blocks.append({"type": block_type, "text": line}); pending = ""
    else:
        signature_name = next((line for line in reversed(lines) if line and not line.startswith("CONTACT:")), title)
        blocks.append({"type": "name", "text": signature_name})
        for line in lines:
            if not line: blocks.append({"type": "space"})
            elif line.startswith("CONTACT: "): blocks.append({"type": "contact", "text": line[9:]})
            elif line.startswith("POSITION: "): blocks.append({"type": "letter_title", "text": line[10:]})
            elif line.startswith("Dear ") or line == "Sincerely,": blocks.append({"type": "salutation", "text": line})
            elif line.startswith("- "): blocks.append({"type": "bullet", "text": line[2:]})
            elif blocks and blocks[-1].get("text") == "Sincerely,": blocks.append({"type": "signature", "text": line})
            elif line != signature_name: blocks.append({"type": "paragraph", "text": line})
    return blocks


def render_pdf(title: str, content: str, kind: str = "resume") -> bytes:
    """Render a branded, ATS-readable resume or cover-letter PDF."""
    if kind not in {"resume", "cover_letter"}: raise ValueError("PDF kind must be resume or cover_letter.")
    pages: list[list[str]] = []; commands: list[str] = []; y = PAGE_HEIGHT - TOP
    body_width = PAGE_WIDTH - LEFT - RIGHT

    def new_page(continuation: bool = False) -> None:
        nonlocal commands, y
        if commands: pages.append(commands)
        commands = []; y = PAGE_HEIGHT - TOP
        if continuation and kind == "resume":
            _text(commands, LEFT, y, "PROFESSIONAL EXPERIENCE - CONTINUED", 12, True, color=NAVY)
            _line(commands, LEFT, y - 4, PAGE_WIDTH - RIGHT); y -= 24

    def ensure(height: float) -> None:
        if y - height < BOTTOM + 20: new_page(True)

    new_page()
    for block in _blocks(title, content, kind):
        block_type, value = block["type"], block.get("text", "")
        if block_type == "space": y -= 5; continue
        if block_type == "name":
            ensure(32); _text(commands, LEFT, y, value.upper(), 22, True, color=NAVY, center=True); y -= 25
        elif block_type == "headline":
            if value: _text(commands, LEFT, y, value, 10.5, True, center=True); y -= 15
        elif block_type == "contact":
            wrapped = _wrap(value, 9, body_width)
            for line in wrapped: _text(commands, LEFT, y, line, 9, center=True); y -= 11
            _line(commands, LEFT + 16, y - 2, PAGE_WIDTH - RIGHT - 16, NAVY, 0.9); y -= 17
        elif block_type == "section":
            ensure(25); _text(commands, LEFT, y, value, 12.5, True, color=NAVY); _line(commands, LEFT, y - 4, PAGE_WIDTH - RIGHT); y -= 19
        elif block_type == "letter_title":
            ensure(38); _line(commands, LEFT + 16, y + 10, PAGE_WIDTH - RIGHT - 16, NAVY, 0.9)
            _text(commands, LEFT, y - 7, value.upper(), 12, True, color=NAVY, center=True)
            _line(commands, LEFT + 16, y - 16, PAGE_WIDTH - RIGHT - 16); y -= 38
        elif block_type == "target":
            wrapped = _wrap(value, 10, body_width - 28, True); height = len(wrapped) * 13 + 14; ensure(height + 4)
            _rect(commands, LEFT, y - height + 7, body_width, height)
            for index, line in enumerate(wrapped): _text(commands, LEFT + 14, y - 5 - index * 13, line, 10, True, color=NAVY, center=True)
            y -= height + 5
        elif block_type == "skillbox":
            wrapped = _wrap(value, 9.4, body_width - 24); height = len(wrapped) * 12 + 14; ensure(height + 4)
            _rect(commands, LEFT, y - height + 7, body_width, height)
            for index, line in enumerate(wrapped): _text(commands, LEFT + 12, y - 4 - index * 12, line, 9.4)
            y -= height + 5
        elif block_type == "bullet":
            wrapped = _wrap(value, 9.4, body_width - 20); ensure(len(wrapped) * 12 + 5)
            _text(commands, LEFT + 4, y, "-", 10, True, color=NAVY)
            for index, line in enumerate(wrapped): _text(commands, LEFT + 18, y - index * 12, line, 9.4)
            y -= len(wrapped) * 12 + 4
        elif block_type in {"body", "profile", "paragraph"}:
            size = 9.6 if kind == "resume" else 10.5; leading = 12.5 if kind == "resume" else 15
            wrapped = _wrap(value, size, body_width); ensure(len(wrapped) * leading + 7)
            for index, line in enumerate(wrapped): _text(commands, LEFT, y - index * leading, line, size)
            y -= len(wrapped) * leading + (11 if block_type == "paragraph" else 5)
        elif block_type == "salutation":
            ensure(25); _text(commands, LEFT, y, value, 10.5); y -= 23
        elif block_type == "signature":
            ensure(24); _text(commands, LEFT, y, value, 10.5); y -= 18

    pages.append(commands)
    for page_number, page in enumerate(pages, 1): _text(page, PAGE_WIDTH - RIGHT - 32, 24, f"Page {page_number}", 8, color=MUTED)

    objects: list[bytes] = [b"<< /Type /Catalog /Pages 2 0 R >>"]
    kids = " ".join(f"{3 + index * 2} 0 R" for index in range(len(pages))); objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode())
    font_regular, font_bold, font_italic = 3 + len(pages) * 2, 4 + len(pages) * 2, 5 + len(pages) * 2
    for index, page in enumerate(pages):
        stream_id = 4 + index * 2
        objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] /Resources << /Font << /F1 {font_regular} 0 R /F2 {font_bold} 0 R /F3 {font_italic} 0 R >> >> /Contents {stream_id} 0 R >>".encode())
        stream = "\n".join(page).encode("latin-1"); objects.append(b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream")
    objects.extend([b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>", b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>", b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Oblique /Encoding /WinAnsiEncoding >>"])
    output = BytesIO(); output.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"); offsets = []
    for number, obj in enumerate(objects, 1): offsets.append(output.tell()); output.write(f"{number} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = output.tell(); output.write(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for offset in offsets: output.write(f"{offset:010d} 00000 n \n".encode())
    output.write(f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()); return output.getvalue()
