#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Iterable


EXAM_MAP = {
    "国考": "国考",
    "国家公务员考试": "国考",
    "中央机关及其直属机构招录": "国考",
    "公务员国考": "国考",
    "省考": "省考",
    "联考": "省考",
    "地方公务员考试": "省考",
    "事业单位": "事业单位",
    "事业编": "事业单位",
    "职测": "事业单位",
    "公基": "事业单位",
}

SUBJECT_MAP = {
    "公基": "公基",
    "公共基础知识": "公基",
    "综合基础知识": "公基",
    "综合基础": "公基",
    "职测": "职测",
    "职业能力倾向测验": "职测",
    "职业倾向能力测验": "职测",
    "行测": "职测",
}

PUBLIC_BASE_MODULE_MAP = {
    "法律": "法律",
    "法律常识": "法律",
    "法理学": "法律",
    "宪法": "法律",
    "民法": "法律",
    "民法典": "法律",
    "刑法": "法律",
    "行政法": "法律",
    "劳动法": "法律",
    "政治": "政治",
    "马哲": "政治",
    "马克思主义": "政治",
    "辩证法": "政治",
    "唯物论": "政治",
    "时政": "政治",
    "中国特色社会主义": "政治",
    "经济": "经济",
    "市场经济": "经济",
    "宏观经济": "经济",
    "微观经济": "经济",
    "财政": "经济",
    "货币": "经济",
    "管理": "管理",
    "行政管理": "管理",
    "公共管理": "管理",
    "组织协调": "管理",
    "决策": "管理",
    "科技": "科技人文",
    "科技常识": "科技人文",
    "自然科学": "科技人文",
    "物理": "科技人文",
    "化学": "科技人文",
    "生物": "科技人文",
    "科技人文": "科技人文",
    "历史": "历史文化",
    "历史文化": "历史文化",
    "中国历史": "历史文化",
    "世界历史": "历史文化",
    "公文": "公文",
    "公文写作": "公文",
    "公文处理": "公文",
    "公文格式": "公文",
}

APTITUDE_MODULE_MAP = {
    "言语": "言语",
    "言语理解": "言语",
    "言语理解与表达": "言语",
    "逻辑填空": "言语",
    "片段阅读": "言语",
    "语句表达": "言语",
    "判断": "判断",
    "判断推理": "判断",
    "逻辑判断": "判断",
    "定义判断": "判断",
    "类比推理": "判断",
    "图形推理": "判断",
    "事件排序": "判断",
    "数量": "数量",
    "数量关系": "数量",
    "数学运算": "数量",
    "工程问题": "数量",
    "行程问题": "数量",
    "利润问题": "数量",
    "资料": "资料",
    "资料分析": "资料",
    "统计图表": "资料",
    "增长率": "资料",
    "比重": "资料",
    "平均数": "资料",
    "常识": "常识",
    "常识判断": "常识",
    "综合常识": "常识",
}

PUBLIC_BASE_MODULES = set(PUBLIC_BASE_MODULE_MAP.values())
APTITUDE_MODULES = set(APTITUDE_MODULE_MAP.values())
ALL_MODULE_MAP = {**PUBLIC_BASE_MODULE_MAP, **APTITUDE_MODULE_MAP}

DIFFICULTY_MAP = {
    "基础": "基础",
    "简单": "基础",
    "入门": "基础",
    "中等": "中等",
    "普通": "中等",
    "常规": "中等",
    "提高": "提高",
    "偏难": "提高",
    "冲刺": "提高",
}

PROVINCES = {
    "北京",
    "天津",
    "上海",
    "重庆",
    "河北",
    "山西",
    "辽宁",
    "吉林",
    "黑龙江",
    "江苏",
    "浙江",
    "安徽",
    "福建",
    "江西",
    "山东",
    "河南",
    "湖北",
    "湖南",
    "广东",
    "海南",
    "四川",
    "贵州",
    "云南",
    "陕西",
    "甘肃",
    "青海",
    "台湾",
    "内蒙古",
    "广西",
    "西藏",
    "宁夏",
    "新疆",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize imported public-exam reference items into JSONL.")
    parser.add_argument("input", help="Imported JSONL path.")
    parser.add_argument("--output", required=True, help="Normalized JSONL path.")
    parser.add_argument("--default-exam-type", default="省考", help="Fallback exam type.")
    parser.add_argument("--default-difficulty", default="中等", help="Fallback difficulty.")
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
            records.append(record)
    return records


def clean_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).replace("\ufeff", "").replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.split("\n")]
    return "\n".join(line for line in lines if line).strip()


