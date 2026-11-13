#!/usr/bin/env python3
"""Audit a Youzan cart audience against a same-window purchased-customer export.

The script is deliberately fail-closed. It prints aggregate-only JSON by
default and writes PII-bearing CSV files only with --write-private-output.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable


TIME_FORMAT = "%Y-%m-%d %H:%M:%S"
PHONE_RE = re.compile(r"^1\d{10}$")


@dataclass
class Table:
    rows: list[dict[str, str]]
    fieldnames: list[str]
    source_name: str


@dataclass
class AuditResult:
    summary: dict[str, Any]
    verified_nonbuyers: list[dict[str, str]]
    excluded_paid: list[dict[str, str]]
    unverifiable_audience: list[dict[str, str]]
    blocked: bool


def decode_csv(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("CSV encoding is not UTF-8/GB18030")


def read_table(path: Path) -> Table:
    if not path.exists():
        raise FileNotFoundError(path)
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as archive:
            names = [name for name in archive.namelist() if name.lower().endswith(".csv") and not name.endswith("/")]
            if len(names) != 1:
                raise ValueError(f"{path.name}: expected exactly one CSV in ZIP, got {len(names)}")
            source_name = names[0]
            text = decode_csv(archive.read(source_name))
    elif path.suffix.lower() == ".csv":
        source_name = path.name
        text = decode_csv(path.read_bytes())
    else:
        raise ValueError(f"{path.name}: only .csv and .zip inputs are supported")

    reader = csv.DictReader(io.StringIO(text, newline=""))
    if not reader.fieldnames:
        raise ValueError(f"{source_name}: missing CSV header")
    fieldnames = [name for name in reader.fieldnames if name]
    rows = []
    for raw in reader:
        row = {key: (value or "").strip() for key, value in raw.items() if key}
        if any(row.values()):
            rows.append(row)
    return Table(rows=rows, fieldnames=fieldnames, source_name=source_name)


def normalize_key(value: str, key_type: str) -> str:
    value = (value or "").strip()
    if key_type == "phone":
        digits = re.sub(r"\D", "", value)
        return digits if PHONE_RE.fullmatch(digits) else ""
    if key_type == "id":
        return value if value and "*" not in value else ""
    raise ValueError(f"unsupported key type: {key_type}")


def parse_time(value: str) -> datetime | None:
    value = (value or "").strip()
    if not value:
        return None
    for fmt in (TIME_FORMAT, "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value[:19] if fmt != "%Y-%m-%d" else value[:10], fmt)
        except ValueError:
            continue
    return None


def unique_by_key(rows: Iterable[dict[str, str]], column: str, key_type: str) -> tuple[dict[str, dict[str, str]], list[dict[str, str]], int]:
    keyed: dict[str, dict[str, str]] = {}
    missing: list[dict[str, str]] = []
    duplicates = 0
    for row in rows:
        key = normalize_key(row.get(column, ""), key_type)
        if not key:
            missing.append(row)
        elif key in keyed:
            duplicates += 1
        else:
            keyed[key] = row
    return keyed, missing, duplicates


def audit_tables(
    audience: Table,
    paid: Table,
    *,
    window_start: datetime,
    window_end: datetime,
    ui_count: int,
    key_type: str,
    audience_key_column: str,
    paid_key_column: str,
    paid_time_column: str,
    allow_ui_count_mismatch: bool = False,
    allow_unverifiable: bool = False,
) -> AuditResult:
    if window_end <= window_start:
        raise ValueError("window end must be later than start")
    for label, table, column in (
        ("audience", audience, audience_key_column),
        ("paid customers", paid, paid_key_column),
    ):
        if column not in table.fieldnames:
            raise ValueError(f"{label}: missing key column {column!r}")
    if paid_time_column not in paid.fieldnames:
        raise ValueError(f"paid customers: missing time column {paid_time_column!r}")

    audience_by_key, audience_missing, audience_duplicates = unique_by_key(
        audience.rows, audience_key_column, key_type
    )
    paid_by_key, paid_missing, paid_duplicates = unique_by_key(
        paid.rows, paid_key_column, key_type
    )

    invalid_paid_time = 0
    outside_paid_window = 0
    for row in paid.rows:
        parsed = parse_time(row.get(paid_time_column, ""))
        if parsed is None:
            invalid_paid_time += 1
        elif not (window_start <= parsed < window_end):
            outside_paid_window += 1

    unique_audience_total = len(audience_by_key) + len(audience_missing)
    count_matches = unique_audience_total == ui_count
    paid_keys = set(paid_by_key)
    excluded_keys = set(audience_by_key) & paid_keys
    nonbuyer_keys = set(audience_by_key) - paid_keys
    verified_nonbuyers = [audience_by_key[key] for key in sorted(nonbuyer_keys)]
    excluded_paid = [audience_by_key[key] for key in sorted(excluded_keys)]

    blockers: list[str] = []
    warnings: list[str] = []
    if not count_matches:
        target = warnings if allow_ui_count_mismatch else blockers
        target.append("ui_count_does_not_match_unique_export_customers")
    if audience_missing:
        target = warnings if allow_unverifiable else blockers
        target.append("audience_contains_unverifiable_customer_keys")
    if paid_missing:
        target = warnings if allow_unverifiable else blockers
        target.append("paid_export_contains_unverifiable_customer_keys")
    if invalid_paid_time:
        blockers.append("paid_export_contains_invalid_or_missing_time")
    if outside_paid_window:
        blockers.append("paid_export_contains_rows_outside_window")

    status = "blocked" if blockers else ("warning" if warnings else "ok")
    summary: dict[str, Any] = {
        "status": status,
        "blockers": blockers,
        "warnings": warnings,
        "window": {
            "timezone": "Asia/Shanghai",
            "start_inclusive": window_start.strftime(TIME_FORMAT),
            "end_exclusive": window_end.strftime(TIME_FORMAT),
        },
        "matching": {
            "key_type": key_type,
            "audience_key_column": audience_key_column,
            "paid_key_column": paid_key_column,
            "name_or_nickname_matching_used": False,
        },
        "audience": {
            "raw_rows": len(audience.rows),
            "ui_count": ui_count,
            "unique_identifiable_customers": len(audience_by_key),
            "unverifiable_rows": len(audience_missing),
            "duplicate_rows_removed": audience_duplicates,
            "unique_total_for_ui_check": unique_audience_total,
            "ui_count_matches": count_matches,
        },
        "paid_customers": {
            "raw_rows": len(paid.rows),
            "unique_identifiable_customers": len(paid_by_key),
            "unverifiable_rows": len(paid_missing),
            "duplicate_rows_removed": paid_duplicates,
            "invalid_or_missing_time_rows": invalid_paid_time,
            "outside_window_rows": outside_paid_window,
        },
        "result": {
            "excluded_as_paid_customers": len(excluded_paid),
            "verified_nonbuyers": len(verified_nonbuyers),
            "unverifiable_audience_rows": len(audience_missing),
            "balance_check": len(excluded_paid) + len(verified_nonbuyers) == len(audience_by_key),
        },
    }
    return AuditResult(
        summary=summary,
        verified_nonbuyers=verified_nonbuyers,
        excluded_paid=excluded_paid,
        unverifiable_audience=audience_missing,
        blocked=bool(blockers),
    )


def write_private_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str], status: str) -> None:
    extra = "_audit_status"
    output_fields = [name for name in fieldnames if name] + ([extra] if extra not in fieldnames else [])
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=output_fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            output = dict(row)
            output[extra] = status
            writer.writerow(output)
    os.chmod(path, 0o600)


def write_outputs(output_dir: Path, result: AuditResult, audience: Table, window_end: datetime) -> list[str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(output_dir, 0o700)
    label = (window_end - timedelta(seconds=1)).date().isoformat()
    paths = [
        (output_dir / f"youzan-cart-nonbuyers-{label}-private.csv", result.verified_nonbuyers, "verified_nonbuyer"),
        (output_dir / f"youzan-cart-excluded-paid-{label}-private.csv", result.excluded_paid, "excluded_paid"),
        (output_dir / f"youzan-cart-unverifiable-{label}-private.csv", result.unverifiable_audience, "unverifiable"),
    ]
    written = []
    for path, rows, status in paths:
        write_private_csv(path, rows, audience.fieldnames, status)
        written.append(str(path))
    summary_path = output_dir / f"youzan-cart-audit-{label}-summary.json"
    summary_path.write_text(json.dumps(result.summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.chmod(summary_path, 0o600)
    written.append(str(summary_path))
    return written


def write_zip_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("data.csv", "\ufeff" + buffer.getvalue())


def self_test() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        audience_path = root / "audience.zip"
        paid_path = root / "paid.zip"
        phone_a = "138" + "0" * 7 + "1"
        phone_b = "138" + "0" * 7 + "2"
        write_zip_csv(
            audience_path,
            [
                {"客户手机号": phone_a, "客户昵称": "a"},
                {"客户手机号": phone_b, "客户昵称": "b"},
                {"客户手机号": phone_b, "客户昵称": "b-duplicate"},
            ],
            ["客户手机号", "客户昵称"],
        )
        write_zip_csv(
            paid_path,
            [{"客户手机号": phone_a, "上次消费时间": "2026-07-17 08:00:00"}],
            ["客户手机号", "上次消费时间"],
        )
        audience_table = read_table(audience_path)
        result = audit_tables(
            audience_table,
            read_table(paid_path),
            window_start=datetime(2026, 7, 17),
            window_end=datetime(2026, 7, 18),
            ui_count=2,
            key_type="phone",
            audience_key_column="客户手机号",
            paid_key_column="客户手机号",
            paid_time_column="上次消费时间",
        )
        assert not result.blocked, result.summary
        assert result.summary["audience"]["duplicate_rows_removed"] == 1
        assert result.summary["result"]["excluded_as_paid_customers"] == 1
        assert result.summary["result"]["verified_nonbuyers"] == 1
        assert result.summary["result"]["balance_check"] is True
        written = write_outputs(root / "private", result, audience_table, datetime(2026, 7, 18))
        assert len(written) == 4
        assert all(Path(path).exists() for path in written)
        assert all((Path(path).stat().st_mode & 0o777) == 0o600 for path in written)
        assert ((root / "private").stat().st_mode & 0o777) == 0o700
    print("self-test: ok")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit a Youzan cart audience against same-window purchased customers.")
    parser.add_argument("--audience", type=Path, help="Cart audience CSV or ZIP containing one CSV")
    parser.add_argument("--paid-customers", type=Path, help="Purchased-customer CSV or ZIP containing one CSV")
    parser.add_argument("--window-start", help="Inclusive start, format YYYY-MM-DD HH:MM:SS")
    parser.add_argument("--window-end", help="Exclusive end, format YYYY-MM-DD HH:MM:SS")
    parser.add_argument("--ui-count", type=int, help="Customer count shown in Youzan for the cart window")
    parser.add_argument("--key-type", choices=("phone", "id"), default="phone")
    parser.add_argument("--audience-key-column", default="客户手机号")
    parser.add_argument("--paid-key-column", default="客户手机号")
    parser.add_argument("--paid-time-column", default="上次消费时间")
    parser.add_argument("--allow-ui-count-mismatch", action="store_true", help="Diagnostic override; never use for final delivery")
    parser.add_argument("--allow-unverifiable", action="store_true", help="Diagnostic override; unmatched rows remain unverified")
    parser.add_argument("--write-private-output", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--self-test", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.self_test:
        self_test()
        return 0
    required = {
        "--audience": args.audience,
        "--paid-customers": args.paid_customers,
        "--window-start": args.window_start,
        "--window-end": args.window_end,
        "--ui-count": args.ui_count,
    }
    missing = [name for name, value in required.items() if value is None]
    if missing:
        raise ValueError("missing required arguments: " + ", ".join(missing))
    if args.ui_count < 0:
        raise ValueError("ui count must be non-negative")
    if args.write_private_output and args.output_dir is None:
        raise ValueError("--output-dir is required with --write-private-output")

    audience = read_table(args.audience)
    paid = read_table(args.paid_customers)
    result = audit_tables(
        audience,
        paid,
        window_start=datetime.strptime(args.window_start, TIME_FORMAT),
        window_end=datetime.strptime(args.window_end, TIME_FORMAT),
        ui_count=args.ui_count,
        key_type=args.key_type,
        audience_key_column=args.audience_key_column,
        paid_key_column=args.paid_key_column,
        paid_time_column=args.paid_time_column,
        allow_ui_count_mismatch=args.allow_ui_count_mismatch,
        allow_unverifiable=args.allow_unverifiable,
    )
    print(json.dumps(result.summary, ensure_ascii=False, indent=2))
    if args.write_private_output:
        if result.summary["status"] != "ok":
            print("private outputs require an audit without blockers or warnings", file=sys.stderr)
            return 2
        else:
            written = write_outputs(
                args.output_dir,
                result,
                audience,
                datetime.strptime(args.window_end, TIME_FORMAT),
            )
            print(json.dumps({"private_outputs_written": len(written)}, ensure_ascii=False))
    return 2 if result.blocked else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, csv.Error, zipfile.BadZipFile) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(1)
