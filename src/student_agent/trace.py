from __future__ import annotations

import json
import secrets
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .contracts import Contracts


class TraceWriter:
    """Append observable workflow events. Never put prompts or chain-of-thought here."""

    def __init__(self, path: Path, contracts: Contracts) -> None:
        self.path = path
        self.contracts = contracts
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def emit(
        self,
        *,
        case_id: str,
        event_type: str,
        actor: str,
        target: str | None = None,
        decision_code: str | None = None,
        tool_name: str | None = None,
        evidence_refs: list[str] | None = None,
        attributes: dict[str, str | int | float | bool | None] | None = None,
    ) -> dict[str, Any]:
        event: dict[str, Any] = {
            "schema_version": "day09-trace-event-v1",
            "event_id": f"evt_{secrets.token_urlsafe(18)}",
            "case_id": case_id,
            "event_type": event_type,
            "occurred_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "actor": actor,
        }
        optional = {
            "target": target,
            "decision_code": decision_code,
            "tool_name": tool_name,
            "evidence_refs": evidence_refs,
            "attributes": attributes,
        }
        event.update({key: value for key, value in optional.items() if value is not None})
        self.contracts.validate_trace(event, "trace event")
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")
        return event

    def checkpoint(self) -> int:
        """Byte offset used to discard events from a failed case attempt."""
        return self.path.stat().st_size if self.path.exists() else 0

    def rollback(self, offset: int) -> None:
        """Truncate back to a checkpoint so a retried case emits cleanly."""
        if self.path.exists() and self.path.stat().st_size > offset:
            with self.path.open("r+b") as handle:
                handle.truncate(offset)

    def drop_case(self, case_id: str) -> None:
        """Remove every event of one case so it can be replayed without duplicates."""
        if not self.path.exists():
            return
        kept: list[str] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            if json.loads(line).get("case_id") == case_id:
                continue
            kept.append(line)
        self.path.write_text(
            "".join(f"{line}\n" for line in kept), encoding="utf-8"
        )