def normalize_exam_type(value: object, default_exam_type: str) -> str:
    text = clean_text(value)
    if not text:
        return default_exam_type
    return EXAM_MAP.get(text, text if text in EXAM_MAP.values() else default_exam_type)


def normalize_subject(
    value: object,
    module_value: object,
    subtype_value: object,
    stem: str,
    analysis: str,
    exam_type: str,
) -> str:
    text = clean_text(value)
    if text:
        return SUBJECT_MAP.get(text, text if text in SUBJECT_MAP.values() else infer_subject(module_value, subtype_value, stem, analysis, exam_type))
    return infer_subject(module_value, subtype_value, stem, analysis, exam_type)


def normalize_module(value: object, subtype_value: object, stem: str, analysis: str, subject: str) -> str:
    text = clean_text(value)
    normalized = normalize_leaf_module(text)
    if normalized:
        return normalized

    subtype_module = normalize_leaf_module(subtype_value)
    if subtype_module:
        return subtype_module

    if text in SUBJECT_MAP or text in SUBJECT_MAP.values():
        return infer_module(stem, analysis, subject)

    if text:
        return infer_module(stem, analysis, subject)

    return infer_module(stem, analysis, subject)


def normalize_difficulty(value: object, default_difficulty: str) -> str:
    text = clean_text(value)
    if not text:
        return default_difficulty
    return DIFFICULTY_MAP.get(text, text if text in DIFFICULTY_MAP.values() else default_difficulty)


def normalize_province(value: object) -> str:
    text = clean_text(value)
    if not text:
        return ""
    if text.endswith("省") or text.endswith("市"):
        text = text[:-1]
    if text.endswith("自治区"):
        text = text.replace("自治区", "")
    return text if text in PROVINCES else clean_text(value)


def normalize_answer(value: object) -> str:
    text = clean_text(value).upper()
    if not text:
        return ""
    match = re.search(r"[A-F]", text)
    return match.group(0) if match else ""


def normalize_string_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        items = [clean_text(item) for item in value]
    else:
        text = clean_text(value)
        if not text:
            return []
        items = [item.strip() for item in re.split(r"[,，;；/、\|]", text)]
    deduped: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item and item not in seen:
            deduped.append(item)
            seen.add(item)
    return deduped


def normalize_options(record: dict[str, object]) -> dict[str, str]:
    options = record.get("options", {})
    result: dict[str, str] = {}
    if isinstance(options, dict):
        for key, value in options.items():
            letter = clean_text(key).upper()
            if re.fullmatch(r"[A-F]", letter):
                result[letter] = clean_text(value)
    elif isinstance(options, list):
        for index, value in enumerate(options):
            letter = chr(ord("A") + index)
            result[letter] = clean_text(value)
    for letter in "ABCDEF":
        for key in (letter, letter.lower(), f"option_{letter.lower()}", f"选项{letter}"):
            if key in record and clean_text(record[key]):
                result[letter] = clean_text(record[key])
    return {key: value for key, value in sorted(result.items()) if value}


def normalize_leaf_module(value: object) -> str:
    text = clean_text(value)
    if not text:
        return ""
    return ALL_MODULE_MAP.get(text, text if text in PUBLIC_BASE_MODULES or text in APTITUDE_MODULES else "")


