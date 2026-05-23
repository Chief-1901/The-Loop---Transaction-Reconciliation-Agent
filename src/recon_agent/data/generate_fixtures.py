from __future__ import annotations
import argparse
import csv
import hashlib
import json
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from .catalog import CATEGORIES, COUPON_CODES, CHANNELS


IST = timezone(timedelta(hours=5, minutes=30))
UTC = timezone.utc


@dataclass
class InjectedDefect:
    txn_id: str
    kind: str
    csv: dict = field(default_factory=dict)
    api: dict = field(default_factory=dict)
    expected_correction: dict = field(default_factory=dict)


class GroundTruth(BaseModel):
    fixture_seed: int
    variant: str
    total_txns: int
    generated_at: str
    expected_summary: dict[str, int]
    injected: list[dict]


def _make_clean(rng: random.Random, idx: int, base_date: datetime) -> tuple[dict, dict]:
    """Returns (csv_row, api_record) — both clean, perfectly reconciled."""
    cat = rng.choice(CATEGORIES)
    merchant = rng.choice(cat.merchants)
    amount = round(rng.gauss(cat.amount_mean, (cat.amount_max - cat.amount_min) / 4), 2)
    amount = max(cat.amount_min, min(cat.amount_max, amount))
    discount_pct = rng.choice([0.10, 0.20, 0.30, 0.40, 0.50])
    discount = round(amount * discount_pct, 2)
    # Indian business hours bias
    hour = rng.choice([11, 12, 13, 14, 19, 20, 21, 22] + list(range(9, 23)))
    minute = rng.randint(0, 59)
    redemption_ts_ist = base_date.replace(
        hour=hour, minute=minute, second=rng.randint(0, 59), tzinfo=IST
    ) + timedelta(days=rng.randint(0, 30))
    settled_at_utc = redemption_ts_ist.astimezone(UTC) + timedelta(minutes=rng.randint(15, 240))

    txn_id = f"TX-{redemption_ts_ist.year}-{idx:05d}"
    user_hash = hashlib.sha256(f"user{rng.randint(0, 10_000)}".encode()).hexdigest()[:8]

    csv_row = {
        "txn_id": txn_id,
        "redemption_ts": redemption_ts_ist.isoformat(),
        "merchant": merchant,
        "merchant_category": cat.name,
        "deal_id": f"DL-{merchant.upper()}-{rng.randint(100, 9999)}",
        "coupon_code": rng.choice(COUPON_CODES),
        "order_value_inr": f"{amount:.2f}",
        "discount_inr": f"{discount:.2f}",
        "user_id": f"u_{user_hash}",
        "channel": rng.choice(CHANNELS),
    }
    api_record = {
        "settlement_id": f"PYU-{redemption_ts_ist.strftime('%Y%m%d')}-{idx:05d}-S",
        "reference_id": txn_id,
        "settled_at": settled_at_utc.isoformat(),
        "payee": merchant,
        "gross_amount": amount,
        "net_amount": round(amount * 0.99, 2),
        "settlement_status": "settled",
    }
    return csv_row, api_record


def _write_csv(path: Path, rows: list[dict], encoding: str = "utf-8") -> None:
    if not rows:
        path.write_text("", encoding=encoding)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding=encoding, newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "page": 1,
        "page_size": len(records),
        "total": len(records),
        "next_cursor": None,
        "records": records,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
