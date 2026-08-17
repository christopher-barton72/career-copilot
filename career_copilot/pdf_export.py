from __future__ import annotations
import textwrap
from io import BytesIO

def render_pdf(title: str, content: str) -> bytes:
    lines=[title,""]
    for paragraph in content.splitlines(): lines.extend(textwrap.wrap(paragraph,width=92) or [""])
    pages=[lines[i:i+48] for i in range(0,len(lines),48)] or [[]]; objects=[]
    objects += [b"<< /Type /Catalog /Pages 2 0 R >>", f"<< /Type /Pages /Kids [{' '.join(f'{3+i*2} 0 R' for i in range(len(pages)))}] /Count {len(pages)} >>".encode()]
    font_id=3+len(pages)*2
    for i,page in enumerate(pages):
        pid=3+i*2; sid=pid+1
        objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 {font_id} 0 R >> >> /Contents {sid} 0 R >>".encode())
        commands=["BT","/F1 10 Tf","54 738 Td","14 TL"]
        for line in page:
            value=line.encode("latin-1","replace").decode("latin-1").replace("\\","\\\\").replace("(","\\(").replace(")","\\)")
            commands.append(f"({value}) Tj T*")
        stream="\n".join(commands+["ET"]).encode("latin-1"); objects.append(b"<< /Length "+str(len(stream)).encode()+b" >>\nstream\n"+stream+b"\nendstream")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    out=BytesIO(); out.write(b"%PDF-1.4\n"); offsets=[]
    for n,obj in enumerate(objects,1): offsets.append(out.tell()); out.write(f"{n} 0 obj\n".encode()+obj+b"\nendobj\n")
    xref=out.tell(); out.write(f"xref\n0 {len(objects)+1}\n0000000000 65535 f \n".encode())
    for offset in offsets: out.write(f"{offset:010d} 00000 n \n".encode())
    out.write(f"trailer << /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()); return out.getvalue()