def infer_subject(module_value: object, subtype_value: object, stem: str, analysis: str, exam_type: str) -> str:
    for raw_value in (module_value, subtype_value):
        text = clean_text(raw_value)
        if not text:
            continue
        if text in SUBJECT_MAP:
            return SUBJECT_MAP[text]
        if text in SUBJECT_MAP.values():
            return text
        normalized = normalize_leaf_module(text)
        if normalized in PUBLIC_BASE_MODULES:
            return "公基"
        if normalized in APTITUDE_MODULES:
            return "职测"

    text = f"{stem}\n{analysis}"
    if any(
        token in text
        for token in (
            "填入画横线部分",
            "最恰当",
            "最符合文意",
            "主旨",
            "这段文字",
            "语句排序",
            "定义",
            "类比",
            "推出",
            "削弱",
            "加强",
            "排序",
            "增长率",
            "同比",
            "环比",
            "比重",
            "平均数",
            "表中",
            "材料中",
            "现期",
            "基期",
            "工程队",
            "甲乙合作",
            "行程",
            "利润",
            "打折",
            "速度",
            "路程",
            "概率",
        )
    ):
        return "职测"
    if any(
        token in text
        for token in (
            "宪法",
            "民法典",
            "民法",
            "行政法",
            "刑法",
            "劳动法",
            "马克思主义",
            "辩证法",
            "唯物论",
            "中国特色社会主义",
            "市场经济",
            "财政",
            "货币",
            "行政管理",
            "公共管理",
            "科技",
            "历史文化",
            "公文",
        )
    ):
        return "公基"
    if exam_type in {"国考", "省考"}:
        return "职测"
    return "公基"


def infer_module(stem: str, analysis: str, subject: str) -> str:
    text = f"{stem}\n{analysis}"
    if subject == "职测":
        if any(token in text for token in ("增长率", "同比", "环比", "比重", "平均数", "倍数", "表中", "材料中", "现期", "基期")):
            return "资料"
        if any(token in text for token in ("填入画横线部分", "最恰当", "最符合文意", "主旨", "这段文字", "语句排序")):
            return "言语"
        if any(token in text for token in ("工程队", "甲乙合作", "行程", "利润", "打折", "速度", "路程", "概率", "排列组合")):
            return "数量"
        if any(token in text for token in ("定义", "类比", "推出", "削弱", "加强", "排序", "甲乙丙", "根据上述", "图形")):
            return "判断"
        if any(
            token in text
            for token in (
                "宪法",
                "民法典",
                "行政法",
                "刑法",
                "科技",
                "历史",
                "文化",
                "地理",
                "哲学",
                "经济",
            )
        ):
            return "常识"
        return "判断"

    if any(token in text for token in ("宪法", "民法典", "民法", "行政法", "刑法", "劳动法", "侵权责任", "物权", "合同")):
        return "法律"
    if any(token in text for token in ("马克思主义", "哲学", "辩证法", "唯物论", "中国特色社会主义", "国家机构", "人民代表大会")):
        return "政治"
    if any(token in text for token in ("市场经济", "财政", "货币", "供求", "税收", "宏观调控", "微观经济")):
        return "经济"
    if any(token in text for token in ("行政管理", "公共管理", "组织协调", "决策", "绩效管理", "领导风格", "激励")):
        return "管理"
    if any(token in text for token in ("公文", "发文字号", "行文规则", "文种", "请示", "通知", "报告")):
        return "公文"
    if any(token in text for token in ("商鞅", "科举", "造纸术", "火药", "指南针", "朝代", "历史文化")):
        return "历史文化"
    return "科技人文"


