from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from .models import CareerProfile, profile_from_dict


class Storage:
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _write(self, path: Path, data: dict[str, Any]) -> None:
        fd, tmp = tempfile.mkstemp(dir=self.root, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(data, handle, indent=2, ensure_ascii=False)
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def save_profile(self, profile: CareerProfile) -> None:
        self._write(self.root / "profile.json", profile.to_dict())

    def load_profile(self) -> CareerProfile | None:
        path = self.root / "profile.json"
        return profile_from_dict(json.loads(path.read_text(encoding="utf-8"))) if path.exists() else None

    def save_analysis(self, analysis: dict[str, Any]) -> None:
        self._write(self.root / "latest_analysis.json", analysis)

    def load_analysis(self) -> dict[str, Any] | None:
        path = self.root / "latest_analysis.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
