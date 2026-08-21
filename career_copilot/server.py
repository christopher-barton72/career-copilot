from __future__ import annotations

import json
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .analyzer import analyze
from .profile import build_profile
from .storage import Storage
from .tailor import tailor
from .pdf_export import render_pdf
from .ai import AIConfig, AIError, assess_fit, status as ai_status


ROOT = Path(__file__).resolve().parent.parent
STORE = Storage(ROOT / "data")
WEB = ROOT / "web"


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB), **kwargs)

    def _json(self, status: int, value: dict) -> None:
        body = json.dumps(value, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(body)

    def _payload(self) -> dict:
        if self.headers.get("Content-Type", "").split(";")[0].strip().lower() != "application/json":
            raise ValueError("Content-Type must be application/json.")
        length = int(self.headers.get("Content-Length", "0"))
        if length > 2_000_000:
            raise ValueError("Request is too large.")
        return json.loads(self.rfile.read(length) or b"{}")

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/profile":
            profile = STORE.load_profile()
            self._json(200, {"profile": profile.to_dict() if profile else None})
        elif path == "/api/analysis":
            self._json(200, {"analysis": STORE.load_analysis()})
        elif path == "/api/health":
            self._json(200, {"status": "ok", "version": "0.2.0", "ai": ai_status()})
        else:
            super().do_GET()

    def do_POST(self) -> None:
        try:
            origin=self.headers.get("Origin")
            if origin and origin not in {f"http://127.0.0.1:{self.server.server_port}",f"http://localhost:{self.server.server_port}"}:
                self._json(403,{"error":"Cross-origin requests are not allowed."}); return
            payload = self._payload()
            path = urlparse(self.path).path
            if path == "/api/profile":
                profile = build_profile(payload, STORE.load_profile())
                STORE.save_profile(profile)
                self._json(200, {"profile": profile.to_dict()})
            elif path == "/api/analyze":
                profile = STORE.load_profile()
                if not profile:
                    raise ValueError("Create a career profile first.")
                result = analyze(profile, payload)
                config = AIConfig.from_env()
                if config.ready:
                    try: result["ai_assessment"] = assess_fit(profile, result, config)
                    except AIError as exc: result["ai_error"] = str(exc)
                STORE.save_analysis(result)
                self._json(200, {"analysis": result})
            elif path == "/api/tailor":
                profile, result = STORE.load_profile(), STORE.load_analysis()
                if not profile or not result:
                    raise ValueError("Save a profile and analyze a job first.")
                materials = tailor(profile, result); STORE.save_materials(materials)
                self._json(200, {"materials": materials})
            elif path == "/api/export":
                profile, result = STORE.load_profile(), STORE.load_analysis()
                if not profile or not result: raise ValueError("Save a profile and analyze a job first.")
                materials=STORE.load_materials()
                if not materials: raise ValueError("Generate application materials before exporting.")
                kind=payload.get("kind","resume")
                if kind not in {"resume","cover_letter"}: raise ValueError("Export kind must be resume or cover_letter.")
                content=materials["tailored_resume" if kind=="resume" else "cover_letter"]
                body=render_pdf("Tailored Resume" if kind=="resume" else "Cover Letter",content,kind)
                self.send_response(200); self.send_header("Content-Type","application/pdf"); self.send_header("Content-Disposition",f'attachment; filename="{kind}.pdf"'); self.send_header("Content-Length",str(len(body))); self.send_header("Cache-Control","no-store"); self.send_header("X-Content-Type-Options","nosniff"); self.end_headers(); self.wfile.write(body)
            else:
                self._json(404, {"error": "Not found"})
        except (ValueError, TypeError, json.JSONDecodeError, AIError) as exc:
            self._json(400, {"error": str(exc)})
        except Exception:
            self._json(500, {"error": "Unexpected local server error."})

    def log_message(self, fmt: str, *args) -> None:
        print(f"[career-copilot] {fmt % args}")


def run() -> None:
    port = int(os.environ.get("CAREER_COPILOT_PORT", "8765"))
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Career Copilot running at http://127.0.0.1:{port}")
    print("Press Ctrl+C to stop. Nothing is submitted to employers.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
