from __future__ import annotations

import re
from io import BytesIO

PAGE_WIDTH, PAGE_HEIGHT = 612, 792
LEFT, RIGHT, TOP, BOTTOM = 54, 54, 58, 54
INK = (0.10, 0.14, 0.13)
MUTED = (0.34, 0.40, 0.38)
ACCENT = (0.06, 0.36, 0.28)
LIGHT = (0.91, 0.95, 0.93)


def _clean(text: str) -> str:
    text = re.sub(r"\s*\[fact_[0-9a-f]+\]", "", text, flags=re.I)
    return text.replace("–", "-").replace("—", "-").replace("’", "'")


def _escape(text: str) -> str:
    return _clean(text).encode("latin-1", "replace").decode("latin-1").replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _wrap(text: str, size: float, width: float) -> list[str]:
    words = _clean(text).split()
    if not words:
        return [""]
    limit = max(12, int(width / (size * 0.53)))
    lines, current = [], words[0]
    for word in words[1:]:
        if len(current) + len(word) + 1 <= limit:
            current += " " + word
        else:
            lines.append(current); current = word
    lines.append(current)
    return lines


def _text(command: list[str], x: float, y: float, value: str, size: float = 10, bold: bool = False, color=INK) -> None:
    font = "/F2" if bold else "/F1"
    command.extend(["BT", f"{color[0]} {color[1]} {color[2]} rg", f"{font} {size} Tf", f"1 0 0 1 {x:.1f} {y:.1f} Tm", f"({_escape(value)}) Tj", "ET"])


def _line(command: list[str], x1: float, y: float, x2: float, color=ACCENT, width: float = 0.8) -> None:
    command.extend([f"{color[0]} {color[1]} {color[2]} RG", f"{width} w", f"{x1:.1f} {y:.1f} m {x2:.1f} {y:.1f} l S"])


def _blocks(title: str, content: str, kind: str) -> list[dict]:
    lines = [_clean(line.strip()) for line in content.splitlines()]
    blocks: list[dict] = []
    if kind == "resume":
        blocks.extend([{"type": "name", "text": lines[0] if lines else title}, {"type": "headline", "text": lines[1] if len(lines) > 1 else ""}])
        for line in lines[2:]:
            if not line: blocks.append({"type": "space"})
            elif line == "SOURCE NOTE": continue
            elif line.isupper() and len(line) < 70: blocks.append({"type": "section", "text": line.replace(" (REVERSE CHRONOLOGICAL)", "")})
            elif line.startswith("- "): blocks.append({"type": "bullet", "text": line[2:]})
            elif not line.startswith("This draft is derived"): blocks.append({"type": "body", "text": line})
    else:
        signature_name = next((line for line in reversed(lines) if line), title)
        blocks.extend([{"type": "name", "text": signature_name}, {"type": "headline", "text": "Cover Letter"}])
        for line in lines:
            if not line: blocks.append({"type": "space"})
            elif line.startswith("Dear ") or line == "Sincerely,": blocks.append({"type": "salutation", "text": line})
            elif line.startswith("- "): blocks.append({"type": "bullet", "text": line[2:]})
            elif blocks and blocks[-1].get("text") == "Sincerely,": blocks.append({"type": "signature", "text": line})
            else: blocks.append({"type": "paragraph", "text": line})
    return blocks


def render_pdf(title: str, content: str, kind: str = "resume") -> bytes:
    """Render a polished, ATS-readable resume or cover letter PDF."""
    if kind not in {"resume", "cover_letter"}: raise ValueError("PDF kind must be resume or cover_letter.")
    pages: list[list[str]] = []; commands: list[str] = []; y = PAGE_HEIGHT - TOP
    body_width = PAGE_WIDTH - LEFT - RIGHT

    def new_page() -> None:
        nonlocal commands, y
        if commands: pages.append(commands)
        commands = [f"{LIGHT[0]} {LIGHT[1]} {LIGHT[2]} rg", f"0 {PAGE_HEIGHT - 12} {PAGE_WIDTH} 12 re f"]
        y = PAGE_HEIGHT - TOP

    def ensure(height: float) -> None:
        if y - height < BOTTOM + 18: new_page()

    new_page()
    for block in _blocks(title, content, kind):
        block_type, value = block["type"], block.get("text", "")
        if block_type == "space": y -= 5; continue
        if block_type == "name":
            ensure(36); _text(commands, LEFT, y, value, 22, True); y -= 27
        elif block_type == "headline":
            ensure(24); _text(commands, LEFT, y, value, 10.5, True, ACCENT); y -= 15; _line(commands, LEFT, y, PAGE_WIDTH - RIGHT); y -= 18
        elif block_type in {"section", "letter_title"}:
            ensure(30); _text(commands, LEFT, y, value, 20 if block_type == "letter_title" else 10, True, INK if block_type == "letter_title" else ACCENT); y -= 14 if block_type == "letter_title" else 7
            _line(commands, LEFT, y, PAGE_WIDTH - RIGHT, ACCENT, 0.65); y -= 15
        elif block_type == "bullet":
            wrapped = _wrap(value, 9.5, body_width - 18); ensure(len(wrapped) * 13 + 5); _text(commands, LEFT + 2, y, "-", 10, True, ACCENT)
            for index, line in enumerate(wrapped): _text(commands, LEFT + 16, y - index * 13, line, 9.5)
            y -= len(wrapped) * 13 + 6
        elif block_type in {"body", "paragraph"}:
            wrapped = _wrap(value, 10, body_width); ensure(len(wrapped) * 14 + 7)
            for index, line in enumerate(wrapped): _text(commands, LEFT, y - index * 14, line, 10)
            y -= len(wrapped) * 14 + (10 if block_type == "paragraph" else 5)
        elif block_type == "salutation":
            ensure(25); _text(commands, LEFT, y, value, 10.5, value == "Sincerely,"); y -= 22
        elif block_type == "signature":
            ensure(24); _text(commands, LEFT, y, value, 11, True, ACCENT); y -= 18

    pages.append(commands)
    for page_number, page in enumerate(pages, 1):
        _line(page, LEFT, 38, PAGE_WIDTH - RIGHT, LIGHT, 0.5)
        _text(page, LEFT, 24, "Career Copilot - evidence-validated draft", 7.5, False, MUTED)
        _text(page, PAGE_WIDTH - RIGHT - 38, 24, f"Page {page_number} of {len(pages)}", 7.5, False, MUTED)

    objects: list[bytes] = [b"<< /Type /Catalog /Pages 2 0 R >>"]
    kids = " ".join(f"{3 + index * 2} 0 R" for index in range(len(pages))); objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode())
    font_regular, font_bold = 3 + len(pages) * 2, 4 + len(pages) * 2
    for index, page in enumerate(pages):
        page_id, stream_id = 3 + index * 2, 4 + index * 2
        objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] /Resources << /Font << /F1 {font_regular} 0 R /F2 {font_bold} 0 R >> >> /Contents {stream_id} 0 R >>".encode())
        stream = "\n".join(page).encode("latin-1"); objects.append(b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream")
    objects.extend([b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>", b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>"])
    output = BytesIO(); output.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"); offsets = []
    for number, obj in enumerate(objects, 1): offsets.append(output.tell()); output.write(f"{number} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = output.tell(); output.write(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for offset in offsets: output.write(f"{offset:010d} 00000 n \n".encode())
    output.write(f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()); return output.getvalue()
