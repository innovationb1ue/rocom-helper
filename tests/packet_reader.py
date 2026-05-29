"""Binary packet file reader for RC01 format captured by PacketLogger."""
from __future__ import annotations

import json
import struct
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.protocol.proto_core import parse_record, extract_inner_message
from src.protocol.opcodes import summarize
from src.analysis.constants import AUX_BATTLE_OPCODES, IN_BATTLE_OPCODES, LIFECYCLE_OPCODES

MAGIC_V1 = b"RC01"

BATTLE_OPCODES = frozenset(LIFECYCLE_OPCODES | IN_BATTLE_OPCODES | AUX_BATTLE_OPCODES)


def read_bin_packet(filepath: Path) -> Dict[str, Any]:
    with open(filepath, "rb") as f:
        magic = f.read(4)
        if magic != MAGIC_V1:
            raise ValueError(f"Invalid magic: {magic!r} in {filepath}")

        cmd = struct.unpack(">H", f.read(2))[0]
        seq = struct.unpack(">I", f.read(4))[0]
        direction = f.read(4).rstrip(b"\x00").decode("ascii")

        hdr_extra_len = struct.unpack(">I", f.read(4))[0]
        header_extra = f.read(hdr_extra_len)

        body_len = struct.unpack(">I", f.read(4))[0]
        body = f.read(body_len)

        decrypted_len = struct.unpack(">I", f.read(4))[0]
        decrypted_body = f.read(decrypted_len) if decrypted_len > 0 else None

        meta_len = struct.unpack(">I", f.read(4))[0]
        meta_bytes = f.read(meta_len)
        metadata = json.loads(meta_bytes.decode("utf-8"))

    pkt = {
        "cmd": cmd,
        "direction": direction,
        "seq": seq,
        "body_len": body_len,
        "header_extra_hex": header_extra.hex(),
        "body_hex": body.hex(),
        "decrypted_body_hex": decrypted_body.hex() if decrypted_body else "",
        "_metadata": metadata,
    }
    return pkt


def _extract_timestamp(filename: str) -> str:
    """Extract timestamp portion from filename for sorting."""
    # Format: {direction}_{cmd_hex}_{seq:04d}_{HHMMSS.mmm}.bin
    parts = filename.rsplit("_", 1)
    if len(parts) == 2:
        return parts[1].replace(".bin", "")
    return ""


def load_battle_packets(session_dir: Path) -> List[Dict[str, Any]]:
    """Load battle-related packets from a session directory, sorted by timestamp."""
    packets = []
    for fpath in sorted(session_dir.glob("*.bin"), key=lambda p: _extract_timestamp(p.name)):
        pkt = read_bin_packet(fpath)
        if pkt["cmd"] != 0x4013 or not pkt["decrypted_body_hex"]:
            continue
        record = parse_record(pkt)
        if record is None:
            continue
        opcode = record.get("opcode", 0)
        if opcode not in BATTLE_OPCODES:
            continue
        packets.append({
            "packet": pkt,
            "record": record,
            "opcode": opcode,
            "filename": fpath.name,
        })
    return packets


def replay_battle(packets: List[Dict[str, Any]]) -> tuple:
    """Replay battle packets through the full pipeline, return (events_log, final_state)."""
    from src.analysis.battle_state import BattleStateTracker

    tracker = BattleStateTracker()
    events = []

    for item in packets:
        record = item["record"]
        opcode = item["opcode"]

        inner = None
        if opcode == 0x0414:
            inner = extract_inner_message(record.get("root", {}))

        kind, summary = summarize(record, inner)

        detail = summary.get("detail", summary)
        if detail is None:
            detail = {}

        state = tracker.handle_event(opcode, detail)

        events.append({
            "opcode": opcode,
            "kind": kind,
            "detail": detail,
            "state": state,
            "filename": item["filename"],
        })

    return events, tracker.get_state()
