"""Field/system perform entry handlers for action resolve."""
from __future__ import annotations

from typing import Any, Dict, Optional

from src.protocol.proto_core import (
    collect_varints,
    field_groups,
    first_sub,
    first_text,
    pick_first,
    skill_name,
)
from src.protocol.battle_parts.sync import _extract_pet_skill_updates


def _weather_name(weather_id: Optional[int]) -> Optional[str]:
    if weather_id is None:
        return None
    from src.data.loader import get_weather
    meta = get_weather(weather_id)
    if isinstance(meta, dict) and meta.get("name"):
        return meta["name"]
    return None


def apply_idle_entry(out: Dict[str, Any], sg: Dict[int, list[Dict[str, Any]]]) -> None:
    """Extract BPT_IDLE from field 20."""
    out["kind"] = "idle"
    im = first_sub(sg.get(20, []))
    if im:
        out["idle_pet_id"] = pick_first(collect_varints(im, 1))


def apply_skill_state_entry(out: Dict[str, Any], sg: Dict[int, list[Dict[str, Any]]]) -> None:
    """Extract BPT_SKILL_STATE from field 24."""
    out["kind"] = "skill_state"
    sm = first_sub(sg.get(24, []))
    if sm:
        out["caster_pet_id"] = pick_first(collect_varints(sm, 1))
        out["state_code"] = pick_first(collect_varints(sm, 2))


def apply_weather_change_entry(out: Dict[str, Any], sg: Dict[int, list[Dict[str, Any]]]) -> None:
    """Extract BPT_WEATHER_CHANGE from field 29."""
    out["kind"] = "weather_change"
    wm = first_sub(sg.get(29, []))
    if not wm:
        return

    out["skill_id"] = pick_first(collect_varints(wm, 1))
    out["skill_name"] = skill_name(out["skill_id"])
    out["weather_id"] = pick_first(collect_varints(wm, 2))
    out["weather_name"] = _weather_name(out["weather_id"])
    out["expire_round"] = pick_first(collect_varints(wm, 5))


def apply_notify_perform_entry(out: Dict[str, Any], sg: Dict[int, list[Dict[str, Any]]]) -> None:
    """Extract BPT_NOTIFY_PERFORM from field 30."""
    out["kind"] = "notify_perform"
    nm = first_sub(sg.get(30, []))
    if not nm:
        return

    out["notify_type"] = pick_first(collect_varints(nm, 1))
    out["notify_data"] = collect_varints(nm, 2)
    out["tips_id"] = first_text(nm, 3)
    params = [e.get("text", "") for e in field_groups(nm).get(4, []) if e.get("text")]
    if params:
        out["params"] = params
    out["uin"] = pick_first(collect_varints(nm, 5))


def apply_ai_action_entry(out: Dict[str, Any], sg: Dict[int, list[Dict[str, Any]]]) -> None:
    """Extract BPT_AI from field 33."""
    out["kind"] = "ai_action"
    am = first_sub(sg.get(33, []))
    if am:
        out["pet_id"] = pick_first(collect_varints(am, 1))
        out["uin"] = pick_first(collect_varints(am, 2))
        out["ai_type"] = pick_first(collect_varints(am, 3))
        out["param"] = pick_first(collect_varints(am, 4))


def apply_pvp_perform_marker_entry(out: Dict[str, Any], sg: Dict[int, list[Dict[str, Any]]]) -> None:
    """Extract BPT_BATTLER_PVP_PERFORM from field 43."""
    out["kind"] = "pvp_perform_marker"
    pm = first_sub(sg.get(43, []))
    if pm:
        out["uin"] = pick_first(collect_varints(pm, 1))
        out["pvp_type"] = pick_first(collect_varints(pm, 2))


def apply_data_update_entry(out: Dict[str, Any], sg: Dict[int, list[Dict[str, Any]]]) -> None:
    """Extract BPT_DATA_UPDATE from field 44."""
    out["kind"] = "data_update"
    dm = first_sub(sg.get(44, []))
    if not dm:
        return

    out["uin"] = pick_first(collect_varints(dm, 1))
    pet_sub = first_sub(field_groups(dm).get(3, []))
    if pet_sub:
        out["pet_id"] = pick_first(collect_varints(pet_sub, 1))
    pet_skill_updates = _extract_pet_skill_updates(dm)
    if pet_skill_updates:
        out["pet_skill_updates"] = pet_skill_updates
