"""Opcode 0x0414 内嵌消息 detail 解析。"""
from __future__ import annotations

from typing import Any, Dict

from src.protocol.proto_core import collect_varints, field_groups, pick_first


def parse_inner390_detail(fields) -> Dict[str, Any]:
    """解析配对上下文 inner message 390。"""
    fg = field_groups(fields)
    pe = next((e for e in fg.get(2, []) if e.get("sub")), None)
    detail: Dict[str, Any] = {"pair_ctx": pick_first(collect_varints(fields, 1))}
    if pe is None:
        return detail
    pg = field_groups(pe["sub"])
    for side, fn in (("friendly", 3), ("enemy", 4)):
        entries = pg.get(fn, [])
        if entries and entries[0].get("sub"):
            s = entries[0]["sub"]
            pid = pick_first(collect_varints(s, 2))
            base: Dict[str, Any] = {"pet_id": pid, "side_flag": pick_first(collect_varints(s, 10))}
            for i in range(3, 7):
                base[f"arg{i}"] = pick_first(collect_varints(s, i))
            if side == "enemy":
                base["arg1"] = pick_first(collect_varints(s, 1))
            detail[side] = base
    return detail


def parse_inner200_detail(fields) -> Dict[str, Any]:
    """解析提交确认 inner message 200。"""
    fg = field_groups(fields)
    ce = next((e for e in fg.get(2, []) if e.get("sub")), None)
    detail: Dict[str, Any] = {"pair_ctx": pick_first(collect_varints(fields, 1))}
    if ce:
        c = ce["sub"]
        detail["commit"] = {
            "flag": pick_first(collect_varints(c, 1)),
            "arg2_ms_like": pick_first(collect_varints(c, 2)),
            "event_time_ms": pick_first(collect_varints(c, 3)),
            "code": pick_first(collect_varints(c, 4)),
        }
    return detail


def parse_inner51_detail(fields) -> Dict[str, Any]:
    """解析通用事件 inner message 51。"""
    fg = field_groups(fields)
    pe = next((e for e in fg.get(2, []) if e.get("sub")), None)
    p = pe["sub"] if pe else None
    return {
        "token": pick_first(collect_varints(fields, 1)),
        "kind": pick_first(collect_varints(p, 1)) if p else None,
        "value2": pick_first(collect_varints(p, 2)) if p else None,
        "value3": pick_first(collect_varints(p, 3)) if p else None,
    }


def parse_inner1_detail(fields) -> Dict[str, Any]:
    """解析效果 inner message 1。"""
    fg = field_groups(fields)
    pe = next((e for e in fg.get(11, []) if e.get("sub")), None)
    if pe is None:
        return {}
    pg = field_groups(pe["sub"])
    he = next((e for e in pg.get(1, []) if e.get("sub")), None)
    ee = next((e for e in pg.get(3, []) if e.get("sub")), None)
    detail: Dict[str, Any] = {}
    if he:
        hs = he["sub"]
        detail["header"] = {
            "kind": pick_first(collect_varints(hs, 1)),
            "actor_token": pick_first(collect_varints(hs, 2)),
            "actor_aux": pick_first(collect_varints(hs, 3)),
            "actor_ref": pick_first(collect_varints(hs, 5)),
            "target_ctx": pick_first(collect_varints(hs, 6)),
            "arg10": pick_first(collect_varints(hs, 10)),
            "arg11": pick_first(collect_varints(hs, 11)),
        }
    if ee:
        es = ee["sub"]
        detail["effect"] = {
            "effect_id": pick_first(collect_varints(es, 1)),
            "code": pick_first(collect_varints(es, 4)),
            "arg10": pick_first(collect_varints(es, 10)),
            "amount": pick_first(collect_varints(es, 11)),
            "arg12": pick_first(collect_varints(es, 12)),
            "arg13": pick_first(collect_varints(es, 13)),
            "arg15": pick_first(collect_varints(es, 15)),
            "arg16": pick_first(collect_varints(es, 16)),
            "arg27": pick_first(collect_varints(es, 27)),
            "arg32": pick_first(collect_varints(es, 32)),
        }
    return detail