def infer_subtype(subject: str, module: str, stem: str, analysis: str) -> str:
    text = f"{stem}\n{analysis}"
    if subject == "职测" and module == "言语":
        if "填入画横线部分" in text or "最恰当的一项" in text:
            return "逻辑填空"
        if "主旨" in text or "这段文字意在说明" in text:
            return "片段阅读"
        return "语句表达"
    if subject == "职测" and module == "判断":
        if "定义" in text and ("属于" in text or "不属于" in text):
            return "定义判断"
        if "类比" in text or re.search(r"[A-Za-z\u4e00-\u9fa5]+[:：][A-Za-z\u4e00-\u9fa5]+", text):
            return "类比推理"
        if "排序" in text or "先后顺序" in text:
            return "事件排序"
        return "逻辑判断"
    if subject == "职测" and module == "数量":
        if "工程" in text or "合作" in text:
            return "工程问题"
        if "路程" in text or "速度" in text or "相遇" in text:
            return "行程问题"
        if "利润" in text or "成本" in text or "售价" in text or "打折" in text:
            return "利润问题"
        return "数学运算"
    if subject == "职测" and module == "资料":
        if "增长率" in text or "同比" in text or "环比" in text:
            return "增长率"
        if "比重" in text:
            return "比重"
        if "平均" in text:
            return "平均数"
        return "倍数与差值"
    if subject == "职测" and module == "常识":
        if any(token in text for token in ("宪法", "民法典", "行政法", "刑法", "劳动法")):
            return "法律常识"
        if any(token in text for token in ("马克思主义", "哲学", "中国特色社会主义", "国家机构")):
            return "政治常识"
        if any(token in text for token in ("商鞅", "科举", "造纸术", "火药", "指南针", "历史", "文化")):
            return "历史人文"
        if any(token in text for token in ("科技", "物理", "化学", "生物", "地理")):
            return "科技常识"
        return "常识判断"
    if subject == "公基" and module == "法律":
        if any(token in text for token in ("宪法", "民法典", "行政法", "刑法", "法律")):
            if "宪法" in text:
                return "宪法"
            if "民法典" in text or "民法" in text:
                return "民法"
            if "行政法" in text:
                return "行政法"
            if "刑法" in text:
                return "刑法"
            if "劳动法" in text:
                return "劳动法"
        return "法律"
    if subject == "公基" and module == "政治":
        if any(token in text for token in ("马克思主义", "哲学", "辩证法", "唯物论")):
            return "马克思主义哲学"
        if "中国特色社会主义" in text:
            return "中国特色社会主义"
        if any(token in text for token in ("国家机构", "人民代表大会", "民族区域自治")):
            return "国家制度"
        return "政治"
    if subject == "公基" and module == "经济":
        if any(token in text for token in ("宏观调控", "财政", "货币", "税收")):
            return "宏观经济"
        if any(token in text for token in ("供求", "成本", "收益", "弹性")):
            return "微观经济"
        return "经济"
    if subject == "公基" and module == "管理":
        if any(token in text for token in ("行政管理", "行政组织", "行政执行")):
            return "行政管理"
        if any(token in text for token in ("公共管理", "危机管理", "绩效管理")):
            return "公共管理"
        if any(token in text for token in ("马斯洛", "赫茨伯格", "领导风格", "激励")):
            return "组织行为"
        return "管理"
    if subject == "公基" and module == "科技人文":
        if any(token in text for token in ("科技", "人工智能", "物理", "化学", "生物")):
            return "科技常识"
        if any(token in text for token in ("地理", "气候", "资源", "环境")):
            return "地理常识"
        return "科技人文"
    if subject == "公基" and module == "历史文化":
        return "历史文化"
    if subject == "公基" and module == "公文":
        return "公文"
    return module


def infer_pattern_tags(exam_type: str, subject: str, province: str, module: str, subtype: str, difficulty: str) -> list[str]:
    tags = [exam_type, subject, module, subtype, difficulty]
    if province:
        tags.append(province)
    if subtype == "定义判断":
        tags.append("要件比对")
    elif subtype == "逻辑填空":
        tags.append("语境对应")
    elif subtype == "工程问题":
        tags.append("设总量")
    elif subtype == "增长率":
        tags.append("现期基期")
    elif module == "法律":
        tags.append("法条边界")
    return tags


