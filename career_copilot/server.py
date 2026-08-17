from __future__ import annotations
import json, os, re
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from .analyzer import analyze
from .profile import build_profile
from .resume_pdf import build_resume_pdf
from .storage import Storage
from .tailor import tailor
ROOT=Path(__file__).resolve().parent.parent; STORE=Storage(ROOT/"data"); WEB=ROOT/"web"
class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs): super().__init__(*args,directory=str(WEB),**kwargs)
    def _json(self,status,value):
        body=json.dumps(value,ensure_ascii=False).encode(); self.send_response(status); self.send_header("Content-Type","application/json; charset=utf-8"); self.send_header("Content-Length",str(len(body))); self.send_header("Cache-Control","no-store"); self.end_headers(); self.wfile.write(body)
    def _payload(self):
        length=int(self.headers.get("Content-Length","0"));
        if length>2_000_000: raise ValueError("Request is too large.")
        return json.loads(self.rfile.read(length) or b"{}")
    def do_GET(self):
        path=urlparse(self.path).path
        if path=="/api/profile":
            p=STORE.load_profile(); self._json(200,{"profile":p.to_dict() if p else None})
        elif path=="/api/analysis": self._json(200,{"analysis":STORE.load_analysis()})
        elif path=="/api/resume.pdf":
            p,a=STORE.load_profile(),STORE.load_analysis()
            if not p or not a: return self._json(400,{"error":"Save a profile and analyze a job first."})
            body=build_resume_pdf(tailor(p,a)); job=a.get("job",{}); stem=re.sub(r"[^A-Za-z0-9]+","-",f"{p.name}-{job.get('company','')}-{job.get('title','')}").strip("-") or "tailored-resume"
            self.send_response(200); self.send_header("Content-Type","application/pdf"); self.send_header("Content-Disposition",f'attachment; filename="{stem}.pdf"'); self.send_header("Content-Length",str(len(body))); self.send_header("Cache-Control","no-store"); self.end_headers(); self.wfile.write(body)
        elif path=="/api/health": self._json(200,{"status":"ok","version":"0.2.0"})
        else: super().do_GET()
    def do_POST(self):
        try:
            payload=self._payload(); path=urlparse(self.path).path
            if path=="/api/profile":
                p=build_profile(payload,STORE.load_profile()); STORE.save_profile(p); self._json(200,{"profile":p.to_dict()})
            elif path=="/api/analyze":
                p=STORE.load_profile();
                if not p: raise ValueError("Create a career profile first.")
                a=analyze(p,payload); STORE.save_analysis(a); self._json(200,{"analysis":a})
            elif path=="/api/tailor":
                p,a=STORE.load_profile(),STORE.load_analysis();
                if not p or not a: raise ValueError("Save a profile and analyze a job first.")
                self._json(200,{"materials":tailor(p,a)})
            else: self._json(404,{"error":"Not found"})
        except (ValueError,TypeError,json.JSONDecodeError) as exc: self._json(400,{"error":str(exc)})
        except Exception: self._json(500,{"error":"Unexpected local server error."})
    def log_message(self,fmt,*args): print(f"[career-copilot] {fmt%args}")
def run():
    port=int(os.environ.get("CAREER_COPILOT_PORT","8765")); server=ThreadingHTTPServer(("127.0.0.1",port),Handler); print(f"Career Copilot running at http://127.0.0.1:{port}")
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()

