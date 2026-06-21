"""RC01 包文件读取与元信息解析。"""
from __future__ import annotations

import json
import os
import struct
from pathlib import Path
from typing import Any, Dict, Optional

from src.analysis.reporting.models import BattleReportError

MAGIC_V1 = b"RC01"
DATA_CMD_PATTERN = "*_0x4013_*.bin"


def read_bin_packet(filepath: Path) -> Dict[str, Any]:
    with open(filepath, "rb") as f:
        magic = f.read(4)
        if magic != MAGIC_V1:
            raise BattleReportError(f"Invalid packet magic in {filepath.name}")
        cmd = struct.unpack(">H", f.read(2))[0]
        seq = struct.unpack(">I", f.read(4))[0]
        direction = f.read(4).rstrip(b"\x00").decode("ascii")
        header_extra_len = struct.unpack(">I", f.read(4))[0]
        header_extra = f.read(header_extra_len)
        body_len = struct.unpack(">I", f.read(4))[0]
        body = f.read(body_len)
        decrypted_len = struct.unpack(">I", f.read(4))[0]
        decrypted_body = f.read(decrypted_len) if decrypted_len > 0 else None
        meta_len = struct.unpack(">I", f.read(4))[0]
        metadata = json.loads(f.read(meta_len).decode("utf-8")) if meta_len else {}

    return {
        "cmd": cmd,
        "direction": direction,
        "seq": seq,
        "body_len": body_len,
        "header_extra_hex": header_extra.hex(),
        "body_hex": body.hex(),
        "decrypted_body_hex": decrypted_body.hex() if decrypted_body else "",
        "_metadata": metadata,
    }


def read_metadata(filepath: Path) -> Optional[Dict[str, Any]]:
    try:
        with open(filepath, "rb") as f:
            if f.read(4) != MAGIC_V1:
                return None
            f.read(2)
            f.read(4)
            f.read(4)
            header_extra_len = struct.unpack(">I", f.read(4))[0]
            f.seek(header_extra_len, os.SEEK_CUR)
            body_len = struct.unpack(">I", f.read(4))[0]
            f.seek(body_len, os.SEEK_CUR)
            decrypted_len = struct.unpack(">I", f.read(4))[0]
            f.seek(decrypted_len, os.SEEK_CUR)
            meta_len = struct.unpack(">I", f.read(4))[0]
            if meta_len <= 0 or meta_len > 1_000_000:
                return None
            return json.loads(f.read(meta_len).decode("utf-8"))
    except Exception:
        return None


def parse_opcode_hex(meta: Dict[str, Any]) -> Optional[int]:
    opcode_hex = meta.get("opcode_hex")
    if not opcode_hex:
        return None
    try:
        return int(opcode_hex, 16)
    except ValueError:
        return None


def extract_timestamp(filename: str) -> str:
    parts = filename.rsplit("_", 1)
    if len(parts) == 2:
        return parts[1].replace(".bin", "")
    return ""


def ts_to_seconds(ts: str) -> float:
    ts = ts.strip()
    return int(ts[0:2]) * 3600 + int(ts[2:4]) * 60 + float(ts[4:])