def merge_tags(primary: list[str], secondary: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for item in primary + secondary:
        if item and item not in seen:
            merged.append(item)
            seen.add(item)
    return merged


def infer_reasoning_path(subject: str, module: str, subtype: str) -> list[str]:
    if subtype == "定义判断":
        return ["提取定义要件", "逐项比对选项", "排除缺失或超出的选项"]
    if subtype == "逻辑填空":
        return ["识别上下文语义", "比较词语搭配和感情色彩", "代入验证语义是否连贯"]
    if subtype == "工程问题":
        return ["设总量为1", "列出效率关系", "求未知量并匹配选项"]
    if subtype == "增长率":
        return ["提取现期与基期数据", "列式计算增长率", "估算并匹配最接近选项"]
    if module == "法律":
        return ["定位对应法律规则", "比较主体条件和法律后果", "排除绝对化或主体错配表述"]
    if subject == "职测" and module == "判断":
        return ["识别核心关系", "逐项比较", "排除迷惑项"]
    if subject == "职测" and module == "数量":
        return ["设元或设总量", "列方程", "求解并验算"]
    if subject == "职测" and module == "资料":
        return ["提取数据", "列式", "估算比较"]
    if subject == "职测" and module == "言语":
        return ["识别语境", "比较选项", "代入验证"]
    if subject == "职测" and module == "常识":
        return ["定位稳定常识考点", "逐项排除明显错误表述", "确定唯一正确答案"]
    return ["定位考点", "逐项比较", "确定唯一答案"]


def infer_distractor_style(subject: str, module: str, subtype: str) -> list[str]:
    if subtype == "定义判断":
        return ["缺少关键要件", "主体不符", "外延过宽"]
    if subtype == "逻辑填空":
        return ["近义词混淆", "搭配不当", "感情色彩错位"]
    if subtype == "工程问题":
        return ["效率关系误用", "时间相加错误", "方程设错"]
    if subtype == "增长率":
        return ["把增长量当增长率", "基期用错", "口径混淆"]
    if module == "法律":
        return ["主体混淆", "条件缺失", "绝对化表述"]
    if subject == "公基":
        return ["概念偷换", "范围张冠李戴", "因果关系错位"]
    return ["表面相似", "条件错位", "逻辑不成立"]


def build_id(stem: str, subject: str, module: str, subtype: str) -> str:
    digest = hashlib.sha1(stem.encode("utf-8")).hexdigest()[:10]
    return f"gk-{subject}-{module}-{subtype}-{digest}"


def normalize_record(record: dict[str, object], default_exam_type: str, default_difficulty: str) -> dict[str, object]:
    stem = clean_text(record.get("stem"))
    analysis = clean_text(record.get("analysis"))
    exam_type = normalize_exam_type(record.get("exam_type"), default_exam_type)
    province = normalize_province(record.get("province"))
    subject = normalize_subject(record.get("subject"), record.get("module"), record.get("subtype"), stem, analysis, exam_type)
    module = normalize_module(record.get("module"), record.get("subtype"), stem, analysis, subject)
    subtype = clean_text(record.get("subtype")) or infer_subtype(subject, module, stem, analysis)
    difficulty = normalize_difficulty(record.get("difficulty"), default_difficulty)
    options = normalize_options(record)
    answer = normalize_answer(record.get("answer"))
    source_type = clean_text(record.get("source_type")) or "unknown"
    inferred_tags = infer_pattern_tags(exam_type, subject, province, module, subtype, difficulty)
    pattern_tags = merge_tags(
        inferred_tags,
        normalize_string_list(record.get("pattern_tags")),
    )
    reasoning_path = normalize_string_list(record.get("reasoning_path")) or infer_reasoning_path(subject, module, subtype)
    distractor_style = normalize_string_list(record.get("distractor_style")) or infer_distractor_style(subject, module, subtype)
    normalized = {
        "id": clean_text(record.get("id")) or build_id(stem, subject, module, subtype),
        "exam_type": exam_type,
        "subject": subject,
        "province": province,
        "module": module,
        "subtype": subtype,
        "difficulty": difficulty,
        "stem": stem,
        "options": options,
        "answer": answer,
        "analysis": analysis,
        "source_type": source_type,
        "pattern_tags": pattern_tags,
        "reasoning_path": reasoning_path,
        "distractor_style": distractor_style,
    }
    source_path = clean_text(record.get("source_path"))
    if source_path:
        normalized["source_path"] = source_path
    return normalized


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
        records = load_jsonl(Path(args.input))
        normalized = [
            normalize_record(record, args.default_exam_type, args.default_difficulty)
            for record in records
        ]
        count = write_jsonl(normalized, Path(args.output))
    except Exception as exc:  # noqa: BLE001
        print(f"[normalize] failed: {exc}", file=sys.stderr)
        return 1

    print(f"[normalize] wrote {count} records to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
