"""战斗 state wrapper 提取和去重。"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from src.protocol.proto.creature import (
    extract_battle_buffs,
    extract_creature,
    extract_simple_items,
    extract_skills_from_round_data,
)
from src.protocol.proto.tree import collect_varints, field_groups, pick_first, walk_messages
from src.protocol.proto.wire import maybe_signed64

logger = logging.getLogger(__name__)

_RE_BATTLE_ENTER_SIDE = re.compile(r"\.6\[\d+\]\.(\d+)\[")
_RE_ROUND_START_OPP = re.compile(r"\.8\[\d+\]\.")
_RE_ROUND_START_PLAYER = re.compile(r"\.44\[\d+\]\.")


def _side_from_path(path: str) -> Optional[int]:
    """Determine side from wrapper path."""
    # battle_enter pattern: .6[N].5[N] or .6[N].6[N]
    m = _RE_BATTLE_ENTER_SIDE.search(path)
    if m:
        f = int(m.group(1))
        if f == 5:
            return 1
        if f == 6:
            return 401
    # round_start pattern: .8[N] present → opponent
    if _RE_ROUND_START_OPP.search(path):
        return 401
    # round_start player pets have .44[N].3[N] without .8
    if _RE_ROUND_START_PLAYER.search(path):
        return 1
    return None


def extract_state_wrapper(msg: Dict[str, Any], *, path: str, record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    groups = field_groups(msg)
    se = next((e for e in groups.get(1, []) if e.get("sub")), None)
    ce = next((e for e in groups.get(2, []) if e.get("sub")), None)
    if se is None or ce is None:
        return None
    creature = extract_creature(ce["sub"], path=f"{path}.2[*]", record=record)
    if creature is None:
        return None
    dm = se["sub"]
    ds = collect_varints(dm, 6)
    side_code = _side_from_path(path)
    max_hp = ds[1] if len(ds) >= 2 else None
    current_hp = ds[25] if len(ds) >= 26 else None

    all_skills = creature.get("skills", [])
    equipped_skills = creature.get("equipped_skills", [])
    skill_source = "pet_data_f12"
    if not equipped_skills:
        round_skills = extract_skills_from_round_data(dm)
        round_equipped = [it for it in round_skills if 1 <= it["equipped_slot"] <= 4]
        if round_equipped:
            all_skills = round_skills
            equipped_skills = sorted(round_equipped, key=lambda it: (it["equipped_slot"], it["skill_id"]))
            skill_source = "inside_info_f8"
            logger.info(
                "Skills from InsideInfo.field8 for %s (side=%s): %s",
                creature["name"], side_code,
                [f"slot{s['equipped_slot']}:{s.get('skill_name', '?')}" for s in equipped_skills],
            )

    initial_buffs = extract_battle_buffs(dm)
    triggered_buffs = [
        item for item in (
            {
                "buffbase_id": maybe_signed64(pick_first(collect_varints(e["sub"], 1)) or 0),
                "value": maybe_signed64(pick_first(collect_varints(e["sub"], 2)) or 0),
                "side": maybe_signed64(pick_first(collect_varints(e["sub"], 3)) or 0),
                "role_uin": pick_first(collect_varints(e["sub"], 4)),
            }
            for e in field_groups(dm).get(65, [])
            if e.get("sub") is not None
        )
        if any(v not in (None, 0) for v in item.values())
    ]
    passive_skill_id = pick_first(collect_varints(dm, 64))
    raw_energy = pick_first(collect_varints(ce["sub"], 33))

    return {
        "name": creature["name"], "level": creature["level"],
        "slot": creature["slot"], "pet_id": creature["pet_id"],
        "side": side_code,
        "types": creature.get("types", []),
        "battle_stats": ds[1:7] if len(ds) >= 7 else [],
        "battle_max_hp": max_hp, "max_hp": max_hp,
        "current_hp": current_hp, "hp": current_hp,
        "energy": raw_energy if raw_energy and raw_energy > 0 else None,
        "stats": creature.get("stats", []),
        "skills": all_skills,
        "equipped_skills": equipped_skills,
        "skill_source": skill_source,
        "initial_buffs": initial_buffs,
        "state_bits": collect_varints(dm, 24),
        "sp_energy": extract_simple_items(dm, 15, {
            1: ("source_type", False),
            2: ("env_type", False),
            3: ("env_layer", False),
            4: ("src_id", True),
            5: ("tod_time", True),
            6: ("expire_round", True),
        }),
        "extra_resist_type": collect_varints(dm, 30),
        "in_battle_round": pick_first(collect_varints(dm, 31)),
        "counter_round": pick_first(collect_varints(dm, 32)),
        "revive_round": pick_first(collect_varints(dm, 33)),
        "revive_rounds": pick_first(collect_varints(dm, 34)),
        "charging_skill_id": pick_first(collect_varints(dm, 35)),
        "remain_buff_infos": extract_simple_items(dm, 39, {
            1: ("buff_id", True),
            2: ("stack", True),
        }),
        "extra_sdt": extract_simple_items(dm, 41, {
            1: ("type", True),
            2: ("result", True),
            3: ("buff_id", False),
            4: ("buffbase_id", False),
        }),
        "changed_attr": [maybe_signed64(v) for v in collect_varints(dm, 54)],
        "dead_round": pick_first(collect_varints(dm, 55)),
        "dead_cnt": pick_first(collect_varints(dm, 56)),
        "using_buffs": collect_varints(dm, 60),
        "triggered_buffs": triggered_buffs,
        "max_energy": pick_first(collect_varints(dm, 53)),
        "speed_min": pick_first(collect_varints(dm, 71)),
        "speed_max": pick_first(collect_varints(dm, 72)),
        "owner_uin": pick_first(collect_varints(dm, 77)),
        "last_up_round": pick_first(collect_varints(dm, 78)),
        "last_down_round": pick_first(collect_varints(dm, 79)),
        "charging_skill_energy": pick_first(collect_varints(dm, 82)),
        "passive_skill_id": passive_skill_id,
        "base_id": creature.get("base_id"),
        "base_conf_id": creature.get("base_conf_id"),
        "base_skill_pool": creature.get("base_skill_pool"),
        "source_opcode": record["opcode"], "source_opcode_hex": record.get("opcode_hex", ""),
        "seq": record.get("seq"), "path": path,
    }


def extract_state_wrappers_from_record(record: Dict[str, Any]) -> List[Dict[str, Any]]:
    wrappers = []
    for path, msg in walk_messages(record["root"]):
        w = extract_state_wrapper(msg, path=path, record=record)
        if w is not None:
            wrappers.append(w)
    return dedupe_state_wrappers(wrappers)


def dedupe_state_wrappers(wrappers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out, seen = [], set()
    for it in wrappers:
        key = (it.get("name"), it.get("level"), it.get("slot"), it.get("pet_id"),
               tuple(it.get("battle_stats") or []), it.get("battle_max_hp"), it.get("current_hp"))
        if key not in seen:
            seen.add(key)
            out.append(it)
    out.sort(key=lambda it: (it.get("slot") is None, int(it.get("slot") or 0), int(it.get("pet_id") or 0)))
    return out

