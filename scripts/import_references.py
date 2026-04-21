#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import zipfile
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree as ET


OPTION_RE = re.compile(r"^\s*([A-F])[\.、\)\]:：]\s*(.+?)\s*$")
ANSWER_RE = re.compile(r"^\s*(?:答案|answer)\s*[:：]\s*([A-F])\s*$", re.IGNORECASE)
ANALYSIS_RE = re.compile(r"^\s*(?:解析|analysis)\s*[:：]\s*(.*)$", re.IGNORECASE)
META_RE = re.compile(r"^\s*(?:@|meta[:：]|标签[:：])\s*(.+)$", re.IGNORECASE)
BLOCK_SPLIT_RE = re.compile(r"^\s*---+\s*$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import raw public-exam reference questions from Markdown/text, CSV, JSONL, or XLSX."
    )
    parser.add_argument("input", nargs="+", help="Input file or directory.")
    parser.add_argument("--output", required=True, help="Output JSONL path.")
    parser.add_argument("--sheet", help="Optional XLSX sheet name.")
    return parser.parse_args()


def discover_files(inputs: list[str]) -> list[Path]:
    supported = {".md", ".markdown", ".txt", ".csv", ".jsonl", ".xlsx"}
    files: list[Path] = []
    for raw in inputs:
        path = Path(raw)
        if path.is_dir():
            for child in sorted(path.rglob("*")):
                if child.is_file() and child.suffix.lower() in supported:
                    files.append(child)
        elif path.is_file():
            files.append(path)
        else:
            raise FileNotFoundError(f"Input not found: {path}")
    if not files:
        raise FileNotFoundError("No supported input files found.")
    return files


def clean_text(text: str) -> str:
    text = text.replace("\ufeff", "").replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.strip() for line in text.split("\n")]
    cleaned = "\n".join(line for line in lines if line)
    return cleaned.strip()


def parse_meta_blob(blob: str) -> dict[str, str]:
    meta: dict[str, str] = {}
    for part in re.split(r"[;；]", blob):
        if not part.strip():
            continue
        if "=" in part:
            key, value = part.split("=", 1)
        elif ":" in part:
            key, value = part.split(":", 1)
        elif "：" in part:
            key, value = part.split("：", 1)
        else:
            continue
        meta[key.strip()] = value.strip()
    return meta


def split_markdown_blocks(text: str) -> list[list[str]]:
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in text.replace("\ufeff", "").splitlines():
        if BLOCK_SPLIT_RE.match(line):
            if any(item.strip() for item in current):
                blocks.append(current)
            current = []
            continue
        current.append(line)
    if any(item.strip() for item in current):
        blocks.append(current)
    return blocks


