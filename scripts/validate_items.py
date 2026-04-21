#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ALLOWED_EXAMS = {"国考", "省考", "事业单位"}
ALLOWED_SUBJECTS = {"公基", "职测"}
PUBLIC_BASE_MODULES = {"法律", "政治", "经济", "管理", "科技人文", "历史文化", "公文"}
APTITUDE_MODULES = {"言语", "判断", "数量", "资料", "常识"}
ALLOWED_MODULES = PUBLIC_BASE_MODULES | APTITUDE_MODULES
ALLOWED_DIFFICULTIES = {"基础", "中等", "提高"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate normalized public-exam JSONL records.")
    parser.add_argument("input", nargs="+", help="Normalized JSONL file(s).")
    return parser.parse_args()


def load_jsonl(path: Path) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    with path.open("r", encoding="utf-8-sig") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                record = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSON: {exc}") from exc
            if not isinstance(record, dict):
                raise ValueError(f"{path}:{line_number}: record must be an object.")
            record["_line"] = line_number
            records.append(record)
    return records


def validate_record(record: dict[str, object], seen_ids: set[str]) -> list[str]:
    errors: list[str] = []
    record_id = str(record.get("id", "")).strip()
    if not record_id:
        errors.append("missing id")
    elif record_id in seen_ids:
        errors.append(f"duplicate id: {record_id}")
    else:
        seen_ids.add(record_id)

    exam_type = str(record.get("exam_type", "")).strip()
    if exam_type not in ALLOWED_EXAMS:
        errors.append(f"invalid exam_type: {exam_type}")

    subject = str(record.get("subject", "")).strip()
    if subject not in ALLOWED_SUBJECTS:
        errors.append(f"invalid subject: {subject}")

    module = str(record.get("module", "")).strip()
    if module not in ALLOWED_MODULES:
        errors.append(f"invalid module: {module}")
    elif subject == "公基" and module not in PUBLIC_BASE_MODULES:
        errors.append(f"module not allowed for subject 公基: {module}")
    elif subject == "职测" and module not in APTITUDE_MODULES:
        errors.append(f"module not allowed for subject 职测: {module}")

    difficulty = str(record.get("difficulty", "")).strip()
    if difficulty not in ALLOWED_DIFFICULTIES:
        errors.append(f"invalid difficulty: {difficulty}")

    stem = str(record.get("stem", "")).strip()
    if not stem:
        errors.append("missing stem")

    options = record.get("options")
    answer = str(record.get("answer", "")).strip().upper()
    if not isinstance(options, dict) or not options:
        errors.append("missing options")
    else:
        option_keys = [key for key, value in sorted(options.items()) if str(value).strip()]
        if len(option_keys) < 4:
            errors.append("option count below 4")
        if len(option_keys) > 6:
            errors.append("option count above 6")
        if not answer:
            errors.append("missing answer")
        elif answer not in option_keys:
            errors.append(f"answer not found in options: {answer}")

    analysis = str(record.get("analysis", "")).strip()
    if not analysis:
        errors.append("missing analysis")

    for field_name in ("pattern_tags", "reasoning_path", "distractor_style"):
        value = record.get(field_name)
        if not isinstance(value, list) or not value or not all(str(item).strip() for item in value):
            errors.append(f"invalid {field_name}")

    return errors


def main() -> int:
    args = parse_args()
    seen_ids: set[str] = set()
    total = 0
    invalid = 0

    try:
        for raw_path in args.input:
            path = Path(raw_path)
            for record in load_jsonl(path):
                total += 1
                errors = validate_record(record, seen_ids)
                if errors:
                    invalid += 1
                    line_number = record.get("_line", "?")
                    print(f"[validate] {path}:{line_number}: " + "; ".join(errors), file=sys.stderr)
    except Exception as exc:  # noqa: BLE001
        print(f"[validate] failed: {exc}", file=sys.stderr)
        return 1

    if invalid:
        print(f"[validate] invalid records: {invalid}/{total}", file=sys.stderr)
        return 1

    print(f"[validate] all records valid: {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
