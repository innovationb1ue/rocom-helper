"""Round-flow lifecycle opcode extraction."""
from __future__ import annotations

from typing import Any, Dict

from src.protocol.proto_core import (
    collect_varints,
    field_groups,
    extract_state_wrappers_from_record,
)
from src.protocol.battle_schema import (
    _schema_or_raw,
    _schema_payload,
    _schema_quality,
)


def extract_1312_round_flow(record: Dict[str, Any]) -> Dict[str, Any]:
    """Extract round-flow details from opcode 0x1312."""
    out: Dict[str, Any] = {"extract_kind": "round_flow"}

    payload = _schema_payload(record, "ZoneBattleRoundFlowNotify")
    if payload is not None:
        for key, value in payload.items():
            if key not in out:
                out[key] = value
        _schema_quality(out, message="ZoneBattleRoundFlowNotify", found=True)
    else:
        root = record.get("root")
        if root is not None:
            groups = field_groups(root)
            for field_no in sorted(groups.keys()):
                entries = groups[field_no]
                values = collect_varints(root, field_no)
                if values:
                    out[f"field_{field_no}_varints"] = values
                for entry in entries:
                    if entry.get("text"):
                        out[f"field_{field_no}_text"] = entry["text"]
                        break
        _schema_quality(out, message="ZoneBattleRoundFlowNotify", found=False)

    wrappers = extract_state_wrappers_from_record(record)
    if wrappers:
        out["wrappers"] = wrappers

    out["opcode"] = record.get("opcode")
    out["opcode_hex"] = record.get("opcode_hex", "")
    return out


def extract_1313_round_confirm(record: Dict[str, Any]) -> Dict[str, Any]:
    """0x1313 BattleRoundConfirmNotify — round confirm."""
    detail = _schema_or_raw(record, "ZoneBattleRoundFlowFinishReq")
    detail["opcode"] = record.get("opcode")
    detail["opcode_hex"] = record.get("opcode_hex", "")
    return detail


def extract_1314_round_confirm_rsp(record: Dict[str, Any]) -> Dict[str, Any]:
    """0x1314 BattleRoundConfirmRsp — round confirm response."""
    detail = _schema_or_raw(record, "ZoneBattleRoundFlowFinishRsp")
    detail["opcode"] = record.get("opcode")
    detail["opcode_hex"] = record.get("opcode_hex", "")
    return detail
