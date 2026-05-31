"""核心协议解析模块。

本模块是协议解析的基础层，包含以下功能区域：

1. Protobuf 解析原语 — read_varint, parse_proto_message 等底层解析函数
2. TGCP 传输层解析 — 4种记录格式（v14, live_s2c, live_c2s, short_heartbeat）
3. 游戏常量 — STAT_NAMES, SIDE_NAMES, SDT_TO_TYPE, SPECIAL_ACTION_COMMANDS
4. 精灵/状态提取 — extract_creature, extract_state_wrapper 等高级提取函数
5. 辅助工具 — walk_messages, field_groups, collect_varints 等查询函数
"""
from __future__ import annotations
import logging
import re
import struct
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple
from src.data.loader import (
    enrich_buff_modifiers,
    get_attr_name,
    get_skill_name,
    get_skill_meta,
    get_pet_meta,
    get_pet_name,
    get_buff_meta,
    get_buffbase_meta,
    get_pet_skill_meta,
    get_pet_species_types,
    get_opcode_pb_meta,
)
from src.config import settings

logger = logging.getLogger(__name__)

_PROTO_SCHEMA_CACHE: Optional[Dict[str, Any]] = None

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
    if v >= 10_000_000 and v % 100 == 0:
        candidate = v // 100
        return candidate if get_skill_name(candidate) else candidate
    if get_skill_name(v):
        return v
    return v

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
# parse_proto_message 是核心递归解析器。
# 按 wire type 分派处理：
#   wire 0 = varint (直接读取数值)
#   wire 1 = 64-bit fixed (存为 raw_hex)
#   wire 2 = length-delimited (尝试 UTF-8 文本 → 递归解析子消息)
#   wire 5 = 32-bit fixed (存为 raw_hex + u32le)
# 解析结果为 {"fields": [...], "consumed": N, "clean": bool} 结构。
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


# --- Schema-aware decode ---

def _load_proto_schema() -> Dict[str, Any]:
    """Lazy-load proto_schema.json for optional schema-aware post-processing."""
    global _PROTO_SCHEMA_CACHE
    if _PROTO_SCHEMA_CACHE is not None:
        return _PROTO_SCHEMA_CACHE
    path = settings.data_dir / "proto_schema.json"
    try:
        import json
        with path.open("r", encoding="utf-8-sig") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        logger.warning("Failed to load proto schema %s: %s", path, exc)
        data = {}
    _PROTO_SCHEMA_CACHE = data if isinstance(data, dict) else {}
    return _PROTO_SCHEMA_CACHE


def _message_schema(message_name: Optional[str]) -> Optional[Dict[str, Any]]:
    if not message_name:
        return None
    messages = _load_proto_schema().get("messages", {})
    if not isinstance(messages, dict):
        return None
    for key in (message_name, f".Next.{message_name}", f"Next.{message_name}"):
        item = messages.get(key)
        if isinstance(item, dict):
            return item
    return None


def _schema_fields(message_schema: Dict[str, Any]) -> Dict[int, Dict[str, Any]]:
    fields = message_schema.get("fields", {})
    out: Dict[int, Dict[str, Any]] = {}
    if not isinstance(fields, dict):
        return out
    for key, value in fields.items():
        if not isinstance(value, dict):
            continue
        try:
            out[int(key)] = value
        except (TypeError, ValueError):
            continue
    return out


def _decode_packed_numeric(blob: bytes, field_type: str) -> List[Any]:
    if field_type in {"float"}:
        return [
            round(float(struct.unpack("<f", blob[i:i + 4])[0]), 6)
            for i in range(0, len(blob) - (len(blob) % 4), 4)
        ]
    values: List[Any] = []
    off = 0
    while off < len(blob):
        try:
            raw, off = read_varint(blob, off)
        except ValueError:
            return []
        values.append(_coerce_scalar(raw, field_type))
    return values


def _coerce_scalar(value: int, field_type: str) -> Any:
    if field_type == "bool":
        return bool(value)
    if field_type in {"int32", "int64", "sint32", "sint64"}:
        return maybe_signed64(value)
    if field_type == "enum":
        return {"value": maybe_signed64(value), "name": None}
    return value


def _decode_scalar_entry(entry: Dict[str, Any], field_type: str) -> Any:
    if entry.get("wire") == 5 and field_type == "float" and entry.get("raw_hex"):
        try:
            return round(float(struct.unpack("<f", bytes.fromhex(entry["raw_hex"]))[0]), 6)
        except (ValueError, struct.error):
            return None
    if entry.get("wire") == 2:
        if field_type in {"string"}:
            return entry.get("text")
        if field_type in {"bytes"}:
            return bytes.fromhex(entry.get("raw_hex", ""))
        raw = entry.get("raw_hex")
        if raw:
            packed = _decode_packed_numeric(bytes.fromhex(raw), field_type)
            return packed if packed else None
    if "value" in entry:
        return _coerce_scalar(entry["value"], field_type)
    return None


