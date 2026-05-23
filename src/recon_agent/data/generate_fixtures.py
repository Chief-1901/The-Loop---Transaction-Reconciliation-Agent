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


DEFECT_VARIANTS: dict[str, dict[str, float]] = {
    "happy_clean":      {},
    "tz_only":          {"timezone_shift": 0.05},
    "encoding_only":    {"encoding_corruption": 0.01},
    "duplicate_only":   {"duplicate": 0.02},
    "value_only":       {"value_mismatch": 0.03},
    "default": {
        "value_mismatch":     0.03,
        "timezone_shift":     0.05,
        "duplicate":          0.02,
        "missing_in_api":     0.02,
        "missing_in_csv":     0.005,
        "encoding_corruption": 0.01,
    },
    "default_disabled_api": {  # same as default; the eval scenario disables fetch_api at CLI
        "value_mismatch":     0.03,
        "timezone_shift":     0.05,
        "duplicate":          0.02,
        "missing_in_api":     0.02,
        "missing_in_csv":     0.005,
        "encoding_corruption": 0.01,
    },
    "default_latin1_csv": {     # like default + CSV written in latin-1 (handled in write step)
        "value_mismatch":     0.03,
        "timezone_shift":     0.05,
        "duplicate":          0.02,
        "missing_in_api":     0.02,
        "encoding_corruption": 0.01,
    },
    "corrupted_source": {},     # CSV will be replaced with binary garbage
    "irreconcilable":   {},     # 0 shared txn_ids — handled in injection
}


def _inject_value_mismatch(csv_row: dict, api_record: dict, rng: random.Random) -> InjectedDefect:
    # round api.gross_amount to nearest ₹10 away from csv's actual
    orig = api_record["gross_amount"]
    rounded = round(orig / 10) * 10 + rng.choice([-0.99, 0.99])
    api_record["gross_amount"] = round(rounded, 2)
    return InjectedDefect(
        txn_id=csv_row["txn_id"], kind="value_mismatch",
        csv={"order_value_inr": orig}, api={"gross_amount": api_record["gross_amount"]},
        expected_correction={
            "field": "gross_amount", "old": api_record["gross_amount"], "new": orig,
            "reason_contains": "rounding",
        }
    )


def _inject_timezone_shift(csv_row: dict, api_record: dict, _rng) -> InjectedDefect:
    # API's settled_at claims +00:00 but the value is actually IST hours
    redemption_ts_ist = datetime.fromisoformat(csv_row["redemption_ts"])
    # write the IST clock time but with UTC offset
    fake_settled = redemption_ts_ist.replace(tzinfo=UTC)
    api_record["settled_at"] = fake_settled.isoformat()
    correct_settled = redemption_ts_ist.astimezone(UTC)
    return InjectedDefect(
        txn_id=csv_row["txn_id"], kind="timezone_shift",
        csv={"redemption_ts": csv_row["redemption_ts"]},
        api={"settled_at": api_record["settled_at"]},
        expected_correction={
            "field": "settled_at", "old": api_record["settled_at"],
            "new": correct_settled.isoformat(), "reason_contains": "ist_stored_as_utc",
        }
    )


def _inject_duplicate(csv_row: dict, api_record: dict, rng: random.Random,
                      csv_rows: list[dict]) -> InjectedDefect:
    # Append another CSV row with same txn_id, slightly different redemption_ts
    dup = dict(csv_row)
    redemption_ts_ist = datetime.fromisoformat(csv_row["redemption_ts"])
    dup["redemption_ts"] = (redemption_ts_ist + timedelta(seconds=rng.randint(5, 60))).isoformat()
    csv_rows.append(dup)
    return InjectedDefect(
        txn_id=csv_row["txn_id"], kind="duplicate",
        csv={"original_ts": csv_row["redemption_ts"], "dup_ts": dup["redemption_ts"]},
        expected_correction={"field": "_status", "old": "duplicate", "new": "merged",
                             "reason_contains": "dup"}
    )


def _inject_missing_in_api(csv_row: dict, api_record: dict, _rng) -> InjectedDefect:
    # signal removal — caller filters this record out of api_records
    return InjectedDefect(
        txn_id=csv_row["txn_id"], kind="missing_in_api",
        csv={"txn_id": csv_row["txn_id"]},
        expected_correction={"field": "_existence", "old": "absent_in_api",
                             "new": "ledger_recorded", "reason_contains": "settlement_gap"}
    )


def _inject_missing_in_csv(csv_row: dict, api_record: dict, _rng) -> InjectedDefect:
    return InjectedDefect(
        txn_id=csv_row["txn_id"], kind="missing_in_csv",
        api={"reference_id": csv_row["txn_id"]},
        expected_correction={"field": "_existence", "old": "absent_in_csv",
                             "new": "csv_backfill", "reason_contains": "tracking_miss"}
    )


def _inject_encoding_corruption(csv_row: dict, _api, _rng) -> InjectedDefect:
    orig = csv_row["merchant"]
    # double-encode: latin-1 bytes of "'" misread as UTF-8
    corrupted = orig.replace("a", "â\x80\x99")
    csv_row["merchant"] = corrupted
    return InjectedDefect(
        txn_id=csv_row["txn_id"], kind="encoding_corruption",
        csv={"merchant": corrupted},
        expected_correction={"field": "merchant", "old": corrupted, "new": orig,
                             "reason_contains": "encoding"}
    )


