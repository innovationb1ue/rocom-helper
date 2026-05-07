"""增量 diff 计算、格式化输出、变更应用。"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List


class ChangeType(Enum):
    ADDED = "added"
    MODIFIED = "modified"
    REMOVED = "removed"


@dataclass
class FieldDiff:
    field: str
    old_val: Any
    new_val: Any


@dataclass
class Change:
    change_type: ChangeType
    key: str
    name: str
    record: dict
    field_diffs: List[FieldDiff] = field(default_factory=list)


def compute_diff(
    existing: Dict[str, dict],
    new_data: Dict[str, dict],
    key_field: str = "wiki_name",
) -> List[Change]:
    """以 key_field 为主键对比新旧数据，返回变更列表。"""
    changes = []

    for k, new_rec in new_data.items():
        old_rec = existing.get(k)
        if old_rec is None:
            changes.append(Change(
                change_type=ChangeType.ADDED,
                key=k,
                name=new_rec.get("name", k),
                record=new_rec,
            ))
        else:
            diffs = _field_diffs(old_rec, new_rec)
            if diffs:
                changes.append(Change(
                    change_type=ChangeType.MODIFIED,
                    key=k,
                    name=new_rec.get("name", k),
                    record=new_rec,
                    field_diffs=diffs,
                ))

    for k, old_rec in existing.items():
        if k not in new_data:
            changes.append(Change(
                change_type=ChangeType.REMOVED,
                key=k,
                name=old_rec.get("name", k),
                record=old_rec,
            ))

    return changes


def format_diff(changes: List[Change], label: str) -> str:
    """生成人类可读的 diff 输出。"""
    added = [c for c in changes if c.change_type == ChangeType.ADDED]
    modified = [c for c in changes if c.change_type == ChangeType.MODIFIED]
    removed = [c for c in changes if c.change_type == ChangeType.REMOVED]
    unchanged = 0  # 无法精确计算，需要总数

    lines = [f"\n{'='*3} {label} {'='*3}"]

    if added:
        lines.append(f"新增 ({len(added)}):")
        for c in added[:30]:
            lines.append(f"  + {_pet_summary(c.record)}")
        if len(added) > 30:
            lines.append(f"  ... 还有 {len(added) - 30} 条")

    if modified:
        lines.append(f"修改 ({len(modified)}):")
        for c in modified[:30]:
            diff_str = ", ".join(
                f"{d.field}: {_fmt(d.old_val)}→{_fmt(d.new_val)}"
                for d in c.field_diffs
            )
            lines.append(f"  ~ {c.name}: {diff_str}")
        if len(modified) > 30:
            lines.append(f"  ... 还有 {len(modified) - 30} 条")

    if removed:
        lines.append(f"移除 ({len(removed)}) [仅警告，不自动删除]:")
        for c in removed[:10]:
            lines.append(f"  - {c.name}")

    if not added and not modified and not removed:
        lines.append("无变更。")

    return "\n".join(lines)


def format_skill_diff(changes: List[Change], label: str) -> str:
    """技能 diff 格式化（更紧凑）。"""
    added = [c for c in changes if c.change_type == ChangeType.ADDED]
    modified = [c for c in changes if c.change_type == ChangeType.MODIFIED]
    removed = [c for c in changes if c.change_type == ChangeType.REMOVED]

    lines = [f"\n{'='*3} {label} {'='*3}"]

    if added:
        lines.append(f"新增 ({len(added)}):")
        for c in added[:20]:
            rec = c.record
            lines.append(
                f"  + {rec.get('name', '?')} [{rec.get('type_name', '?')}]"
                f" 威力:{rec.get('power', 0)}"
            )
        if len(added) > 20:
            lines.append(f"  ... 还有 {len(added) - 20} 条")

    if modified:
        lines.append(f"修改 ({len(modified)}):")
        for c in modified[:20]:
            diff_str = ", ".join(
                f"{d.field}: {_fmt(d.old_val)}→{_fmt(d.new_val)}"
                for d in c.field_diffs
            )
            lines.append(f"  ~ {c.name}: {diff_str}")

    if removed:
        lines.append(f"移除 ({len(removed)}) [仅警告]:")
        for c in removed[:10]:
            lines.append(f"  - {c.name}")

    if not added and not modified and not removed:
        lines.append("无变更。")

    return "\n".join(lines)


def apply_diff(
    existing: Dict[str, dict],
    changes: List[Change],
) -> Dict[str, dict]:
    """应用 Added + Modified 变更，返回新 dict。"""
    result = dict(existing)
    for c in changes:
        if c.change_type in (ChangeType.ADDED, ChangeType.MODIFIED):
            result[c.key] = c.record
    return result


def load_indexed(path: str, key: str = "wiki_name") -> Dict[str, dict]:
    """加载 JSON 数组文件并按 key 索引。"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return {r.get(key, ""): r for r in data if r.get(key)}
        return {}
    except FileNotFoundError:
        return {}


def save_json(path: str, data: Any) -> None:
    """保存 JSON 文件（格式化输出）。"""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _field_diffs(old: dict, new: dict) -> List[FieldDiff]:
    """逐字段对比，返回有差异的字段列表。"""
    diffs = []
    all_keys = set(old.keys()) | set(new.keys())
    for k in sorted(all_keys):
        ov = old.get(k)
        nv = new.get(k)
        if ov != nv:
            diffs.append(FieldDiff(field=k, old_val=ov, new_val=nv))
    return diffs


def _pet_summary(rec: dict) -> str:
    types = "/".join(rec.get("type_names", []))
    stats = rec.get("stats", {})
    s = (
        f"[{types}]"
        f" HP:{stats.get('HP', '?')}"
        f" ATK:{stats.get('ATK', '?')}"
        f" SPA:{stats.get('SPA', '?')}"
        f" DEF:{stats.get('DEF', '?')}"
        f" SPD:{stats.get('SPD', '?')}"
        f" SPE:{stats.get('SPE', '?')}"
    )
    stage = rec.get("stage", "")
    if stage:
        s += f" 阶段:{stage}"
    return f"{rec.get('name', '?')} {s}"


def _fmt(val: Any) -> str:
    if isinstance(val, list):
        return ",".join(str(v) for v in val)
    return str(val)
