"""技能与特殊行动提取辅助。

这些函数处理多个 opcode 共用的 actor/target/skill/special-action 形态，
从主 battle 提取门面中拆出，方便之后按 opcode 继续细分。
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from src.protocol.proto_core import (
    SPECIAL_ACTION_COMMANDS,
    SPECIAL_ACTION_SHAPES,
    _attach_skill_meta,
    collect_varints,
    field_groups,
    first_sub,
    normalize_skill_id,
    pick_first,
    side_name,
    skill_name,
)


def _extract_skill_ref(msg: Dict[str, Any], *, skill_field: int = 3) -> Dict[str, Any]:
    """从子消息中抽取技能引用：field 1=actor, 2=target, 3=skill。"""
    all_field_values = collect_varints(msg, skill_field)
    skill_id_x100 = pick_first(all_field_values, low=100_000)
    sid = normalize_skill_id(skill_id_x100)

    skill_slot_index: Optional[int] = None
    if skill_id_x100 is None:
        raw_small = [v for v in all_field_values if 1 <= v <= 10]
        if raw_small:
            skill_slot_index = raw_small[0]

    actor = pick_first(collect_varints(msg, 1))
    target = pick_first(collect_varints(msg, 2))
    out: Dict[str, Any] = {
        "actor_side": actor,
        "actor_side_name": side_name(actor),
        "target_side": target,
        "target_side_name": side_name(target),
        "skill_id_x100": skill_id_x100,
        "skill_id": sid,
        "skill_name": skill_name(sid),
        "skill_slot_index": skill_slot_index,
    }
    _attach_skill_meta(out, sid)
    return out


def _extract_special_action(
    msg: Dict[str, Any],
    *,
    command_flag: Optional[int] = None,
    command_slot: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """尝试将消息解释为特殊行动（愿力、能量瓶、换宠等）。"""
    kind = pick_first(collect_varints(msg, 1), low=0, high=99)
    if kind is None:
        return None

    sub: Optional[Dict[str, Any]] = None
    payload_branch: Optional[int] = None
    for branch in (8, 4, 3):
        entries = field_groups(msg).get(branch, [])
        s = first_sub(entries)
        if s is not None:
            sub = s
            payload_branch = branch
            break

    if sub is None:
        return None

    action_name: Optional[str] = None
    if command_flag is not None and command_slot is not None:
        action_name = SPECIAL_ACTION_COMMANDS.get((command_flag, command_slot))  # type: ignore[arg-type]
    if action_name is None and payload_branch is not None:
        action_name = SPECIAL_ACTION_SHAPES.get((kind, payload_branch))  # type: ignore[arg-type]

    if action_name is None:
        return None

    out: Dict[str, Any] = {
        "action_kind": "special_action",
        "action_name": action_name,
        "payload_kind": kind,
        "payload_branch": payload_branch,
        "command_flag": command_flag,
        "command_slot": command_slot,
    }
    actor = pick_first(collect_varints(sub, 1))
    target = pick_first(collect_varints(sub, 2))
    out["actor_side"] = actor
    out["actor_side_name"] = side_name(actor)
    out["target_side"] = target
    out["target_side_name"] = side_name(target)
    return out


def _extract_skill_or_special(
    record: Dict[str, Any],
    *,
    extra_fields: Dict[str, Any],
    command_flag: Optional[int] = None,
    command_slot: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """从 record.root 提取技能或特殊行动，按协议形态逐级 fallback。"""
    root = record.get("root")
    if root is None:
        return None

    groups = field_groups(root)
    payload = first_sub(groups.get(2, []))
    if payload is None:
        return None

    out: Optional[Dict[str, Any]] = None

    skill_id_x100 = pick_first(collect_varints(payload, 3), low=100_000)
    if skill_id_x100 is not None:
        out = _extract_skill_ref(payload)
    else:
        f3_sub = first_sub(field_groups(payload).get(3, []))
        if f3_sub is not None:
            sid3 = pick_first(collect_varints(f3_sub, 3), low=100_000)
            if sid3 is not None:
                out = _extract_skill_ref(f3_sub)

    if out is None:
        raw_all = collect_varints(payload, 3)
        raw_small = [v for v in raw_all if 1 <= v <= 10]
        if raw_small:
            actor = pick_first(collect_varints(payload, 1))
            target = pick_first(collect_varints(payload, 2))
            out = {
                "actor_side": actor,
                "actor_side_name": side_name(actor),
                "target_side": target,
                "target_side_name": side_name(target),
                "skill_id": None,
                "skill_name": None,
                "skill_slot_index": raw_small[0],
            }

    if out is None:
        out = _extract_special_action(
            payload,
            command_flag=command_flag,
            command_slot=command_slot,
        )

    if out is None:
        return None

    out.update(extra_fields)
    out["opcode"] = record.get("opcode")
    out["opcode_hex"] = record.get("opcode_hex", "")
    return out
