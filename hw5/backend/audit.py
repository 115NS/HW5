"""Append-only audit trail for the agent team (output/audit_trail.json).

The file is one JSON array. Entries are only ever appended, never edited or
removed. Each entry stores the SHA-256 of the previous entry (`prev_hash`) and
its own hash (`hash`), so any later edit or deletion breaks the chain and
`verify()` reports it. Before every append the existing chain is verified;
if it has been tampered with, the append is refused instead of overwriting.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

GENESIS_HASH = "0" * 64


def _entry_hash(entry: dict[str, Any]) -> str:
    body = {k: v for k, v in entry.items() if k != "hash"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()


class AuditTamperedError(RuntimeError):
    pass


class AuditTrail:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.lock_path = self.path.with_name(f".{self.path.name}.lock")

    def _read(self) -> list[dict[str, Any]]:
        if not self.path.exists() or self.path.stat().st_size == 0:
            return []
        data = json.loads(self.path.read_text())
        if not isinstance(data, list):
            raise AuditTamperedError(f"{self.path} is not a JSON array.")
        return data

    @staticmethod
    def _problems(entries: list[dict[str, Any]]) -> list[str]:
        problems = []
        prev = GENESIS_HASH
        for i, e in enumerate(entries):
            if e.get("seq") != i:
                problems.append(f"entry {i}: seq is {e.get('seq')!r}, expected {i}")
            if e.get("prev_hash") != prev:
                problems.append(f"entry {i}: prev_hash does not match entry {i - 1}")
            if e.get("hash") != _entry_hash(e):
                problems.append(f"entry {i}: hash mismatch (entry was edited)")
            prev = e.get("hash", "")
        return problems

    def verify(self) -> tuple[bool, list[str]]:
        problems = self._problems(self._read())
        return (not problems, problems)

    def entries(self) -> list[dict[str, Any]]:
        return self._read()

    def append(
        self,
        *,
        action: str,
        run_id: str,
        ticket_id: int | None,
        agent: str | None,
        **fields: Any,
    ) -> dict[str, Any]:
        """Append one entry. Extra keyword fields (tool, delegation, error,
        approval_status, details, step, ...) are stored as given."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.lock_path, "w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            entries = self._read()
            problems = self._problems(entries)
            if problems:
                raise AuditTamperedError("Refusing to append to a modified audit trail: " + "; ".join(problems[:3]))
            entry: dict[str, Any] = {
                "seq": len(entries),
                "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
                "run_id": run_id,
                "ticket_id": ticket_id,
                "agent": agent,
                "action": action,
                **{k: v for k, v in fields.items() if v is not None},
                "prev_hash": entries[-1]["hash"] if entries else GENESIS_HASH,
            }
            entry = json.loads(json.dumps(entry, default=str))  # store exactly what is hashed
            entry["hash"] = _entry_hash(entry)
            entries.append(entry)
            fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=".audit-", suffix=".json")
            with os.fdopen(fd, "w") as f:
                json.dump(entries, f, indent=2)
                f.write("\n")
            os.replace(tmp, self.path)
        return entry
