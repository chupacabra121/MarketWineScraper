"""Per-run CSV and JSONL exports."""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Iterable, Sequence

from .models import EXPORT_COLUMNS, WineProduct


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def write_csv(products: Sequence[WineProduct], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=EXPORT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for product in products:
            writer.writerow(product.to_row())
    return path


def write_jsonl(products: Sequence[WineProduct], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for product in products:
            handle.write(json.dumps(product.to_row(), ensure_ascii=False) + "\n")
    return path


def export_run(products: Iterable[WineProduct], out_dir: Path, site: str,
               formats: Sequence[str] = ("csv", "jsonl")) -> list[Path]:
    """Write one file per requested format, named by site and timestamp."""
    items = list(products)
    stamp = _stamp()
    written: list[Path] = []
    for fmt in formats:
        target = Path(out_dir) / f"{site}-{stamp}.{fmt}"
        if fmt == "csv":
            written.append(write_csv(items, target))
        elif fmt == "jsonl":
            written.append(write_jsonl(items, target))
        else:
            raise ValueError(f"unknown export format: {fmt}")
    return written
