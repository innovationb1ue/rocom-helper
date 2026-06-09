"""Action-result command extraction for battle protocol."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.protocol.proto_core import (
    _WILLPOWER_SKILL_ID,
    collect_varints,
    extract_state_wrappers_from_record,
    field_groups,
    first_sub,
    pick_first,
)
from src.protocol.battle_actions import _extract_skill_ref, _extract_special_action


def extract_130c_result(record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract battle-result details from opcode 0x130C."""
    root = record.get("root")
    if root is None:
        return None

    rg = field_groups(root)
    container = first_sub(rg.get(10, []))
    state_msg = first_sub(field_groups(container).get(2, [])) if container else None

    skill_ctn = first_sub(rg.get(11, []))
    skill_msg = first_sub(field_groups(skill_ctn).get(2, [])) if skill_ctn else None

    out: Dict[str, Any] = _extract_skill_ref(skill_msg, skill_field=1) if skill_msg else {}

    btok_msg = first_sub(field_groups(container).get(1, [])) if container else None
    out.update({
        "battle_token": pick_first(collect_varints(btok_msg, 1)),
        "current_hp": pick_first(collect_varints(state_msg, 3), low=0, high=99999) if state_msg else None,
        "energy_after": pick_first(collect_varints(state_msg, 26), low=0, high=99) if state_msg else None,
        "result_code": pick_first(collect_varints(first_sub(rg.get(1, [])), 1), low=0, high=999),
        "opcode": record.get("opcode"),
        "opcode_hex": record.get("opcode_hex", ""),
    })

    if skill_ctn and out.get("skill_id") is None:
        sp = _extract_special_action(skill_ctn)
        if sp:
            out.update(sp)

    wrappers = extract_state_wrappers_from_record(record)
    if wrappers:
        out["state_wrappers"] = wrappers

    if out.get("skill_id") is None:
        inferred = infer_action_from_wrappers(wrappers or [])
        if inferred:
            out["action_kind"] = "special_action"
            out["action_name"] = inferred

    semantic_keys = (
        "battle_token", "current_hp", "energy_after", "result_code",
        "skill_id", "skill_name", "skill_id_x100", "action_name",
        "action_kind", "state_wrappers",
    )
    return out if any(out.get(key) is not None for key in semantic_keys) else None


def infer_action_from_wrappers(wrappers: List[Dict[str, Any]]) -> Optional[str]:
    """Infer willpower action by checking if any wrapper has the willpower skill."""
    return "愿力强化" if any(
        any(int(sk.get("skill_id") or 0) == _WILLPOWER_SKILL_ID
            for sk in (wrapper.get("dynamic_skills") or []))
        for wrapper in wrappers
    ) else None
