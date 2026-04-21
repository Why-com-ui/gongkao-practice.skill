#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


SCENARIOS = [
    "国考 + 言语 + 5题 + 中等 + set",
    "江苏省考 + 判断推理 + 10题 + 提高 + set",
    "广东省考 + 资料分析 + 3题 + 基础 + interactive",
    "事业单位 + 公基 + 5题 + 中等 + set",
    "事业单位 + 混合练习 + 8题",
    "导入 Markdown 参考题 -> 结构化入库",
    "导入 CSV/Excel 参考题 -> 结构化入库",
    "基于 3-5 道参考题生成同结构新题",
    "参考题字段缺失/答案异常时的校验失败",
    "未指定省份/模块/难度时是否走默认值",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export local validation prompts for gongkao-practice.")
    parser.add_argument(
        "--output",
        default="assets/reference-bank/samples/validation-prompts.md",
        help="Output markdown path.",
    )
    parser.add_argument(
        "--bank-dir",
        default="assets/reference-bank/normalized",
        help="Directory containing normalized JSONL files.",
    )
    return parser.parse_args()


def count_records(bank_dir: Path) -> tuple[int, list[str]]:
    preferred = bank_dir / "sample_references.jsonl"
    if preferred.exists():
        with preferred.open("r", encoding="utf-8-sig") as handle:
            total = sum(1 for line in handle if line.strip())
        return total, [preferred.name]

    total = 0
    files: list[str] = []
    for path in sorted(bank_dir.glob("*.jsonl")):
        files.append(path.name)
        with path.open("r", encoding="utf-8-sig") as handle:
            total += sum(1 for line in handle if line.strip())
    return total, files


def render_markdown(total_records: int, files: list[str]) -> str:
    lines = [
        "# 本地验证提示词",
        "",
        f"- 结构化题目总数: `{total_records}`",
        f"- 已发现题库文件: `{', '.join(files) if files else '无'}`",
        "",
        "## 核心验收场景",
        "",
    ]
    for index, scenario in enumerate(SCENARIOS, start=1):
        lines.append(f"{index}. `{scenario}`")

    lines.extend(
        [
            "",
            "## 示例请求",
            "",
            '- “按江苏省考风格出 5 道判断推理题，难度提高，每题后给答案和解析。”',
            '- “给我来一组事业单位公基 5 题练习，题后立刻显示答案解析。”',
            '- “学习 `assets/reference-bank/normalized/sample_references.jsonl` 的 3 道题，再出 3 道同结构同解法的新题。”',
            '- “进入逐题互动模式，按广东省考资料分析风格开始练习。”',
            "",
            "## 验收关注点",
            "",
            "- 题型归类是否正确",
            "- 地区风格是否明显跑偏",
            "- 仿题是否只是表面改写",
            "- 答案是否唯一",
            "- 解析是否说明正确项和错误项",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    bank_dir = Path(args.bank_dir)
    total_records, files = count_records(bank_dir)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown(total_records, files), encoding="utf-8")

    summary = {
        "output": str(output_path),
        "total_records": total_records,
        "files": files,
        "scenarios": SCENARIOS,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
