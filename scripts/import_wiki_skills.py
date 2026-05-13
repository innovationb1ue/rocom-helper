"""从 wiki 技能数据导入精灵可学技能到 pet_skill_map.json。

数据源: references/NRC_AI/data/raw/skills_wiki.csv
  - 每行一个技能，包含"可学习精灵"列（用 | 分隔精灵名）
  - 精灵名可能带后缀如"（xxx的样子）"，需去掉后缀匹配

合并策略:
  - 通过 pet_map.json 的 name 字段反查 base_id
  - 通过 skill_map.json 的 name 字段反查 skill_id
  - 为已有精灵补充新技能（不覆盖已有的 level_skills）
  - 为 pet_skill_map 中空缺的精灵填充数据

用法:
    py -m scripts.import_wiki_skills              # 预览模式（不写入）
    py -m scripts.import_wiki_skills --apply      # 写入结果
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PET_MAP_PATH = PROJECT_ROOT / "data" / "game" / "pet_map.json"
SKILL_MAP_PATH = PROJECT_ROOT / "data" / "game" / "skill_map.json"
PET_SKILL_MAP_PATH = PROJECT_ROOT / "data" / "game" / "pet_skill_map.json"
WIKI_SKILLS_PATH = PROJECT_ROOT / "references" / "NRC_AI" / "data" / "raw" / "skills_wiki.csv"


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def build_name_to_base_id(pet_map: dict) -> Dict[str, int]:
    """构建 精灵名 → base_id 映射（取第一个出现的）。"""
    name_to_base: Dict[str, int] = {}
    for v in pet_map.values():
        name = v.get("name", "")
        bid = v.get("base_id")
        if name and bid and name not in name_to_base:
            name_to_base[name] = int(bid)
    return name_to_base


def build_name_to_skill_id(skill_map: dict) -> Dict[str, int]:
    """构建 技能名 → skill_id 映射。"""
    return {
        v.get("name", ""): int(k)
        for k, v in skill_map.items()
        if v.get("name")
    }


def strip_variant_suffix(pet_name: str) -> str:
    """去掉精灵名中的形态后缀，如'喵喵（草系的样子）'→'喵喵'。"""
    return re.sub(r"（.*?）", "", pet_name).strip()


def parse_wiki_skills(path: Path) -> List[Tuple[str, List[str]]]:
    """解析 skills_wiki.csv，返回 [(skill_name, [pet_name, ...]), ...]。"""
    results = []
    with path.open("r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            skill_name = row.get("技能名", "").strip()
            pets_raw = row.get("可学习精灵", "")
            pet_names = []
            for raw in pets_raw.split("|"):
                pet = raw.strip()
                if not pet or pet.startswith("展开全部"):
                    continue
                clean = strip_variant_suffix(pet)
                if clean:
                    pet_names.append(clean)
            if skill_name and pet_names:
                results.append((skill_name, pet_names))
    return results


def merge_wiki_skills(
    pet_skill_map: dict,
    wiki_data: List[Tuple[str, List[str]]],
    name_to_base: Dict[str, int],
    name_to_skill: Dict[str, int],
) -> Tuple[int, int, int]:
    """合并 wiki 技能数据到 pet_skill_map。

    Returns:
        (new_entries, new_skill_entries, pets_touched)
    """
    new_entries = 0
    new_skill_entries = 0
    pets_touched: Set[str] = set()
    unmatched_skills = 0
    unmatched_pets = 0

    for skill_name, pet_names in wiki_data:
        skill_id = name_to_skill.get(skill_name)
        if not skill_id:
            unmatched_skills += 1
            continue

        for pet_name in pet_names:
            base_id = name_to_base.get(pet_name)
            if not base_id:
                unmatched_pets += 1
                continue

            bid_str = str(base_id)
            # 确保 pet_skill_map 中有该条目
            if bid_str not in pet_skill_map:
                pet_skill_map[bid_str] = {
                    "id": base_id,
                    "editor_name": pet_name,
                    "level_skills": [],
                }
                new_entries += 1

            entry = pet_skill_map[bid_str]
            if "level_skills" not in entry or entry["level_skills"] is None:
                entry["level_skills"] = []

            # 检查是否已有该技能
            existing_ids = {s.get("skill_id") for s in entry["level_skills"]}
            if skill_id not in existing_ids:
                entry["level_skills"].append({
                    "level_gain_skill": 2,  # 2 = wiki 来源（区别于 1 = 升级学习）
                    "level_point": 0,
                    "skill_id": skill_id,
                    "stage": 0,
                })
                new_skill_entries += 1
                pets_touched.add(bid_str)

    if unmatched_skills:
        print(f"  [info] {unmatched_skills} 个技能名未在 skill_map 中匹配")
    if unmatched_pets:
        print(f"  [info] {unmatched_pets} 次精灵名未在 pet_map 中匹配")

    return new_entries, new_skill_entries, len(pets_touched)


def count_coverage(pet_skill_map: dict) -> Tuple[int, int, int]:
    """统计覆盖情况: (有技能的条目数, 无技能的条目数, 总技能条目数)。"""
    with_skills = 0
    without_skills = 0
    total_entries = 0
    for v in pet_skill_map.values():
        ls = v.get("level_skills")
        if ls and len(ls) > 0:
            with_skills += 1
            total_entries += len(ls)
        else:
            without_skills += 1
    return with_skills, without_skills, total_entries


def main() -> None:
    parser = argparse.ArgumentParser(description="从 wiki 导入精灵可学技能")
    parser.add_argument("--apply", action="store_true", help="写入结果（默认仅预览）")
    args = parser.parse_args()

    print("[1/5] 加载数据文件...")
    pet_map = load_json(PET_MAP_PATH)
    skill_map = load_json(SKILL_MAP_PATH)
    pet_skill_map = load_json(PET_SKILL_MAP_PATH)

    before_with, before_without, before_total = count_coverage(pet_skill_map)
    print(f"  当前: {before_with} 个精灵有技能, {before_without} 个无技能, 共 {before_total} 条技能")

    print("[2/5] 构建名称映射...")
    name_to_base = build_name_to_base_id(pet_map)
    name_to_skill = build_name_to_skill_id(skill_map)
    print(f"  精灵名→base_id: {len(name_to_base)} 条")
    print(f"  技能名→skill_id: {len(name_to_skill)} 条")

    print("[3/5] 解析 wiki 技能数据...")
    wiki_data = parse_wiki_skills(WIKI_SKILLS_PATH)
    print(f"  解析到 {len(wiki_data)} 个技能的学习列表")

    print("[4/5] 合并数据...")
    new_entries, new_skill_entries, pets_touched = merge_wiki_skills(
        pet_skill_map, wiki_data, name_to_base, name_to_skill
    )
    print(f"  新增精灵条目: {new_entries}")
    print(f"  新增技能条目: {new_skill_entries}")
    print(f"  涉及精灵数: {pets_touched}")

    after_with, after_without, after_total = count_coverage(pet_skill_map)
    print(f"\n  合并后: {after_with} 个精灵有技能, {after_without} 个无技能, 共 {after_total} 条技能")
    print(f"  覆盖率: {before_with}/796 → {after_with}/796")
    print(f"  技能条目: {before_total} → {after_total} (+{after_total - before_total})")

    if args.apply:
        print("[5/5] 写入 pet_skill_map.json...")
        with PET_SKILL_MAP_PATH.open("w", encoding="utf-8") as f:
            json.dump(pet_skill_map, f, ensure_ascii=False, indent=2)
        print("  写入完成。")
    else:
        print("[5/5] 预览模式，未写入。使用 --apply 写入结果。")


if __name__ == "__main__":
    main()
