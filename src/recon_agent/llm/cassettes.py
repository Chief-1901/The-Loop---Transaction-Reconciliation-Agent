from __future__ import annotations
import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from .providers import RawLLMResponse


class CassetteMiss(Exception):
    pass


class CassetteLayer:
    """Three modes:
      live    — no read, no write
      record  — no read; write every response to the cassette
      replay  — read; raise CassetteMiss on unknown hash
    """

    def __init__(
        self,
        mode: Literal["live", "record", "replay"],
        path: Path,
    ):
        self.mode = mode
        self.path = path
        self._index: dict[str, RawLLMResponse] = {}
        if self.mode == "replay":
            self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            entry = json.loads(line)
            self._index[entry["hash"]] = RawLLMResponse(**entry["response"])

    @staticmethod
    def hash(
        provider: str, model: str, subtask: str,
        messages: list[dict], schema: type[BaseModel],
    ) -> str:
        payload = {
            "provider": provider,
            "model": model,
            "subtask": subtask,
            "messages": messages,
            "schema": schema.model_json_schema(),
        }
        blob = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(blob).hexdigest()

    def get(self, h: str) -> RawLLMResponse | None:
        if self.mode == "replay":
            r = self._index.get(h)
            if r is None:
                return None
            return r
        return None

    def require(self, h: str) -> RawLLMResponse:
        r = self.get(h)
        if r is None:
            raise CassetteMiss(
                f"No cassette for hash {h[:12]}... in {self.path}. "
                f"Re-record with `make eval-live`."
            )
        return r

    def put(self, h: str, response: RawLLMResponse) -> None:
        if self.mode != "record":
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"hash": h, "response": response.model_dump()}) + "\n")
        self._index[h] = response
