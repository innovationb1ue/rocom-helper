"""从 BinData JSON 文件导入游戏数据到项目 data/game/ 目录。

参考 rocom.aoe.top 的 export_pet_json.py 和 sync-pet-data.mjs 的数据处理逻辑。

用法:
    py -m scripts.import_bin_data <bdata_dir> [--output-dir <dir>] [--dry-run]

    bdata_dir: 已解码的 BinData JSON 目录（如 references/Roco-Kingdom-World-Data/Bin/BinDataCompressed/）

    --output-dir: 输出目录，默认 data/game/
    --dry-run: 不写入文件，仅打印变更摘要

示例:
    # 用现有 reference 数据测试
    py -m scripts.import_bin_data references/Roco-Kingdom-World-Data/Bin/BinDataCompressed --dry-run

    # 实际导入新数据
    py -m scripts.import_bin_data /path/to/new/BinDataCompressed --output-dir data/game/
"""
from __future__ import annotations

import argparse
import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Tuple

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_OUTPUT = _PROJECT_ROOT / "data" / "game"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ── 类型 ID 映射 ──────────────────────────────────────────────
# BinData TYPE_DICTIONARY 的 raw ID → 当前项目 type_chart.json 的 ID
# 映射通过 name 匹配完成，在 _build_type_map() 中动态构建

# BinData 技能 type 字段值: 1=主动, 2=被动
# BinData 技能 damage_type: 1=物理, 2=特殊/魔法
# BinData 技能 skill_dam_type: 技能自身的属性类型(raw type ID)

# ── 工具函数 ─────────────────────────────────────────────────

def load_bin_table(dir_path: Path, name: str) -> Dict[str, Any]:
    """加载 BinData JSON 表，返回 RocoDataRows 字典。"""
    path = dir_path / f"{name}.json"
    if not path.exists():
        log.warning("BinData 表不存在: %s", path)
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("RocoDataRows", {})