def is_title(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    return bool(
        re.match(
            r"^(#+\s*)?(?:第?\s*\d+\s*题|题目\s*\d+|q\d+|question\s*\d+)",
            stripped,
            re.IGNORECASE,
        )
    )


def canonical_meta_key(key: str) -> str:
    normalized = key.strip().lower().replace(" ", "_")
    mapping = {
        "exam": "exam_type",
        "exam_type": "exam_type",
        "examtype": "exam_type",
        "考试": "exam_type",
        "考试类型": "exam_type",
        "subject": "subject",
        "科目": "subject",
        "学科": "subject",
        "province": "province",
        "地区": "province",
        "省份": "province",
        "module": "module",
        "模块": "module",
        "题型": "subtype",
        "subtype": "subtype",
        "difficulty": "difficulty",
        "难度": "difficulty",
        "pattern_tags": "pattern_tags",
        "tags": "pattern_tags",
        "reasoning_path": "reasoning_path",
        "distractor_style": "distractor_style",
        "id": "id",
    }
    return mapping.get(normalized, normalized)


def parse_markdown_block(lines: list[str], source_path: Path) -> dict[str, object]:
    metadata: dict[str, str] = {}
    stem_lines: list[str] = []
    options: dict[str, str] = {}
    analysis_lines: list[str] = []
    answer = ""
    in_analysis = False

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#") and not stem_lines and not options:
            continue
        meta_match = META_RE.match(line)
        if meta_match:
            metadata.update(parse_meta_blob(meta_match.group(1)))
            continue
        if is_title(line) and not stem_lines and not options:
            continue
        option_match = OPTION_RE.match(line)
        if option_match:
            options[option_match.group(1).upper()] = option_match.group(2).strip()
            in_analysis = False
            continue
        answer_match = ANSWER_RE.match(line)
        if answer_match:
            answer = answer_match.group(1).upper()
            in_analysis = False
            continue
        analysis_match = ANALYSIS_RE.match(line)
        if analysis_match:
            first_line = analysis_match.group(1).strip()
            if first_line:
                analysis_lines.append(first_line)
            in_analysis = True
            continue
        if in_analysis:
            analysis_lines.append(line)
            continue
        stem_lines.append(line)

    item: dict[str, object] = {
        "source_path": str(source_path),
        "source_type": source_path.suffix.lower().lstrip("."),
        "stem": clean_text("\n".join(stem_lines)),
        "options": options,
        "answer": answer,
        "analysis": clean_text("\n".join(analysis_lines)),
    }
    for key, value in metadata.items():
        item[canonical_meta_key(key)] = value
    return item


def parse_markdown_file(path: Path) -> list[dict[str, object]]:
    text = path.read_text(encoding="utf-8")
    items = [parse_markdown_block(block, path) for block in split_markdown_blocks(text)]
    return [item for item in items if item.get("stem")]


def parse_jsonl_file(path: Path) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    with path.open("r", encoding="utf-8-sig") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                record = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSONL record: {exc}") from exc
            if not isinstance(record, dict):
                raise ValueError(f"{path}:{line_number}: each JSONL line must be an object.")
            record.setdefault("source_path", str(path))
            record.setdefault("source_type", path.suffix.lower().lstrip("."))
            items.append(record)
    return items


def normalize_row_keys(row: dict[str, str]) -> dict[str, object]:
    normalized: dict[str, object] = {}
    options: dict[str, str] = {}
    for raw_key, raw_value in row.items():
        key = (raw_key or "").strip()
        value = (raw_value or "").strip()
        if not key:
            continue
        low = key.lower().replace(" ", "_")
        if low in {"a", "b", "c", "d", "e", "f"}:
            options[low.upper()] = value
            continue
        if re.fullmatch(r"option[_\s-]*[a-f]", low):
            options[low[-1].upper()] = value
            continue
        if re.fullmatch(r"选项[a-f]", key.lower()):
            options[key[-1].upper()] = value
            continue
        normalized[canonical_meta_key(key)] = value

    if options:
        normalized["options"] = options
    return normalized


def parse_csv_file(path: Path) -> list[dict[str, object]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = [normalize_row_keys(row) for row in reader]
    for row in rows:
        row.setdefault("source_path", str(path))
        row.setdefault("source_type", path.suffix.lower().lstrip("."))
    return rows


def column_index(cell_ref: str) -> int:
    letters = "".join(char for char in cell_ref if char.isalpha()).upper()
    index = 0
    for char in letters:
        index = index * 26 + (ord(char) - 64)
    return index - 1


def parse_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    try:
        raw = archive.read("xl/sharedStrings.xml")
    except KeyError:
        return []
    root = ET.fromstring(raw)
    namespace = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    strings: list[str] = []
    for node in root.findall("a:si", namespace):
        parts = [text.text or "" for text in node.findall(".//a:t", namespace)]
        strings.append("".join(parts))
    return strings


def workbook_sheet_targets(archive: zipfile.ZipFile) -> dict[str, str]:
    namespace = {
        "a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
        "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
    }
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    rel_map: dict[str, str] = {}
    for rel in rels.findall("rel:Relationship", namespace):
        rel_map[rel.attrib["Id"]] = rel.attrib["Target"]
    targets: dict[str, str] = {}
    for sheet in workbook.findall("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}sheets/{http://schemas.openxmlformats.org/spreadsheetml/2006/main}sheet"):
        rel_id = sheet.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
        if not rel_id or rel_id not in rel_map:
            continue
        target = rel_map[rel_id]
        if not target.startswith("xl/"):
            target = f"xl/{target}"
        targets[sheet.attrib["name"]] = target
    return targets


def parse_xlsx_rows(path: Path, sheet_name: str | None) -> list[dict[str, object]]:
    namespace = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(path) as archive:
        targets = workbook_sheet_targets(archive)
        if not targets:
            raise ValueError(f"{path}: no worksheets found.")
        chosen_sheet = sheet_name or next(iter(targets))
        if chosen_sheet not in targets:
            raise ValueError(f"{path}: sheet '{chosen_sheet}' not found.")
        sheet_xml = archive.read(targets[chosen_sheet])
        shared_strings = parse_shared_strings(archive)

    root = ET.fromstring(sheet_xml)
    rows: list[list[str]] = []
    for row in root.findall(".//a:sheetData/a:row", namespace):
        values: dict[int, str] = {}
        max_index = -1
        for cell in row.findall("a:c", namespace):
            cell_ref = cell.attrib.get("r", "")
            index = column_index(cell_ref) if cell_ref else len(values)
            max_index = max(max_index, index)
            cell_type = cell.attrib.get("t")
            value = ""
            if cell_type == "inlineStr":
                text_parts = [node.text or "" for node in cell.findall(".//a:t", namespace)]
                value = "".join(text_parts)
            else:
                value_node = cell.find("a:v", namespace)
                if value_node is None:
                    value = ""
                else:
                    raw_value = value_node.text or ""
                    if cell_type == "s" and raw_value.isdigit():
                        shared_index = int(raw_value)
                        value = shared_strings[shared_index] if shared_index < len(shared_strings) else ""
                    else:
                        value = raw_value
            values[index] = value
        if max_index >= 0:
            rows.append([values.get(i, "") for i in range(max_index + 1)])

    if not rows:
        return []
    headers = rows[0]
    records: list[dict[str, object]] = []
    for row_values in rows[1:]:
        row = {headers[i]: row_values[i] if i < len(row_values) else "" for i in range(len(headers))}
        normalized = normalize_row_keys(row)
        normalized.setdefault("source_path", str(path))
        normalized.setdefault("source_type", path.suffix.lower().lstrip("."))
        records.append(normalized)
    return records


def import_file(path: Path, sheet_name: str | None) -> list[dict[str, object]]:
    suffix = path.suffix.lower()
    if suffix in {".md", ".markdown", ".txt"}:
        return parse_markdown_file(path)
    if suffix == ".csv":
        return parse_csv_file(path)
    if suffix == ".jsonl":
        return parse_jsonl_file(path)
    if suffix == ".xlsx":
        return parse_xlsx_rows(path, sheet_name)
    raise ValueError(f"Unsupported file type: {path}")


def write_jsonl(records: Iterable[dict[str, object]], output_path: Path) -> int:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with output_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            count += 1
    return count


def main() -> int:
    args = parse_args()
    try:
        files = discover_files(args.input)
        all_records: list[dict[str, object]] = []
        for path in files:
            all_records.extend(import_file(path, args.sheet))
        count = write_jsonl(all_records, Path(args.output))
    except Exception as exc:  # noqa: BLE001
        print(f"[import] failed: {exc}", file=sys.stderr)
        return 1

    print(f"[import] wrote {count} records to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
