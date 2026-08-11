"""A record of judgements already made about the data.

The checks in :mod:`winescraper.validate` cannot settle everything. Some of what
they flag is correct and will stay flagged forever — "Sampanie Moet & Chandon"
carries no colour, no grape and no sweetness, so it reaches the review queue
every single run and is wine every single time. Some of it is a real fault the
code cannot see: two different Tohani wines that Freshful lists under identical
titles.

Without somewhere to put the answer, both come back in full on every run, and a
queue that repeats itself is a queue nobody reads. This stores the answer.

Decisions live in a JSON-lines file, one object per line, meant to be committed:
they are human judgements about a catalogue, not derived data, so they belong in
version control next to the code rather than in a database that gets rebuilt.

    {"finding": "review", "retailer": "auchan", "external_id": "9887",
     "verdict": "wine", "note": "Moet & Chandon", "decided_at": "2026-08-11..."}

Three verdicts:

``wine``
    The flag was wrong; the listing is fine. Stop reporting it.
``exclude``
    The flag was right and the listing does not belong in the data. It is
    dropped from exports and reports — a denylist anyone can extend without
    touching the filter code.
``noted``
    The flag is real and cannot be fixed here. Stop reporting it, but keep it
    on the record so the reason is not lost.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

VERDICTS = ("wine", "exclude", "noted")

#: Findings keyed by the wine they group rather than by a single listing.
_WINE_FINDINGS = {"wine spread"}


@dataclass(frozen=True)
class Decision:
    finding: str
    verdict: str
    retailer: str = ""
    external_id: str = ""
    wine_key: str = ""
    note: str = ""
    decided_at: str = ""

    @property
    def target(self) -> tuple:
        """What this decision applies to."""
        if self.wine_key:
            return ("wine", self.wine_key)
        return ("listing", self.retailer, str(self.external_id))

    def to_json(self) -> dict:
        out = {"finding": self.finding, "verdict": self.verdict}
        if self.wine_key:
            out["wine_key"] = self.wine_key
        else:
            out["retailer"] = self.retailer
            out["external_id"] = str(self.external_id)
        if self.note:
            out["note"] = self.note
        out["decided_at"] = self.decided_at
        return out


@dataclass
class DecisionLog:
    """Every decision made so far, indexed for lookup."""

    decisions: list = field(default_factory=list)

    @property
    def by_target(self) -> dict:
        # Later lines win, so a decision can be revised by appending a new one.
        return {(d.finding, *d.target): d for d in self.decisions}

    @property
    def excluded(self) -> set:
        """Listings a human has ruled out of the dataset."""
        return {d.target for d in self.decisions
                if d.verdict == "exclude" and not d.wine_key}

    def settled(self, finding: str, retailer: str = "", external_id: str = "",
                wine_key: str = "") -> Decision | None:
        target = ("wine", wine_key) if wine_key else ("listing", retailer, str(external_id))
        return self.by_target.get((finding, *target))

    def add(self, decision: Decision) -> Decision:
        self.decisions.append(decision)
        return decision


def load(path: str | Path) -> DecisionLog:
    """Read the log, skipping unparsable lines rather than failing the run."""
    path = Path(path)
    if not path.exists():
        return DecisionLog()
    decisions = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            raw = json.loads(line)
            decisions.append(Decision(
                finding=raw["finding"], verdict=raw["verdict"],
                retailer=raw.get("retailer", ""),
                external_id=str(raw.get("external_id", "")),
                wine_key=raw.get("wine_key", ""),
                note=raw.get("note", ""),
                decided_at=raw.get("decided_at", "")))
        except (json.JSONDecodeError, KeyError) as exc:
            # A malformed line is a typo in a hand-edited file. Losing the
            # whole log to it would be worse than losing the line.
            raise ValueError(f"{path}:{number}: {exc}") from None
    return DecisionLog(decisions)


def record(path: str | Path, decision: Decision) -> Decision:
    """Append one decision. The file is append-only so history is preserved."""
    if decision.verdict not in VERDICTS:
        raise ValueError(f"verdict must be one of {', '.join(VERDICTS)}")
    if not decision.wine_key and not (decision.retailer and decision.external_id):
        raise ValueError("a decision needs either a wine_key or retailer + external_id")
    if decision.finding in _WINE_FINDINGS and not decision.wine_key:
        raise ValueError(f"'{decision.finding}' applies to a wine, so it needs a wine_key")
    stamped = Decision(**{**decision.__dict__,
                          "decided_at": decision.decided_at or _now()})
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(stamped.to_json(), ensure_ascii=False) + "\n")
    return stamped


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def filter_rows(rows: list, log: DecisionLog) -> tuple[list, int]:
    """Drop listings ruled out by an ``exclude`` verdict.

    This is the part of the log that changes the data rather than the report: a
    denylist anyone can extend by recording a decision, without editing the
    filter rules in ``normalize``. Returns (kept rows, dropped count).
    """
    excluded = log.excluded
    if not excluded:
        return list(rows), 0
    kept = [r for r in rows
            if ("listing", r["retailer"], str(r.get("external_id"))) not in excluded]
    return kept, len(rows) - len(kept)


def apply(findings: list, log: DecisionLog) -> tuple[list, int]:
    """Drop findings already settled. Returns (open findings, settled count)."""
    if not log.decisions:
        return list(findings), 0
    open_findings = []
    settled = 0
    for finding in findings:
        key = getattr(finding, "wine_key", "") or ""
        if log.settled(finding.kind, retailer=getattr(finding, "retailer_key", ""),
                       external_id=getattr(finding, "external_id", ""),
                       wine_key=key):
            settled += 1
            continue
        open_findings.append(finding)
    return open_findings, settled
