"""Protobuf 解析原语、传输层常量、精灵/状态提取。"""
from __future__ import annotations
import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple
from src.data.loader import get_attr_name, get_skill_name, get_skill_meta, get_pet_meta, get_pet_name, get_buff_meta, get_buffbase_meta, get_pet_skill_meta, get_wiki_pet_types

logger = logging.getLogger(__name__)

# --- 底层 proto 原语 ---

def read_varint(data: bytes, off: int) -> Tuple[int, int]:
    value = shift = 0
    cur = off
    while cur < len(data):
        byte = data[cur]
        cur += 1
        value |= (byte & 0x7F) << shift
        if byte < 0x80:
            return value, cur
        shift += 7
        if shift > 63:
            raise ValueError(f"varint too large at offset 0x{off:X}")
    raise ValueError(f"unterminated varint at offset 0x{off:X}")

def maybe_utf8(blob: bytes) -> Optional[str]:
    if not blob:
        return None
    try:
        text = blob.decode("utf-8")
    except UnicodeDecodeError:
        return None
    return None if any(ord(c) < 0x20 and c not in "\r\n\t" for c in text) else text

def strip_tsf4g_padding(data: bytes) -> bytes:
    marker = b"tsf4g"
    if data.rfind(marker) == len(data) - 6:
        pad = data[-1]
        if len(marker) + 1 <= pad <= 64 and len(data) >= pad:
            return data[:-pad]
        if pad == 1:
            return data[:-1]
        if 0 < pad <= 16 and len(data) >= pad and all(b == pad for b in data[-pad:]):
            return data[:-pad]
    return data

def tsf4g_trailer_len(data: bytes) -> int:
    marker = b"tsf4g"
    if data.rfind(marker) != len(data) - 6:
        return 0
    pad = data[-1]
    if len(marker) + 1 <= pad <= 64 and len(data) >= pad:
        return pad
    if pad == 1:
        return 1
    if 0 < pad <= 16 and len(data) >= pad and all(b == pad for b in data[-pad:]):
        return pad
    return 0

def normalize_c2s_opcode(opcode: int) -> Tuple[int, bool]:
    low16 = opcode & 0xFFFF
    if opcode > 0xFFFF and (opcode >> 16) == 0x0001 and low16:
        return low16, True
    return opcode, False

def maybe_signed64(value: int) -> int:
    return value - (1 << 64) if value >= (1 << 63) else value

# --- TGCP 命令映射 ---
TGCP_COMMAND_NAMES: Dict[int, str] = {
    0x1001: "SYN", 0x1002: "ACK", 0x2001: "AUTH_REQ", 0x2002: "AUTH_RSP",
    0x4013: "DATA", 0x5002: "SSTOP", 0x6002: "BINGO", 0x9001: "HEARTBEAT",
}
SSTOP_CODE_NAMES: Dict[int, str] = {0x11: "AUTH_INVALID", 0x12: "AUTH_REQUIRED"}

def tgcp_command_name(cmd: int) -> str:
    return TGCP_COMMAND_NAMES.get(cmd, f"UNKNOWN_0x{cmd:04X}")

# --- 游戏常量 ---
STAT_NAMES = ["HP", "ATK", "DEF", "SPA", "SPD", "SPE"]
SIDE_NAMES: Dict[int, str] = {1: "我方", 401: "敌方"}
_WILLPOWER_SKILL_ID = 7700014
_ENERGY_BOTTLE_MAX = 10
SPECIAL_ACTION_COMMANDS: Dict[Tuple[int, int], str] = {
    (8, 7): "愿力强化", (3, 8): "能量瓶", (2, 9): "换人",
}
SPECIAL_ACTION_SHAPES: Dict[Tuple[int, int], str] = {
    (8, 8): "愿力强化", (3, 4): "能量瓶", (2, 3): "换人",
}

# SkillDamType enum values (proto_schema PetData.skill_dam_type) → elemental type ID.
# The battle protocol sends SkillDamType enum values in field 6, not type IDs directly.
SDT_TO_TYPE: Dict[int, int] = {
    2: 0,   # SDT_COMMON → 普通
    3: 3,   # SDT_GRASS → 草
    4: 1,   # SDT_FIRE → 火
    5: 2,   # SDT_WATER → 水
    6: 17,  # SDT_LIGHT → 光
    7: 8,   # SDT_EARTH → 地
    9: 5,   # SDT_ICE → 冰
    10: 15, # SDT_DRAGON → 龙
    11: 4,  # SDT_ELECTRIC → 电
    12: 7,  # SDT_TOXIC → 毒
    13: 12, # SDT_INSECT → 虫
    14: 6,  # SDT_FIGHT → 武
    15: 9,  # SDT_WING → 翼
    16: 10, # SDT_MOE → 萌
    17: 13, # SDT_GHOST → 幽
    18: 16, # SDT_DEMON → 恶
    19: 14, # SDT_MECHANIC → 机械
    20: 11, # SDT_PHANTOM → 幻
    23: 0,  # SDT_GENERAL → 普通
}