def decode_proto_by_schema(msg: Dict[str, Any], message_name: Optional[str]) -> Optional[Dict[str, Any]]:
    """Decode a parsed protobuf tree using proto_schema.json.

    The raw recursive tree remains the source of truth for fallback extractors; this
    helper only adds a named, schema-shaped view for semantic post-processing.
    """
    schema = _message_schema(message_name)
    if schema is None:
        return None
    field_specs = _schema_fields(schema)
    grouped = field_groups(msg)
    decoded: Dict[str, Any] = {}
    for field_no, entries in grouped.items():
        spec = field_specs.get(field_no)
        if spec is None:
            continue
        name = spec.get("name") or f"field_{field_no}"
        field_type = str(spec.get("type") or "")
        is_message = bool(spec.get("message"))
        repeated = bool(spec.get("repeated"))
        values: List[Any] = []
        for entry in entries:
            value: Any = None
            if is_message:
                sub = entry.get("sub")
                value = decode_proto_by_schema(sub, field_type) if sub is not None else None
            else:
                value = _decode_scalar_entry(entry, field_type)
            if value is None:
                continue
            if repeated and isinstance(value, list) and not is_message and entry.get("wire") == 2:
                values.extend(value)
            else:
                values.append(value)
        if not values:
            continue
        decoded[name] = values if repeated or len(values) > 1 else values[0]
    return decoded


def _attach_schema_decode(record: Dict[str, Any]) -> Dict[str, Any]:
    meta = get_opcode_pb_meta(record.get("opcode"))
    if not isinstance(meta, dict):
        return record
    message_name = meta.get("message")
    decoded = decode_proto_by_schema(record.get("root") or {}, message_name)
    if decoded is not None:
        record["_message_name"] = message_name
        record["_decoded"] = decoded
    return record

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
    return None

# --- 精灵/状态提取 ---
# extract_creature 从单个 protobuf 消息中提取完整的精灵信息。
# 提取流程: 名称(field 3) → 等级(field 10) → slot/pet_id → 属性值(field 14) → 技能(field 12)
# 同时附加 pet_meta 数据和 wiki 类型校验。
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
        ("skill_dam_type", "skill_dam_type"),
    ):
        if src in meta and dst not in out:
            out[dst] = meta[src]
    dam_type = meta.get("skill_dam_type")
    if dam_type is not None and "skill_element" not in out:
        out["skill_element"] = SDT_TO_TYPE.get(dam_type)

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
    for source_index, entry in enumerate(field_groups(msg).get(8, [])):
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
        item = {
            "skill_id": sid,
            "equipped_slot": pos,
            "pp": None,
            "cost_energy": cost_e,
            "source_index": source_index,
            "source": "battle_inside.skill_round_data",
        }
        _attach_skill_meta(item, sid)
        skills.append(item)
    skills.sort(key=lambda it: (it["equipped_slot"] == 0, it["equipped_slot"], it["skill_id"]))
    return skills


def extract_battle_buffs(msg: Dict[str, Any]) -> List[Dict[str, Any]]:
    """从 BattleInsidePetInfo.field 5 (BattleBuffInfo) 提取初始 buff 列表。

    BattleBuffInfo: field 2=buff_id, field 4=stack。
    包括先天特性 (innate trait) 所对应的 buff。
    """
    buffs: List[Dict[str, Any]] = []
    seen_ids: set = set()
    for entry in field_groups(msg).get(5, []):
        sub = entry.get("sub")
        if sub is None:
            continue
        buff_id = pick_first(collect_varints(sub, 2))
        if buff_id is None:
            continue
        if buff_id in seen_ids:
            continue
        seen_ids.add(buff_id)
        stack = pick_first(collect_varints(sub, 4))
        item = enrich_buff_modifiers({"id": buff_id, "name": buff_name(buff_id) or str(buff_id), "stage": stack})
        buffs.append(item)
    return buffs