def generate_fixtures(
    seed: int = 42,
    n_txns: int = 500,
    variant: str = "default",
    out_dir: Path = Path("src/recon_agent/data/fixtures"),
    ground_truth_dir: Path = Path("src/recon_agent/data"),
) -> GroundTruth:
    rng = random.Random(seed)
    spec = DEFECT_VARIANTS[variant]

    base_date = datetime(2026, 4, 1, tzinfo=IST)
    csv_rows: list[dict] = []
    api_records: list[dict] = []

    for i in range(n_txns):
        csv_row, api_record = _make_clean(rng, i, base_date)
        csv_rows.append(csv_row)
        api_records.append(api_record)

    # Pass 2: inject defects
    injected: list[InjectedDefect] = []
    txn_to_csv_idx = {row["txn_id"]: i for i, row in enumerate(csv_rows)}
    txn_to_api_idx = {rec["reference_id"]: i for i, rec in enumerate(api_records)}

    for kind, rate in spec.items():
        n_inject = max(1, int(n_txns * rate)) if rate > 0 else 0
        # pick distinct txn_ids that haven't been hit yet
        candidates = [r["txn_id"] for r in csv_rows
                      if r is not None and r["txn_id"] not in {d.txn_id for d in injected}]
        chosen = rng.sample(candidates, min(n_inject, len(candidates)))

        for txn_id in chosen:
            csv_idx = txn_to_csv_idx[txn_id]
            api_idx = txn_to_api_idx.get(txn_id)
            csv_row = csv_rows[csv_idx]
            api_record = api_records[api_idx] if api_idx is not None else None

            if kind == "value_mismatch" and api_record:
                injected.append(_inject_value_mismatch(csv_row, api_record, rng))
            elif kind == "timezone_shift" and api_record:
                injected.append(_inject_timezone_shift(csv_row, api_record, rng))
            elif kind == "duplicate":
                injected.append(_inject_duplicate(csv_row, api_record or {}, rng, csv_rows))
            elif kind == "missing_in_api" and api_record:
                injected.append(_inject_missing_in_api(csv_row, api_record, rng))
                api_records[api_idx] = None     # mark for removal
            elif kind == "missing_in_csv":
                # remove from CSV, keep in API
                injected.append(_inject_missing_in_csv(csv_row, api_record or {}, rng))
                csv_rows[csv_idx] = None
            elif kind == "encoding_corruption":
                injected.append(_inject_encoding_corruption(csv_row, api_record, rng))

    # Drop marked-None entries
    csv_rows = [r for r in csv_rows if r is not None]
    api_records = [r for r in api_records if r is not None]

    # Special variants
    if variant == "corrupted_source":
        csv_path = out_dir / "tracking_db.csv"
        out_dir.mkdir(parents=True, exist_ok=True)
        csv_path.write_bytes(b"\x00\x01\x02\xff\xfe\xfd" * 500)
        _write_json(out_dir / "payu_settlements.json", api_records)
    elif variant == "irreconcilable":
        # rewrite all api.reference_ids so 0 match csv.txn_ids
        for rec in api_records:
            rec["reference_id"] = "DROPPED-" + rec["reference_id"]
        _write_csv(out_dir / "tracking_db.csv", csv_rows)
        _write_json(out_dir / "payu_settlements.json", api_records)
    elif variant == "default_latin1_csv":
        _write_csv(out_dir / "tracking_db.csv", csv_rows, encoding="latin-1")
        _write_json(out_dir / "payu_settlements.json", api_records)
    else:
        _write_csv(out_dir / "tracking_db.csv", csv_rows)
        _write_json(out_dir / "payu_settlements.json", api_records)

    gt = GroundTruth(
        fixture_seed=seed,
        variant=variant,
        total_txns=n_txns,
        generated_at=datetime.now(timezone.utc).isoformat(),
        expected_summary=_count_by_kind(injected),
        injected=[
            {
                "txn_id": d.txn_id, "kind": d.kind, "csv": d.csv,
                "api": d.api, "expected_correction": d.expected_correction,
            }
            for d in injected
        ],
    )
    ground_truth_dir.mkdir(parents=True, exist_ok=True)
    gt_path = ground_truth_dir / f"ground_truth_{variant}.json"
    gt_path.write_text(gt.model_dump_json(indent=2), encoding="utf-8")
    return gt


def _count_by_kind(injected: list[InjectedDefect]) -> dict[str, int]:
    out: dict[str, int] = {}
    for d in injected:
        out[d.kind] = out.get(d.kind, 0) + 1
    out["_total"] = len(injected)
    return out


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--variant", default="default", choices=list(DEFECT_VARIANTS.keys()))
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--n", type=int, default=500)
    p.add_argument("--out-dir", type=Path, default=Path("src/recon_agent/data/fixtures"))
    args = p.parse_args()
    gt = generate_fixtures(seed=args.seed, n_txns=args.n,
                           variant=args.variant, out_dir=args.out_dir)
    print(f"variant={gt.variant} txns={gt.total_txns} injected={gt.expected_summary}")


if __name__ == "__main__":
    main()