# --- 名称查找 ---
def normalize_skill_id(v: Optional[int]) -> Optional[int]:
    if v is None:
        return None
    return v // 100 if v >= 100_000 and v % 100 == 0 else v

def skill_name(skill_id: Optional[int]) -> Optional[str]:
    return get_skill_name(skill_id)

def type_name(type_id: Optional[int]) -> Optional[str]:
    return get_attr_name(type_id)

def pet_name_fn(pet_id: Optional[int]) -> Optional[str]:
    return get_pet_name(pet_id)

def buff_name(buff_id: Optional[int]) -> Optional[str]:
    meta = get_buff_meta(buff_id)
    if not isinstance(meta, dict):
        return None
    if isinstance(meta.get("name"), str) and meta["name"]:
        return meta["name"]
    if isinstance(meta.get("editor_name"), str) and meta["editor_name"]:
        return meta["editor_name"]
    return None

def side_name(side_id: Optional[int]) -> Optional[str]:
    if side_id is None:
        return None
    v = int(side_id)
    if v in SIDE_NAMES:
        return SIDE_NAMES[v]
    # Extended IDs: 1-6 = player slots, 401-406 = opponent slots
    if v >= 401:
        return "敌方"
    if 1 <= v <= 6:
        return "我方"
    return None

def _attach_buff_meta(out: Dict[str, Any], buff_id: Optional[int]) -> None:
    if buff_id is None:
        return
    name = buff_name(buff_id)
    if name and not out.get("effect_name"):
        out["effect_name"] = name

def _attach_buffbase_meta(out: Dict[str, Any], base_id: Optional[int]) -> None:
    if base_id is None:
        return
    meta = get_buffbase_meta(base_id)
    if isinstance(meta, dict) and meta.get("name") and not out.get("effect_base_name"):
        out["effect_base_name"] = meta["name"]

def _extract_actor_target(msg: Dict[str, Any], out: Dict[str, Any]) -> None:
    actor = pick_first(collect_varints(msg, 1))
    target = pick_first(collect_varints(msg, 2))
    out["actor_side"] = actor
    out["actor_side_name"] = side_name(actor)
    out["target_side"] = target
    out["target_side_name"] = side_name(target)