def _extract_simple_items(msg: Dict[str, Any], field_no: int, spec: Dict[int, Tuple[str, bool]]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for entry in field_groups(msg).get(field_no, []):
        sub = entry.get("sub")
        if sub is None:
            continue
        item: Dict[str, Any] = {}
        for fn, (name, signed) in spec.items():
            value = pick_first(collect_varints(sub, fn))
            if value is not None:
                item[name] = maybe_signed64(value) if signed else value
        if item:
            items.append(item)
    return items


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
    base_conf_id = pick_first(collect_varints(msg, 15))
    stats = extract_stats(msg)
    all_skills = extract_skills(msg)
    equipped = [it for it in all_skills if 1 <= it["equipped_slot"] <= 4]
    out: Dict[str, Any] = {
        "name": name, "level": level, "slot": slot, "pet_id": pid,
        "base_conf_id": base_conf_id,
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
    base_id = out.get("base_id")
    if base_id:
        species_types = get_pet_species_types(base_id)
        if species_types and species_types != out["types"]:
            logger.debug("Type mismatch for %s (base_id=%s): protocol=%s, species=%s",
                         name, base_id, out["types"], species_types)
    return out

_RE_BATTLE_ENTER_SIDE = re.compile(r"\.6\[\d+\]\.(\d+)\[")
_RE_ROUND_START_OPP = re.compile(r"\.8\[\d+\]\.")
_RE_ROUND_START_PLAYER = re.compile(r"\.44\[\d+\]\.")

def _side_from_path(path: str) -> Optional[int]:
    """Determine side from wrapper path.

    0x1316 battle_enter:  ``root.6[N].(5|6)[N].2[*]`` → field 5=player(1), field 6=opponent(401).
    0x131A round_start:   ``root.3[N].2[N].44[N].8[N].3[N]`` → has ``.8[`` = opponent(401);
                           ``root.3[N].2[N].44[N].3[N]`` (no .8) = player(1).
    """
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


# extract_state_wrapper 从「动态属性 + 精灵信息」二合一消息中提取战斗状态。
# 结构: field 1 = 动态属性（HP/能量/battle_stats）, field 2 = 精灵基本信息
# 技能提取采用双策略：先从 PetData.field 12 取，若为空则从 InsideInfo.field 8 取
# (PvP 战斗中实际技能来源通常是 InsideInfo.field 8)
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

    # 初始 buff 列表 (含先天特性) from BattleInsidePetInfo.field 5
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
    # 先天特性/被动技能 from BattleInsidePetInfo.field 64
    passive_skill_id = pick_first(collect_varints(dm, 64))
    # 能量来自 PetData.field 33。battle_attr[26] 是"宠物伤害类型1"，不是能量。
    # PetData.energy 在 battle_enter 时为 0（未设置），在 round_start 时为实际值。
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
        "sp_energy": _extract_simple_items(dm, 15, {
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
        "remain_buff_infos": _extract_simple_items(dm, 39, {
            1: ("buff_id", True),
            2: ("stack", True),
        }),
        "extra_sdt": _extract_simple_items(dm, 41, {
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
# TGCP (Tencent Game Communication Protocol) 传输层有 4 种记录格式：
# 1. v14 — 标准格式，30字节头（magic 0x55AA/0x3963），含 session_id/sub_id/opcode
# 2. live_s2c — 服务端直推格式，10字节头（magic 0x55AA），opcode 在前4字节
# 3. live_c2s — 客户端直推格式，14字节头（magic 0x3963），含 raw_opcode 和 req_seq
# 4. live_c2s_short_heartbeat — 客户端短心跳，16字节，固定 opcode 0x013E
# parse_record 按优先级依次尝试四种格式，首次匹配即返回。
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

def _is_probable_business_opcode(opcode: int) -> bool:
    return isinstance(opcode, int) and get_opcode_pb_meta(opcode) is not None

def _finalize_record(record: Dict[str, Any]) -> Dict[str, Any]:
    return _attach_schema_decode(record)

# v14 格式布局 (30字节头):
# [0:4]   transport_seq (big-endian)
# [4:6]   magic 0x55AA
# [6:10]  record_len (big-endian)
# [10:12] reserved (must be 0)
# [12:16] version (0 or 1)
# [16:20] session_id → s2c 用作 opcode (取低16位)
# [20:24] sub_id → c2s 用作 raw_opcode (高16位可能为 0x0001 前缀)
# [24:26] magic 0x3963
# [26:30] req_seq
# [30:]   payload (带 tsf4g padding)
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
    return _finalize_record({
        **common, "record_type": "business", "transport_kind": "tgcp_data",
        "transport_layout": "tgcp_4013_v14", "transport_seq": transport_seq,
        "record_len": record_len, "session_id": session_id,
        "session_id_hex": f"0x{session_id:08X}", "sub_id": sub_id,
        "sub_id_hex": f"0x{sub_id:08X}", "opcode": opcode,
        "opcode_hex": f"0x{opcode:04X}", "raw_opcode": raw_opcode,
        "raw_opcode_hex": f"0x{raw_opcode:08X}", "opcode_normalized": normalized,
        "req_seq": req_seq, "payload_len": len(payload),
        "payload_trailer_len": trailer_len, "root": root,
    })

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
    return _finalize_record({
        **common, "record_type": "business", "transport_kind": "tgcp_data",
        "transport_layout": "tgcp_4013_live_s2c", "opcode": opcode,
        "opcode_hex": f"0x{opcode:04X}", "subtype": subtype,
        "payload_len": len(payload), "payload_trailer_len": trailer_len, "root": root,
    })

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
    return _finalize_record({
        **common, "record_type": "business", "transport_kind": "tgcp_data",
        "transport_layout": "tgcp_4013_live_c2s",
        "opcode": opcode, "opcode_hex": f"0x{opcode:04X}",
        "raw_opcode": raw_opcode, "raw_opcode_hex": f"0x{raw_opcode:08X}",
        "opcode_normalized": normalized, "req_seq": req_seq,
        "payload_len": len(payload), "payload_trailer_len": trailer_len, "root": root,
    })

def _parse_record_live_c2s_no_magic(body: bytes, common: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Parse observed c2s business packets that omit the 0x3963 marker.

    Layout matches live_c2s except bytes [8:10] are an opaque marker rather than
    the magic value.  Guard with opcode metadata and a clean protobuf payload to
    avoid treating arbitrary c2s blobs as business records.
    """
    if common["direction"] != "c2s" or len(body) < 14 or body[8:10] == b"\x39\x63":
        return None
    prefix_u32 = int.from_bytes(body[0:4], "big")
    raw_opcode = int.from_bytes(body[4:8], "big")
    opcode, normalized = normalize_c2s_opcode(raw_opcode)
    if not _is_probable_business_opcode(opcode):
        return None
    req_seq = int.from_bytes(body[10:14], "big")
    raw_payload = body[14:]
    trailer_len = tsf4g_trailer_len(raw_payload)
    payload = strip_tsf4g_padding(raw_payload)
    root, _, _ = _build_payload_root(opcode, payload)
    if not root.get("clean"):
        return None
    if any(entry.get("field") == 0 for entry in root.get("fields", [])):
        return None
    return _finalize_record({
        **common, "record_type": "business", "transport_kind": "tgcp_data",
        "transport_layout": "tgcp_4013_live_c2s_no_magic",
        "transport_seq": prefix_u32, "prefix_u32": prefix_u32,
        "prefix_u32_hex": f"0x{prefix_u32:08X}",
        "opcode": opcode, "opcode_hex": f"0x{opcode:04X}",
        "raw_opcode": raw_opcode, "raw_opcode_hex": f"0x{raw_opcode:08X}",
        "opcode_normalized": normalized,
        "marker_u16": int.from_bytes(body[8:10], "big"),
        "marker_u16_hex": f"0x{int.from_bytes(body[8:10], 'big'):04X}",
        "req_seq": req_seq,
        "payload_len": len(payload), "payload_trailer_len": trailer_len,
        "root": root,
    })

def _parse_record_live_c2s_short_heartbeat(body: bytes, common: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if common["direction"] != "c2s" or len(body) < 16 or body.find(b"tsf4g", 8) < 0:
        return None
    opcode = int.from_bytes(body[6:8], "big")
    if opcode != 0x013E:
        return None
    req_seq = int.from_bytes(body[14:16], "little")
    leading_u32 = int.from_bytes(body[0:4], "big")
    return _finalize_record({
        **common, "record_type": "business", "transport_kind": "tgcp_data",
        "transport_layout": "tgcp_4013_live_c2s_short_heartbeat",
        "transport_seq": leading_u32, "prefix_u32": leading_u32,
        "prefix_u32_hex": f"0x{leading_u32:08X}",
        "opcode": opcode, "opcode_hex": f"0x{opcode:04X}",
        "format": "c2s_short_heartbeat", "req_seq": req_seq,
        "payload_len": 0, "root": _empty_root(),
    })


# parse_record 是传输层的入口函数。
# 只处理 TGCP DATA (cmd=0x4013) 包，依次尝试四种记录格式。
# 返回 None 表示无法识别的格式。
def parse_record(packet: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if packet.get("cmd") != 0x4013 or not packet.get("decrypted_body_hex"):
        return None
    body = bytes.fromhex(packet["decrypted_body_hex"])
    common = {"seq": packet["seq"], "direction": packet["direction"],
              "first_frame": packet.get("first_frame"), "first_time": packet.get("first_time")}
    return (_parse_record_v14(body, common)
            or _parse_record_live_s2c(body, common)
            or _parse_record_live_c2s(body, common)
            or _parse_record_live_c2s_no_magic(body, common)
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