def load_project_json(path: Path) -> dict:
    """加载项目现有 JSON 数据文件。"""
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: Any) -> None:
    """保存 JSON 文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    log.info("写入: %s (%s)", path.name, _size_str(data))


def _size_str(data: Any) -> str:
    if isinstance(data, dict):
        return f"{len(data)} 条"
    elif isinstance(data, list):
        return f"{len(data)} 条"
    return "ok"


def clean_text(val: Any) -> Optional[str]:
    """清洗文本：去处HTML标签、合并空白、返回 None 如果为空。"""
    if not isinstance(val, str):
        return None
    val = re.sub(r"<[^>]*>", "", val)
    val = val.replace("\r\n", "\n").replace("\r", "\n")
    val = re.sub(r"\s+", " ", val).strip()
    return val or None


def normalize_array(val: Any) -> list:
    """标准化为数组。"""
    if val is None:
        return []
    if isinstance(val, list):
        return val
    return [val]


def first_numeric(val: Any) -> Optional[int]:
    """取第一个数字值。"""
    if isinstance(val, (int, float)):
        return int(val)
    if isinstance(val, list):
        for v in val:
            if isinstance(v, (int, float)):
                return int(v)
    return None


# ── 类型映射构建 ─────────────────────────────────────────────

def build_type_map(bdata_dir: Path, project_dir: Path) -> Dict[int, int]:
    """构建 BinData raw type ID → 项目 type ID 的映射。

    通过 TYPE_DICTIONARY 的 type_name 与项目 type_chart.json 的 name 匹配。
    """
    type_dict = load_bin_table(bdata_dir, "TYPE_DICTIONARY")
    type_chart = load_project_json(project_dir / "type_chart.json")

    # 项目 type name → id
    proj_name_to_id: Dict[str, int] = {}
    for t in type_chart.get("types", []):
        proj_name_to_id[t["name"]] = t["id"]

    # BinData raw id → type_name
    raw_to_name: Dict[int, str] = {}
    for k, v in type_dict.items():
        raw_to_name[int(k)] = v.get("type_name", "")

    # 匹配
    mapping: Dict[int, int] = {}
    # 直接名称匹配（BinData type_name → 项目 name）
    # type_name 可能是 "火系"（带"系"后缀）或 "草"（直接名称）
    # 注意："地"（raw_id=3）、"无系别"（raw_id=1）需要单独处理
    name_match_map = {
        "普通系": "普通",
        "火系": "火",
        "水系": "水",
        "草系": "草",
        "电系": "电",
        "冰系": "冰",
        "武系": "武",
        "毒系": "毒",
        "地系": "地",
        "翼系": "翼",
        "萌系": "萌",
        "幻系": "幻",
        "虫系": "虫",
        "幽系": "幽",
        "机械系": "机械",
        "龙系": "龙",
        "恶系": "恶",
        "光系": "光",
        # 直接名称（无"系"后缀）
        "普通": "普通",
        "草": "草",
        "火": "火",
        "水": "水",
        "光": "光",
        "土": "土",
        "冰": "冰",
        "龙": "龙",
        "电": "电",
        "毒": "毒",
        "虫": "虫",
        "武": "武",
        "飞": "翼",
        "萌": "萌",
        "暗": "恶",
        "幻": "幻",
        "机械": "机械",
        "鬼": "幽",
        # 地（raw_id=3）
        "地": "土",
    }

    for raw_id, type_name in raw_to_name.items():
        proj_name = name_match_map.get(type_name)        # "火系" → "火"
        if proj_name and proj_name in proj_name_to_id:
            mapping[raw_id] = proj_name_to_id[proj_name]  # raw_id=4 → proj_id=4

    log.info("类型映射: %d 个 raw ID → 项目 ID", len(mapping))
    for raw_id, proj_id in sorted(mapping.items()):
        log.debug("  raw %d (%s) → project %d (%s)",
                  raw_id, raw_to_name.get(raw_id, "?"),
                  proj_id, [t["name"] for t in type_chart.get("types", []) if t["id"] == proj_id][0])

    return mapping


# ── 血系类型名 → raw type ID (18 血系对应 18 个属性) ──────

BLOOD_TYPE_NAMES = [
    "COMMON", "GRASS", "FIRE", "WATER", "LIGHT",
    "STONE", "ICE", "DRAGON", "ELECTRIC", "TOXIC",
    "INSECT", "FIGHT", "WING", "MOE", "GHOST",
    "DEMON", "MECHANIC", "PHANTOM",
]


# ── pet_species.json 生成 (新文件, 不覆盖 pet_map) ────────────

def build_pet_species(bdata_dir: Path, type_map: Dict[int, int]) -> Dict[str, Any]:
    """从 PETBASE_CONF 构建宠物物种数据（按 base_id 索引）。

    这是新文件，不覆盖现有的 pet_map.json（pet_map 存的是实例 ID→base_id）。
    pet_species.json 存的是 base_id → 种族值/属性/特性等。
    """
    petbase = load_bin_table(bdata_dir, "PETBASE_CONF")
    result: Dict[str, Any] = {}

    # 加载 type_chart 用于 type_names 填充
    type_chart = load_project_json(_DEFAULT_OUTPUT / "type_chart.json")
    id_to_name = {t["id"]: t["name"] for t in type_chart.get("types", [])}

    for k, row in petbase.items():
        pid = row.get("id")
        if not pid:
            continue

        pid_str = str(pid)
        name = clean_text(row.get("name")) or ""

        # 类型: unit_type 是 raw type ID 数组
        raw_types = normalize_array(row.get("unit_type", []))
        # 映射：尝试用 type_map，若无映射则保留原始值（fallback to original type system）
        types = []
        for rt in raw_types:
            if rt in type_map:
                types.append(type_map[rt])
            else:
                # 无映射时直接用原始值（部分 BinData type ID 与项目 ID 重叠）
                types.append(rt)
        type_names = [id_to_name.get(t, "") for t in types]

        # 种族值
        stats = {
            "hp": row.get("hp_max_race", 0) or 0,
            "atk": row.get("phy_attack_race", 0) or 0,
            "spa": row.get("spe_attack_race", 0) or 0,
            "def": row.get("phy_defence_race", 0) or 0,
            "spd": row.get("spe_defence_race", 0) or 0,
            "spe": row.get("speed_race", 0) or 0,
            "sum": row.get("SUM_race", 0) or 0,
        }

        # 攻击风格
        atk_diff = stats["atk"] - stats["spa"]
        if abs(atk_diff) <= 10:
            attack_style = "Both"
        elif atk_diff > 0:
            attack_style = "Physical"
        else:
            attack_style = "Magic"

        # 从 JL_res 提取 portrait key
        portrait_key = None
        jl_res = row.get("JL_res") or row.get("JL_small_res") or ""
        m = re.search(r"JL_(\w+)\.", str(jl_res))
        if m:
            portrait_key = m.group(1)

        # 性别比例 (0-10 scale → 0-100)
        proportion_male = row.get("proportion_male")
        male_rate = None
        female_rate = None
        if isinstance(proportion_male, (int, float)):
            if proportion_male <= 10:
                male_rate = int(proportion_male * 10)
            else:
                male_rate = int(proportion_male)
            female_rate = max(0, 100 - male_rate)

        # 实装判断
        completeness = row.get("completeness")
        has_handbook = bool(row.get("pictorial_book_id"))
        has_standpaint = bool(row.get("handbook_standpaint_bg"))
        has_egg = bool(normalize_array(row.get("egg_group", [])))
        implemented = (
            (completeness == 1)
            or (has_handbook and (completeness == 1 or has_standpaint))
            or has_egg
        )

        # 是否是 boss/队长形态
        is_boss = bool(row.get("boss_type"))
        is_leader = is_boss or bool(portrait_key and re.search(r"(_shouling|_boss)$", portrait_key or ""))

        entry = {
            "id": pid,
            "name": name,
            "types": types,
            "type_names": type_names,
            "stats": stats,
            "attack_style": attack_style,
            "quality": row.get("quality"),
            "stage": row.get("stage"),
            "max_energy": first_numeric(row.get("max_energy")) or 0,
            "evolution_ids": normalize_array(row.get("pet_evolution_id", [])),
            "evolution_pet_ids": normalize_array(row.get("evolution_pet_id", [])),
            "level_skill_conf_id": row.get("level_skill_conf_id"),
            "habit_group": row.get("belong_habit_group") or row.get("pet_habitat_group_role_type"),
            "move_type": clean_text(row.get("move_type")),
            "description": clean_text(row.get("description")),
            "portrait_key": portrait_key,
            "implemented": implemented,
            "completeness": completeness,
            "is_leader": is_leader,
            "is_boss": is_boss,
            "egg_group": normalize_array(row.get("egg_group", [])),
            "proportion_male": proportion_male,
            "male_rate": male_rate,
            "female_rate": female_rate,
            "nature_ids": normalize_array(row.get("nature_ids", [])),
            "pet_feature": row.get("pet_feature"),
            "pet_glass_feature": row.get("pet_glass_feature"),
            "pet_chaos_feature": row.get("pet_chaos_feature"),
            "pet_classis_id": row.get("pet_classis_id"),
            "talent_normal_chance": row.get("talent_normal_chance"),
            "talent_good_chance": row.get("talent_good_chance"),
            "talent_amazing_chance": row.get("talent_amazing_chance"),
            "talent_perfect_chance": row.get("talent_perfect_chance"),
            "critical_dam": row.get("critical_dam"),
            "weight_low": row.get("weight_low"),
            "weight_high": row.get("weight_high"),
            "height_low": row.get("height_low"),
            "height_high": row.get("height_high"),
            "pictorial_book_id": row.get("pictorial_book_id"),
        }

        result[pid_str] = entry

    log.info("pet_species: %d 个物种（来自 PETBASE_CONF）", len(result))
    return result


# ── pet_map.json 增强 ─────────────────────────────────────────

def enhance_pet_map(pet_map: Dict[str, Any], pet_species: Dict[str, Any]) -> Dict[str, Any]:
    """用物种数据增强现有 pet_map（添加 name/type/stats 等字段）。"""
    enhanced = {}
    for pid_str, entry in pet_map.items():
        base_id = entry.get("base_id")
        species = pet_species.get(str(base_id), {}) if base_id else {}

        enhanced[pid_str] = {
            **entry,
            "species_name": species.get("name", entry.get("name", "")),
            "species_types": species.get("types", []),
            "species_type_names": species.get("type_names", []),
            "species_stats": species.get("stats", {}),
            "species_quality": species.get("quality"),
            "species_stage": species.get("stage"),
            "species_implemented": species.get("implemented", False),
            "species_evolution_ids": species.get("evolution_ids", []),
        }

    log.info("pet_map: 已增强 %d 个实例条目", len(enhanced))
    return enhanced


# ── skill_map.json 生成 ───────────────────────────────────────

def build_skill_map(bdata_dir: Path, type_map: Dict[int, int]) -> Dict[str, Any]:
    """从 SKILL_CONF 构建增强版 skill_map。"""
    skill_conf = load_bin_table(bdata_dir, "SKILL_CONF")
    result: Dict[str, Any] = {}

    for k, row in skill_conf.items():
        sid = row.get("id")
        if not sid:
            continue

        sid_str = str(sid)
        name = clean_text(row.get("name")) or ""
        desc = clean_text(row.get("desc")) or ""

        # 技能属性类型
        raw_dam_type = row.get("skill_dam_type")
        skill_type_id = type_map.get(raw_dam_type) if raw_dam_type else None

        entry = {
            "id": sid,
            "name": name,
            "desc": desc,
            "energy_cost": normalize_array(row.get("energy_cost", [])),
            "dam_para": normalize_array(row.get("dam_para", [])),
            "type": row.get("type"),                    # 1=主动, 2=被动
            "skill_dam_type": raw_dam_type,             # raw type ID
            "skill_type_id": skill_type_id,             # 映射后的项目 type ID
            "damage_type": row.get("damage_type"),      # 1=物理, 2=特殊
            "contact_type": row.get("contact_type"),
            "skill_priority": row.get("skill_priority"),
            "target_type": row.get("target_type"),
            "target_count": row.get("target_count"),
            "cd_round": normalize_array(row.get("cd_round", [])),
            "hit_para": row.get("hit_para"),
            "skill_result": row.get("skill_result", []),
            "res_id": row.get("res_id"),
            "icon": row.get("icon"),
            "describe_type": normalize_array(row.get("describe_type", [])),
            "target_blood_limit": normalize_array(row.get("target_blood_limit", [])),
            "monitor_data_version": row.get("monitor_data_version"),
        }
        result[sid_str] = entry

    log.info("skill_map: %d 个技能（来自 SKILL_CONF）", len(result))
    return result


# ── pet_skill_map.json 生成 ───────────────────────────────────

def build_pet_skill_map(bdata_dir: Path) -> Dict[str, Any]:
    """从 LEVEL_SKILL_CONF 构建增强版 pet_skill_map。"""
    level_skill = load_bin_table(bdata_dir, "LEVEL_SKILL_CONF")
    skill_conf = load_bin_table(bdata_dir, "SKILL_CONF")

    # 构建技能 id → name 索引
    skill_name_idx: Dict[int, str] = {}
    for k, v in skill_conf.items():
        sid = v.get("id")
        if sid:
            skill_name_idx[sid] = clean_text(v.get("name")) or ""

    result: Dict[str, Any] = {}

    for k, row in level_skill.items():
        lid = row.get("id")
        if not lid:
            continue

        lid_str = str(lid)
        editor_name = clean_text(row.get("editor_name")) or ""

        # 等级技能
        level_skills = []
        for ls in normalize_array(row.get("level", [])):
            if not isinstance(ls, dict):
                continue
            skill_id = ls.get("param")
            if skill_id:
                level_skills.append({
                    "level_point": ls.get("level_point", 0),
                    "stage": ls.get("stage", 0),
                    "level_gain_skill": ls.get("level_gain_skill", 1),
                    "skill_id": skill_id,
                    "skill_name": skill_name_idx.get(skill_id),
                })

        # 技能石
        machine_skills = []
        for ms in normalize_array(row.get("machine_skill_group", [])):
            if not isinstance(ms, dict):
                continue
            skill_id = ms.get("machine_skill_id")
            if skill_id:
                machine_skills.append({
                    "machine_skill_id": skill_id,
                    "machine_skill_name": clean_text(ms.get("machine_skill_name")),
                })

        # 血脉技能 (18 种属性)
        blood_skills: Dict[str, Any] = {}
        blood_level = row.get("blood_skill_level_point")
        for btype in BLOOD_TYPE_NAMES:
            field = f"blood_skill_{btype}"
            skill_id = row.get(field)
            if skill_id:
                blood_skills[field] = {
                    "skill_id": skill_id,
                    "skill_name": skill_name_idx.get(skill_id),
                }
                if blood_level:
                    blood_skills[field]["level_point"] = blood_level

        entry = {
            "id": lid,
            "editor_name": editor_name,
            "level_skills": level_skills,
            "machine_skills": machine_skills,
            "blood_skills": blood_skills,
            "blood_skill_level_point": blood_level,
        }
        result[lid_str] = entry

    log.info("pet_skill_map: %d 个物种技能（来自 LEVEL_SKILL_CONF）", len(result))
    return result


# ── nature_map.json 生成 ──────────────────────────────────────

def build_nature_map(bdata_dir: Path) -> Dict[str, Any]:
    """从 NATURE_CONF 构建性格数据。"""
    nature_conf = load_bin_table(bdata_dir, "NATURE_CONF")
    result: Dict[str, Any] = {}

    # 属性 effect ID → 属性名映射
    # 80=物攻, 81=物防, 82=特攻, 83=特防, 85=速度
    attr_labels = {80: "atk", 81: "def", 82: "spa", 83: "spd", 85: "spe"}

    for k, row in nature_conf.items():
        nid = row.get("id")
        if not nid:
            continue

        entry = {
            "id": nid,
            "name": clean_text(row.get("name")) or "",
            "is_player_pet_nature": row.get("is_player_pet_nature", False),
            "positive_effect": row.get("positive_effect"),
            "positive_effect_proportion": row.get("positive_effect_proportion"),
            "positive_effect_grow": row.get("positive_effect_grow"),
            "negative_effect": row.get("negative_effect"),
            "negative_effect_proportion": row.get("negative_effect_proportion"),
            "prob": row.get("prob"),
        }

        # 添加人类可读标签
        pe = row.get("positive_effect")
        ne = row.get("negative_effect")
        if pe in attr_labels:
            entry["positive_stat"] = attr_labels[pe]
        if ne in attr_labels:
            entry["negative_stat"] = attr_labels[ne]

        # 性格描述
        descs = row.get("random_desc", [])
        if isinstance(descs, list) and descs:
            entry["random_descs"] = [
                {"nature_id": d.get("nature_id"), "desc": clean_text(d.get("nature_desc")),
                 "weight": d.get("random_weight")}
                for d in descs if isinstance(d, dict)
            ]

        result[str(nid)] = entry

    log.info("nature_map: %d 个性格（来自 NATURE_CONF）", len(result))
    return result


# ── evolution_map.json 生成 ───────────────────────────────────

def build_evolution_map(bdata_dir: Path, pet_species_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """从 PET_EVOLUTION_CONF 构建进化链数据。

    pet_species_data: 可选，从 PETBASE_CONF 生成的宠物物种数据，用于回填 pet_name。
    BinData 解码后的 evolution_chain 通常不含 pet_name，需从 pet_species 查找。
    """
    evolution = load_bin_table(bdata_dir, "PET_EVOLUTION_CONF")
    result: Dict[str, Any] = {}

    # 构建 petbase_id → name 查表（用于回填空的 pet_name）
    species_id_to_name: Dict[int, str] = {}
    if pet_species_data:
        for v in pet_species_data.values():
            pid = v.get("id")
            if pid:
                species_id_to_name[int(pid)] = v.get("name", "")

    for k, row in evolution.items():
        eid = row.get("id")
        if not eid:
            continue

        # 进化链
        chain = []
        for stage in normalize_array(row.get("evolution_chain", [])):
            if not isinstance(stage, dict):
                continue
            petbase_id = stage.get("petbase_id")
            # pet_name 可能为空，回填：从 pet_species 按 petbase_id 查找
            pet_name_raw = clean_text(stage.get("pet_name"))
            pet_name = pet_name_raw if pet_name_raw else species_id_to_name.get(petbase_id, "")
            chain.append({
                "petbase_id": petbase_id,
                "pet_name": pet_name,
                "stage": stage.get("stage"),
                "level": stage.get("level", 0),
                "unit_type": normalize_array(stage.get("unit_type", [])),
                "evolution_need": normalize_array(stage.get("evolution_need", [])),
                "evolution_need_type": stage.get("evolution_need_type"),
                "evolution_need_data1": stage.get("evolution_need_data1"),
                "evolution_need_data2": stage.get("evolution_need_data2"),
                "evolution_need_level": stage.get("evolution_need_level", 0),
                "evolution_need_money": stage.get("evolution_need_money", 0),
                "evolution_need_items": normalize_array(stage.get("evolution_need_items", [])),
            })

        # 从第一条宠物名字派生 name，保证与 evolution_chain 一致
        # chain[0].pet_name 已通过 species_id_to_name 回填（BinData 的 pet_name 为空时）
        first_pet_name = chain[0]["pet_name"] if chain else ""
        derived_name = (first_pet_name + "进化链") if first_pet_name else ""

        entry = {
            "id": eid,
            "name": derived_name,
            "pvp_mute_group": row.get("pvp_mute_group"),
            "evolution_group": row.get("evolution_group"),
            "handbook_evolution_group": row.get("handbook_evolution_group"),
            "statistics_evolution_group": row.get("statistics_evolution_group"),
            "evolution_chain": chain,
            "talent_random_id": row.get("talent_random_id"),
        }
        result[str(eid)] = entry

    log.info("evolution_map: %d 条进化链（来自 PET_EVOLUTION_CONF）", len(result))
    return result


# ── battle_config.json 生成 ───────────────────────────────────

def build_battle_config(bdata_dir: Path) -> Dict[str, Any]:
    """从 BATTLE_GLOBAL_CONFIG 提取战斗全局参数。"""
    config = load_bin_table(bdata_dir, "BATTLE_GLOBAL_CONFIG")
    result: Dict[str, Any] = {}

    key_mappings = {
        "restraint_percent": "单倍克制伤害倍率",
        "double_restraint_percent": "双倍克制伤害倍率",
        "restrained_percent": "单倍被克制伤害倍率",
        "double_restrained_percent": "双倍被克制伤害倍率",
        "battle_unit_maximum": "战斗中一方上场的最大单位数量",
        "battle_catch_times": "每回合最大抓捕次数",
        "battle_overtime_limit": "战斗操作倒计时隐藏时间上限",
        "battle_gve_blood_energy": "精灵选招完毕后获得能量数",
        "battle_gve_blood_deathround": "固定回合数+精灵死亡次数*系数",
        "battle_gve_blood_boss_energy": "血脉boss能量以及上限",
        "catch_fight_max": "捕捉概率战斗修正最大值",
        "catch_icon_display_time": "捕捉广播图标显示的秒数",
    }

    for row_key, editor_label in key_mappings.items():
        # 按 key 字段匹配
        for k, v in config.items():
            if v.get("key") == row_key:
                new_en = clean_text(v.get("editor_name"))
                # 如果 BinData 无 editor_name，用预设的 editor_label
                en = new_en if new_en else editor_label
                result[row_key] = {
                    "editor_name": en,
                    "value": v.get("num") if v.get("num") is not None else v.get("numList", []),
                }
                break

    # 直接存储所有全局配置
    # 注意：BinData 的 BATTLE_GLOBAL_CONFIG entries 有 is_loc=2 (editor_name 本地化)，
    # 解码后 editor_name=None，无法从 BinData 恢复。因此：
    # - 只在 BinData 提供非空 editor_name 时更新，否则保留原文件内容
    existing_all = {}
    try:
        existing_bc = load_project_json(out_path / "battle_config.json")
        existing_all = existing_bc.get("_all", {})
    except Exception:
        pass

    result["_all"] = {}
    for k, v in config.items():
        key = v.get("key", k)
        new_editor_name = clean_text(v.get("editor_name")) or ""
        # 如果 BinData 的 editor_name 为空但原文件有值，保留原值
        if not new_editor_name and key in existing_all:
            existing_en = existing_all[key].get("editor_name", "")
            if existing_en:
                new_editor_name = existing_en
        result["_all"][key] = {
            "editor_name": new_editor_name,
            "value": v.get("num") if v.get("num") is not None else v.get("numList", []),
        }

    log.info("battle_config: %d 个全局参数", len(config))
    return result


# ── weather_map.json 生成 ─────────────────────────────────────

def build_weather_map(bdata_dir: Path) -> Dict[str, Any]:
    """从 WEATHER_CONF 构建天气数据。"""
    weather = load_bin_table(bdata_dir, "WEATHER_CONF")
    result: Dict[str, Any] = {}

    for k, row in weather.items():
        wid = row.get("id")
        if not wid:
            continue

        entry = {
            "id": wid,
            "weather_type": row.get("weather_type"),
            "name": clean_text(row.get("name")) or "",
            "weather_params": row.get("weather_params"),
            "weather_buff": normalize_array(row.get("weather_buff", [])),
            "temperature": row.get("temperature"),
            "report_tip": clean_text(row.get("report_tip")),
            "icon": row.get("icon"),
            "show_icon": row.get("show_icon"),
        }
        result[str(wid)] = entry

    log.info("weather_map: %d 个天气类型（来自 WEATHER_CONF）", len(result))
    return result


# ── type_chart.json 增强 ──────────────────────────────────────

def build_type_chart_enhancement(bdata_dir: Path) -> Tuple[Dict[int, List[int]], Dict[int, str]]:
    """从 TYPE_DICTIONARY 提取 immunity 数据和 raw_to_name 映射。

    Returns:
        immunity_map: raw_id → List[immune_buff_id]
        raw_to_name: raw_id → type_name
    """
    type_dict = load_bin_table(bdata_dir, "TYPE_DICTIONARY")
    immunity_map: Dict[int, List[int]] = {}
    raw_to_name: Dict[int, str] = {}

    for k, v in type_dict.items():
        rid = int(k)
        raw_to_name[rid] = v.get("type_name", "") or ""
        immunity = v.get("type_immunity", [])
        if immunity:
            immunity_map[rid] = normalize_array(immunity)

    return immunity_map, raw_to_name


# ── innate_skills 增强 ────────────────────────────────────────

def build_innate_pet_mapping(bdata_dir: Path, type_map: Dict[int, int]) -> Dict[str, Any]:
    """从 PETBASE_CONF 提取 pet_feature 字段构建宠物→特性技能映射。"""
    petbase = load_bin_table(bdata_dir, "PETBASE_CONF")
    pet_to_skill: Dict[str, Any] = {}

    for k, row in petbase.items():
        pid = row.get("id")
        if not pid:
            continue

        # pet_feature / pet_glass_feature / pet_chaos_feature 是特性技能 ID
        # 这三个字段通常是同样的值，取第一个非空
        feature_ids = []
        for field in ["pet_feature", "pet_glass_feature", "pet_chaos_feature"]:
            fid = row.get(field)
            if fid and fid not in feature_ids:
                feature_ids.append(fid)

        if feature_ids:
            pet_to_skill[str(pid)] = {
                "base_id": pid,
                "name": clean_text(row.get("name")) or "",
                "feature_skill_ids": feature_ids,
                # 主特征就是第一个
                "primary_feature": feature_ids[0] if feature_ids else None,
            }

    log.info("innate_pet_mapping: %d 个宠物有特性技能", len(pet_to_skill))
    return pet_to_skill


# ── 主流程 ────────────────────────────────────────────────────

def import_all(bdata_dir: str, output_dir: str, dry_run: bool = False) -> Dict[str, Any]:
    """执行完整的数据导入流程。返回变更摘要。"""
    bdata_path = Path(bdata_dir)
    out_path = Path(output_dir)

    if not bdata_path.exists():
        raise FileNotFoundError(f"BinData 目录不存在: {bdata_path}")

    log.info("=== 开始从 %s 导入 BinData ===", bdata_path)
    log.info("输出目录: %s", out_path)

    changes = {}

    # 构建类型映射
    type_map = build_type_map(bdata_path, out_path)
    if not type_map:
        log.error("类型映射构建失败！请检查 TYPE_DICTIONARY.json 和 type_chart.json")
        return changes

    # ── 1. pet_species.json (新文件) + pet_map.json 增强 ──
    log.info("--- [1/9] pet_species ---")
    new_species = build_pet_species(bdata_path, type_map)
    changes["pet_species"] = {"new_count": len(new_species), "new_file": True}
    if not dry_run:
        save_json(out_path / "pet_species.json", new_species)

    # 增强现有 pet_map
    old_pet_map = load_project_json(out_path / "pet_map.json")
    old_pm_count = len(old_pet_map)
    if old_pet_map:
        enhanced_pm = enhance_pet_map(old_pet_map, new_species)
        changes["pet_map"] = {
            "old_count": old_pm_count,
            "new_count": len(enhanced_pm),
            "enhanced": True,
        }
        if not dry_run:
            save_json(out_path / "pet_map.json", enhanced_pm)
    else:
        changes["pet_map"] = {"note": "无现有 pet_map.json，跳过增强"}

    # ── 2. skill_map.json ──
    log.info("--- [2/9] skill_map ---")
    new_skill_map = build_skill_map(bdata_path, type_map)
    old_skill_map = load_project_json(out_path / "skill_map.json")
    changes["skill_map"] = {
        "old_count": len(old_skill_map),
        "new_count": len(new_skill_map),
        "delta": len(new_skill_map) - len(old_skill_map),
    }
    if not dry_run:
        save_json(out_path / "skill_map.json", new_skill_map)

    # ── 3. pet_skill_map.json ──
    log.info("--- [3/9] pet_skill_map ---")
    new_psm = build_pet_skill_map(bdata_path)
    old_psm = load_project_json(out_path / "pet_skill_map.json")
    changes["pet_skill_map"] = {
        "old_count": len(old_psm),
        "new_count": len(new_psm),
        "delta": len(new_psm) - len(old_psm),
    }
    if not dry_run:
        save_json(out_path / "pet_skill_map.json", new_psm)

    # ── 4. nature_map.json (新文件) ──
    log.info("--- [4/9] nature_map ---")
    new_nature = build_nature_map(bdata_path)
    changes["nature_map"] = {"new_count": len(new_nature), "new_file": True}
    if not dry_run:
        save_json(out_path / "nature_map.json", new_nature)

    # ── 5. evolution_map.json (新文件) ──
    log.info("--- [5/9] evolution_map ---")
    new_evo = build_evolution_map(bdata_path, pet_species_data=new_species)
    changes["evolution_map"] = {"new_count": len(new_evo), "new_file": True}
    if not dry_run:
        save_json(out_path / "evolution_map.json", new_evo)

    # ── 6. battle_config.json (新文件) ──
    log.info("--- [6/9] battle_config ---")
    new_bc = build_battle_config(bdata_path)
    bc_count = len(new_bc) - 1  # 减去 _all 键
    changes["battle_config"] = {"new_count": bc_count, "new_file": True,
                                "all_params": len(new_bc.get("_all", {}))}
    if not dry_run:
        save_json(out_path / "battle_config.json", new_bc)

    # ── 7. weather_map.json (新文件) ──
    log.info("--- [7/9] weather_map ---")
    new_weather = build_weather_map(bdata_path)
    changes["weather_map"] = {"new_count": len(new_weather), "new_file": True}
    if not dry_run:
        save_json(out_path / "weather_map.json", new_weather)

    # ── 8. innate_skills 增强 ──
    log.info("--- [8/9] innate_skills 宠物映射 ---")
    pet_trait_map = build_innate_pet_mapping(bdata_path, type_map)
    changes["innate_pet_traits"] = {"new_count": len(pet_trait_map)}

    # 更新 innate_skills.json 中的 pets 映射
    innate_path = out_path / "innate_skills.json"
    innate = load_project_json(innate_path)
    innate["pets"] = pet_trait_map
    innate["_meta"]["pet_mapping_source"] = "PETBASE_CONF.pet_feature / pet_glass_feature / pet_chaos_feature"
    changes["innate_skills_pets"] = {"new_count": len(pet_trait_map)}
    if not dry_run:
        save_json(innate_path, innate)
        log.info("innate_skills.json: pets 映射已填充 (%d 个宠物)", len(pet_trait_map))

    # ── 9. type_chart 增强 ──
    # 注：type_chart.json 原有的 immunity 数据是正确的，不从 BinData 覆盖
    # 只记录本次处理了 immunity_map 中的多少条（不作写入）
    immunity_map, raw_to_name = build_type_chart_enhancement(bdata_path)
    changes["type_chart"] = {"note": "immunity 数据保留原文件，不从 BinData 覆盖"}

    # ── 打印摘要 ──
    log.info("=== 导入完成 ===")
    if dry_run:
        log.info("（DRY RUN — 未写入文件）")
    log.info("变更摘要:")
    for name, info in changes.items():
        if info.get("new_file"):
            log.info("  %s: 新建 (%d 条)", name, info.get("new_count", 0))
        elif info.get("enhanced"):
            log.info("  %s: 增强 (%d → %d 条, 添加 species_* 字段)", name,
                     info.get("old_count", 0), info.get("new_count", 0))
        elif "delta" in info:
            delta = info["delta"]
            direction = "+" if delta > 0 else ""
            log.info("  %s: %d → %d (%s%d)", name,
                     info.get("old_count", 0), info.get("new_count", 0), direction, delta)
        elif "all_params" in info:
            log.info("  %s: 新建 (%d 个核心参数, %d 个全部参数)",
                     name, info.get("new_count", 0), info.get("all_params", 0))
        else:
            log.info("  %s: %s", name, info)

    return changes


# ── CLI ────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="从 BinData JSON 导入游戏数据"
    )
    parser.add_argument(
        "bdata_dir",
        help="已解码的 BinData JSON 目录（如 BinDataCompressed/）",
    )
    parser.add_argument(
        "--output-dir",
        default=str(_DEFAULT_OUTPUT),
        help=f"输出目录（默认: {_DEFAULT_OUTPUT}）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="不写入文件，仅打印变更摘要",
    )
    args = parser.parse_args()

    import_all(args.bdata_dir, args.output_dir, args.dry_run)


if __name__ == "__main__":
    main()
