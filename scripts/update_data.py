"""精灵/技能增量更新脚本 — 从 BWIKI 拉取最新数据并做增量更新。

用法:
    python -m scripts.update_data                     # 全量拉取+diff+交互确认
    python -m scripts.update_data --fetch-only        # 仅拉取保存
    python -m scripts.update_data --diff              # 对比已有数据输出 diff
    python -m scripts.update_data --apply             # 直接应用（跳过确认）
    python -m scripts.update_data --dry-run           # 拉取+diff 不写入
    python -m scripts.update_data --skip-details      # 跳过精灵详情抓取
"""
from __future__ import annotations

import argparse
import logging
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_PETS_PATH = str(_PROJECT_ROOT / "data" / "game" / "wiki_pets.json")
_SKILLS_PATH = str(_PROJECT_ROOT / "data" / "game" / "wiki_skills.json")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


def main() -> None:
    args = parse_args()

    from scripts.mappers import load_type_map, map_pets, map_skills
    from scripts.differ import (
        ChangeType, compute_diff, format_diff, format_skill_diff,
        apply_diff, load_indexed, save_json,
    )
    from scripts.wiki_client import fetch_all_pets, fetch_all_skills, fetch_pet_details

    type_map = load_type_map()

    # --- 拉取或加载 ---
    if args.diff:
        log.info("--diff 模式: 使用已有 wiki 数据，不拉取")
        pets = list(load_indexed(_PETS_PATH).values())
        skills = list(load_indexed(_SKILLS_PATH).values())
        details = {}
    else:
        log.info("[1/4] 从 BWIKI 拉取精灵列表...")
        wiki_pets_raw = fetch_all_pets()

        log.info("[2/4] 拉取精灵详情（技能关联）...")
        details = fetch_pet_details(wiki_pets_raw, skip=args.skip_details)

        log.info("[3/4] 从 BWIKI 拉取技能列表...")
        wiki_skills_raw = fetch_all_skills()

        # 映射
        pets, skipped = map_pets(wiki_pets_raw, type_map, details)
        if skipped:
            log.warning("跳过 %d 只精灵（未知属性）: %s", len(skipped), ", ".join(skipped[:10]))
        skills = map_skills(wiki_skills_raw, type_map)

    # 索引
    new_pets_idx = {p["wiki_name"]: p for p in pets if p.get("wiki_name")}
    new_skills_idx = {s["wiki_name"]: s for s in skills if s.get("wiki_name")}

    # --- Diff ---
    log.info("[4/4] 计算增量 diff...")
    existing_pets = load_indexed(_PETS_PATH)
    existing_skills = load_indexed(_SKILLS_PATH)

    pet_changes = compute_diff(existing_pets, new_pets_idx)
    skill_changes = compute_diff(existing_skills, new_skills_idx)

    print(format_diff(pet_changes, "精灵数据变更 (wiki_pets.json)"))
    print(format_skill_diff(skill_changes, "技能数据变更 (wiki_skills.json)"))

    has_changes = any(
        c.change_type in (ChangeType.ADDED, ChangeType.MODIFIED)
        for c in pet_changes + skill_changes
    )

    # --- 决策 ---
    if args.dry_run:
        log.info("--dry-run: 不写入文件")
        return

    if args.apply or args.fetch_only:
        do_apply = True
    else:
        if not has_changes:
            log.info("无新增/修改，无需应用。")
            return
        answer = input("\n是否应用以上变更？[y/N/detail]: ").strip().lower()
        if answer == "detail":
            _print_detail(pet_changes, skill_changes)
            answer = input("\n应用？[y/N]: ").strip().lower()
        do_apply = answer in ("y", "yes")

    if not do_apply:
        log.info("未确认，跳过写入。")
        return

    # --- 写入 ---
    final_pets = apply_diff(existing_pets, pet_changes)
    final_skills = apply_diff(existing_skills, skill_changes)

    save_json(_PETS_PATH, list(final_pets.values()))
    save_json(_SKILLS_PATH, list(final_skills.values()))
    log.info("写入完成: wiki_pets.json (%d 条), wiki_skills.json (%d 条)",
             len(final_pets), len(final_skills))


def _print_detail(pet_changes, skill_changes):
    from scripts.differ import ChangeType
    for c in pet_changes + skill_changes:
        if c.change_type == ChangeType.MODIFIED:
            print(f"\n  {c.name}:")
            for d in c.field_diffs:
                print(f"    {d.field}: {d.old_val!r} → {d.new_val!r}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="精灵/技能增量更新脚本")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--fetch-only", action="store_true", help="仅拉取保存，不交互确认")
    g.add_argument("--diff", action="store_true", help="仅对比已有数据输出 diff")
    g.add_argument("--apply", action="store_true", help="直接应用，跳过确认")
    g.add_argument("--dry-run", action="store_true", help="拉取+diff，不写入文件")
    p.add_argument("--skip-details", action="store_true",
                   help="跳过精灵详情抓取（不获取技能关联）")
    return p.parse_args()


if __name__ == "__main__":
    main()