def extract_inner_message(root: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not root.get("fields"):
        return None
    fs = root["fields"][0].get("sub")
    if fs is None or len(fs["fields"]) != 1:
        return None
    wrapper = fs["fields"][0]
    ws = wrapper.get("sub")
    if ws is None:
        return None
    return {"message_id": wrapper["field"], "fields": {"fields": ws["fields"]}}

# --- Protobuf 消息解析 ---
def parse_proto_message(data: bytes, *, depth: int = 0, max_depth: int = 10, max_fields: int = 5000) -> Dict[str, Any]:
    fields: List[Dict[str, Any]] = []
    off, clean = 0, True
    while off < len(data):
        if len(fields) >= max_fields:
            clean = False
            break
        start = off
        try:
            tag, off = read_varint(data, off)
        except ValueError:
            clean = False
            break
        field_no, wire_type = tag >> 3, tag & 7
        entry: Dict[str, Any] = {"field": field_no, "wire": wire_type, "offset": start}
        try:
            if wire_type == 0:
                entry["value"], off = read_varint(data, off)
            elif wire_type == 1:
                if off + 8 > len(data):
                    clean = False
                    break
                entry["raw_hex"] = data[off:off + 8].hex()
                off += 8
            elif wire_type == 2:
                blen, off = read_varint(data, off)
                if off + blen > len(data):
                    clean = False
                    break
                blob = data[off:off + blen]
                off += blen
                entry["len"] = blen
                entry["raw_hex"] = blob.hex()
                text = maybe_utf8(blob)
                if text is not None:
                    entry["text"] = text
                elif depth < max_depth and blob:
                    sub = parse_proto_message(blob, depth=depth + 1, max_depth=max_depth, max_fields=max_fields)
                    if sub["fields"] and sub["consumed"] == len(blob):
                        entry["sub"] = sub
            elif wire_type == 5:
                if off + 4 > len(data):
                    clean = False
                    break
                blob = data[off:off + 4]
                off += 4
                entry["raw_hex"] = blob.hex()
                entry["u32le"] = int.from_bytes(blob, "little")
            else:
                clean = False
                break
        except ValueError:
            clean = False
            break
        fields.append(entry)
    return {"fields": fields, "consumed": off, "clean": clean and off == len(data)}

# --- 辅助函数 ---
def walk_messages(msg: Dict[str, Any], path: str = "root") -> List[Tuple[str, Dict[str, Any]]]:
    out = [(path, msg)]
    per_field: Dict[int, int] = defaultdict(int)
    for entry in msg["fields"]:
        sub = entry.get("sub")
        if sub is None:
            continue
        per_field[entry["field"]] += 1
        out.extend(walk_messages(sub, f"{path}.{entry['field']}[{per_field[entry['field']]}]"))
    return out

def field_groups(msg: Optional[Dict[str, Any]]) -> Dict[int, List[Dict[str, Any]]]:
    if msg is None:
        return {}
    cached = msg.get("_groups")
    if isinstance(cached, dict):
        return cached
    grouped: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for entry in msg["fields"]:
        grouped[entry["field"]].append(entry)
    cached = dict(grouped)
    msg["_groups"] = cached
    return cached

def collect_varints(msg: Optional[Dict[str, Any]], field_no: int) -> List[int]:
    return [e["value"] for e in field_groups(msg).get(field_no, []) if "value" in e]

def first_text(msg: Dict[str, Any], field_no: int) -> Optional[str]:
    for e in field_groups(msg).get(field_no, []):
        if e.get("text"):
            return e["text"]
    return None

def first_sub(entries: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    return next((e["sub"] for e in entries if e.get("sub") is not None), None)

def pick_first(values: List[int], *, low: Optional[int] = None, high: Optional[int] = None) -> Optional[int]:
    for v in values:
        if (low is None or v >= low) and (high is None or v <= high):
            return v
    return values[0] if values else None

# --- 精灵/状态提取 ---
def _attach_skill_meta(out: Dict[str, Any], skill_id: Optional[int]) -> None:
    if skill_id is None:
        return
    name = skill_name(skill_id)
    if name and not out.get("skill_name"):
        out["skill_name"] = name
    meta = get_skill_meta(skill_id)
    if not meta:
        return
    for src, dst in (
        ("desc", "skill_desc"), ("energy_cost", "skill_energy_cost"),
        ("target_type", "skill_target_type"), ("target_count", "skill_target_count"),
        ("skill_priority", "skill_priority"), ("damage_type", "skill_damage_type"),
        ("skill_feature", "skill_feature"), ("cd_round", "skill_cd_round"),
    ):
        if src in meta and dst not in out:
            out[dst] = meta[src]

def extract_skills(msg: Dict[str, Any]) -> List[Dict[str, Any]]:
    skills, seen = [], set()
    for entry in field_groups(msg).get(12, []):
        sub = entry.get("sub")
        if sub is None:
            continue
        for child in sub["fields"]:
            cs = child.get("sub")
            if cs is None:
                continue
            sid = pick_first(collect_varints(cs, 1), low=1_000_000)
            if sid is None:
                continue
            slot = pick_first(collect_varints(cs, 5), low=0, high=8) or 0
            pp = pick_first(collect_varints(cs, 8), low=0, high=99)
            key = (sid, slot, pp)
            if key in seen:
                continue
            seen.add(key)
            item = {"skill_id": sid, "equipped_slot": slot, "pp": pp}
            _attach_skill_meta(item, sid)
            skills.append(item)
    skills.sort(key=lambda it: (it["equipped_slot"] == 0, it["equipped_slot"], it["skill_id"]))
    return skills


def extract_skills_from_round_data(msg: Dict[str, Any]) -> List[Dict[str, Any]]:
    """从 BattleInsidePetInfo.field 8 (PetSkillRoundData) 提取技能。

    比起 PetData.field 12 (PetSkillInfo)，这是 PvP 战斗中技能数据的实际来源。
    PetSkillRoundData: field 39=skill_id, field 25=pos, field 9=cost_energy。
    """
    skills, seen = [], set()
    for entry in field_groups(msg).get(8, []):
        sub = entry.get("sub")
        if sub is None:
            continue
        sid = pick_first(collect_varints(sub, 39))
        pos = pick_first(collect_varints(sub, 25))
        if sid is None or pos is None:
            continue
        key = (sid, pos)
        if key in seen:
            continue
        seen.add(key)
        cost_e = pick_first(collect_varints(sub, 9))
        item = {"skill_id": sid, "equipped_slot": pos, "pp": None, "cost_energy": cost_e}
        _attach_skill_meta(item, sid)
        skills.append(item)
    skills.sort(key=lambda it: (it["equipped_slot"] == 0, it["equipped_slot"], it["skill_id"]))
    return skills

def extract_stats(msg: Dict[str, Any]) -> List[Dict[str, Any]]:
    best: List[Dict[str, Any]] = []
    for entry in field_groups(msg).get(14, []):
        sub = entry.get("sub")
        if sub is None:
            continue
        stats = []
        for idx in range(1, 7):
            sf = field_groups(sub).get(idx, [])
            if not sf:
                continue
            ss = sf[0].get("sub")
            if ss is None:
                continue
            base = pick_first(collect_varints(ss, 1), low=0, high=9999)
            calc = pick_first(collect_varints(ss, 3), low=0, high=99999)
            bonus = pick_first(collect_varints(ss, 6), low=0, high=99999)
            total = (calc + bonus) if calc is not None and bonus is not None else calc
            stats.append({"index": idx, "name": STAT_NAMES[idx - 1], "base": base, "calc": calc, "bonus": bonus, "total": total})
        if len(stats) > len(best):
            best = stats
    return best

def extract_creature(msg: Dict[str, Any], *, path: str, record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    name = first_text(msg, 3)
    level = pick_first(collect_varints(msg, 10), low=1, high=100)
    if not name or level is None:
        return None
    slot = pick_first(collect_varints(msg, 1), low=0, high=999)
    pid = pick_first(collect_varints(msg, 2), low=1000)
    stats = extract_stats(msg)
    all_skills = extract_skills(msg)
    equipped = [it for it in all_skills if 1 <= it["equipped_slot"] <= 4]
    out: Dict[str, Any] = {
        "name": name, "level": level, "slot": slot, "pet_id": pid,
        "types": [SDT_TO_TYPE.get(v, v) for v in collect_varints(msg, 6)],
        "stats": stats, "max_hp": stats[0]["total"] if stats else None,
        "skills": all_skills,
        "equipped_skills": sorted(equipped, key=lambda it: (it["equipped_slot"], it["skill_id"])),
        "source_opcode": record["opcode"], "source_opcode_hex": record.get("opcode_hex", ""),
        "seq": record.get("seq"), "path": path,
    }
    pet_meta_data = get_pet_meta(pid)
    if isinstance(pet_meta_data, dict):
        if pet_meta_data.get("base_id") is not None:
            out["base_id"] = pet_meta_data["base_id"]
        if pet_meta_data.get("pet_info_id") is not None:
            out["pet_info_id"] = pet_meta_data["pet_info_id"]
    if out.get("base_id") is not None:
        skill_pool = get_pet_skill_meta(out["base_id"])
        if isinstance(skill_pool, dict):
            out["base_skill_pool"] = skill_pool.get("level_skills") or []
    wiki_types = get_wiki_pet_types(name)
    if wiki_types and wiki_types != out["types"]:
        logger.debug("Type mismatch for %s: protocol=%s, wiki=%s",
                     name, out["types"], wiki_types)
    return out

def _side_from_path(path: str) -> Optional[int]:
    """Determine side from wrapper path.

    0x1316 battle_enter:  ``root.6[N].(5|6)[N].2[*]`` → field 5=player(1), field 6=opponent(401).
    0x131A round_start:   ``root.3[N].2[N].44[N].8[N].3[N]`` → has ``.8[`` = opponent(401);
                           ``root.3[N].2[N].44[N].3[N]`` (no .8) = player(1).
    """
    import re
    # battle_enter pattern: .6[N].5[N] or .6[N].6[N]
    m = re.search(r"\.6\[\d+\]\.(\d+)\[", path)
    if m:
        f = int(m.group(1))
        if f == 5:
            return 1
        if f == 6:
            return 401
    # round_start pattern: .8[N] present → opponent
    if re.search(r"\.8\[\d+\]\.", path):
        return 401
    # round_start player pets have .44[N].3[N] without .8
    if re.search(r"\.44\[\d+\]\.", path):
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

    # 技能提取: 先用 PetData.field 12, 若为空则从 BattleInsidePetInfo.field 8 取
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

    return {
        "name": creature["name"], "level": creature["level"],
        "slot": creature["slot"], "pet_id": creature["pet_id"],
        "side": side_code,
        "types": creature.get("types", []),
        "battle_stats": ds[1:7] if len(ds) >= 7 else [],
        "battle_max_hp": max_hp, "max_hp": max_hp,
        "current_hp": current_hp, "hp": current_hp,
        "energy": ds[26] if len(ds) >= 27 else None,
        "stats": creature.get("stats", []),
        "skills": all_skills,
        "equipped_skills": equipped_skills,
        "skill_source": skill_source,
        "base_id": creature.get("base_id"),
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
    return _dedupe_state_wrappers(wrappers)

def _dedupe_state_wrappers(wrappers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out, seen = [], set()
    for it in wrappers:
        key = (it.get("name"), it.get("level"), it.get("slot"), it.get("pet_id"),
               tuple(it.get("battle_stats") or []), it.get("battle_max_hp"), it.get("current_hp"))
        if key not in seen:
            seen.add(key)
            out.append(it)
    out.sort(key=lambda it: (it.get("slot") is None, int(it.get("slot") or 0), int(it.get("pet_id") or 0)))
    return out

# --- 传输层解析 ---
def parse_special_payload(opcode: int, payload: bytes) -> Optional[Tuple[str, Dict[str, Any]]]:
    if opcode == 0x013D and len(payload) == 12:
        return "s2c_heartbeat_nty_binary", {
            "heartbeat_seq": int.from_bytes(payload[0:8], "little"),
            "server_logic_tick_ivl": int.from_bytes(payload[8:12], "little", signed=True),
        }
    if opcode == 0x013F and len(payload) == 40:
        return "s2c_heartbeat_result_binary", {
            "ret_info": {"ret_code": int.from_bytes(payload[0:4], "little")},
            "heartbeat_seq": int.from_bytes(payload[4:12], "little"),
            "server_time": int.from_bytes(payload[12:20], "little"),
        }
    return None

def _build_payload_root(opcode: int, payload: bytes) -> Tuple[Dict[str, Any], str, Optional[Dict[str, Any]]]:
    special = parse_special_payload(opcode, payload)
    if special:
        return {"fields": [], "consumed": len(payload), "clean": True}, special[0], special[1]
    if not payload:
        return {"fields": [], "consumed": 0, "clean": True}, "protobuf", None
    return parse_proto_message(payload), "protobuf", None

def _empty_root() -> Dict[str, Any]:
    return {"fields": [], "consumed": 0, "clean": True}

def _parse_record_v14(body: bytes, common: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if len(body) < 0x1E or body[4:6] != b"\x55\xaa" or body[24:26] != b"\x39\x63":
        return None
    reserved = int.from_bytes(body[10:12], "big")
    version = int.from_bytes(body[12:16], "big")
    record_len = int.from_bytes(body[6:10], "big")
    raw_payload = body[30:]
    trailer_len = tsf4g_trailer_len(raw_payload)
    no_trailer_len = len(body) - trailer_len
    if reserved != 0 or version not in {0, 1} or record_len != no_trailer_len - 4:
        return None
    transport_seq = int.from_bytes(body[0:4], "big")
    session_id = int.from_bytes(body[16:20], "big")
    sub_id = int.from_bytes(body[20:24], "big")
    req_seq = int.from_bytes(body[26:30], "big")
    payload = strip_tsf4g_padding(raw_payload)
    if common["direction"] == "c2s":
        raw_opcode = sub_id
        opcode, normalized = normalize_c2s_opcode(raw_opcode)
    else:
        raw_opcode = session_id
        opcode = session_id & 0xFFFF
        normalized = False
    root, payload_format, special_payload = _build_payload_root(opcode, payload)
    return {
        **common, "record_type": "business", "transport_kind": "tgcp_data",
        "transport_layout": "tgcp_4013_v14", "transport_seq": transport_seq,
        "record_len": record_len, "session_id": session_id,
        "session_id_hex": f"0x{session_id:08X}", "sub_id": sub_id,
        "sub_id_hex": f"0x{sub_id:08X}", "opcode": opcode,
        "opcode_hex": f"0x{opcode:04X}", "raw_opcode": raw_opcode,
        "raw_opcode_hex": f"0x{raw_opcode:08X}", "opcode_normalized": normalized,
        "req_seq": req_seq, "payload_len": len(payload),
        "payload_trailer_len": trailer_len, "root": root,
    }

def _parse_record_live_s2c(body: bytes, common: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if common["direction"] != "s2c" or len(body) < 10 or body[4:6] != b"\x55\xaa":
        return None
    opcode = int.from_bytes(body[0:4], "big")
    if not (0 < opcode <= 0xFFFF):
        return None
    subtype = int.from_bytes(body[6:10], "big")
    raw_payload = body[10:]
    trailer_len = tsf4g_trailer_len(raw_payload)
    payload = strip_tsf4g_padding(raw_payload)
    root, _, _ = _build_payload_root(opcode, payload)
    return {
        **common, "record_type": "business", "transport_kind": "tgcp_data",
        "transport_layout": "tgcp_4013_live_s2c", "opcode": opcode,
        "opcode_hex": f"0x{opcode:04X}", "subtype": subtype,
        "payload_len": len(payload), "payload_trailer_len": trailer_len, "root": root,
    }

def _parse_record_live_c2s(body: bytes, common: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if common["direction"] != "c2s" or len(body) < 14 or body[8:10] != b"\x39\x63":
        return None
    raw_opcode = int.from_bytes(body[4:8], "big")
    if not (raw_opcode >> 16 in {0x0000, 0x0001} and (raw_opcode & 0xFFFF) != 0):
        return None
    opcode, normalized = normalize_c2s_opcode(raw_opcode)
    req_seq = int.from_bytes(body[10:14], "big")
    raw_payload = body[14:]
    trailer_len = tsf4g_trailer_len(raw_payload)
    payload = strip_tsf4g_padding(raw_payload)
    root, _, _ = _build_payload_root(opcode, payload)
    return {
        **common, "record_type": "business", "transport_kind": "tgcp_data",
        "transport_layout": "tgcp_4013_live_c2s",
        "opcode": opcode, "opcode_hex": f"0x{opcode:04X}",
        "raw_opcode": raw_opcode, "raw_opcode_hex": f"0x{raw_opcode:08X}",
        "opcode_normalized": normalized, "req_seq": req_seq,
        "payload_len": len(payload), "payload_trailer_len": trailer_len, "root": root,
    }

def _parse_record_live_c2s_short_heartbeat(body: bytes, common: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if common["direction"] != "c2s" or len(body) < 16 or body.find(b"tsf4g", 8) < 0:
        return None
    opcode = int.from_bytes(body[6:8], "big")
    if opcode != 0x013E:
        return None
    req_seq = int.from_bytes(body[14:16], "little")
    leading_u32 = int.from_bytes(body[0:4], "big")
    return {
        **common, "record_type": "business", "transport_kind": "tgcp_data",
        "transport_layout": "tgcp_4013_live_c2s_short_heartbeat",
        "transport_seq": leading_u32, "prefix_u32": leading_u32,
        "prefix_u32_hex": f"0x{leading_u32:08X}",
        "opcode": opcode, "opcode_hex": f"0x{opcode:04X}",
        "format": "c2s_short_heartbeat", "req_seq": req_seq,
        "payload_len": 0, "root": _empty_root(),
    }


def parse_record(packet: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if packet.get("cmd") != 0x4013 or not packet.get("decrypted_body_hex"):
        return None
    body = bytes.fromhex(packet["decrypted_body_hex"])
    common = {"seq": packet["seq"], "direction": packet["direction"],
              "first_frame": packet.get("first_frame"), "first_time": packet.get("first_time")}
    return (_parse_record_v14(body, common)
            or _parse_record_live_s2c(body, common)
            or _parse_record_live_c2s(body, common)
            or _parse_record_live_c2s_short_heartbeat(body, common))

def parse_tgcp_control_packet(packet: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    cmd = int(packet.get("cmd", 0) or 0)
    if cmd == 0x4013:
        return None
    header_extra = bytes.fromhex(packet.get("header_extra_hex") or "")
    body = bytes.fromhex(packet.get("body_hex") or "")
    record: Dict[str, Any] = {
        "record_type": "tgcp_control", "transport_kind": "tgcp_control",
        "transport_layout": "be21_control", "seq": packet.get("seq"),
        "direction": packet.get("direction"), "cmd": cmd,
        "cmd_hex": f"0x{cmd:04X}", "tgcp_command_name": tgcp_command_name(cmd),
        "body_len": len(body),
    }
    if cmd == 0x1002 and len(header_extra) >= 18:
        key = header_extra[2:18]
        record["session_key_hex"] = key.hex()
        if all(32 <= b < 127 for b in key):
            record["session_key_ascii"] = key.decode("ascii", errors="ignore")
    return record
