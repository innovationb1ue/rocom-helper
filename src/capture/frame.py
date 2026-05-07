"""BE21 帧解析：从 TCP 字节流中提取 BE21 协议帧。"""
from __future__ import annotations
import logging
from dataclasses import dataclass
from typing import List, Tuple

logger = logging.getLogger(__name__)

MAGIC = b"\x33\x66"
FIXED_HDR_LEN = 21
_KNOWN_CMD_RANGE = range(0x0001, 0x8000)
_MAX_BUFFER_SIZE = 16 * 1024 * 1024
_MAX_PENDING_BYTES = 8 * 1024 * 1024
_MAX_SEEN_ACKS = 256

@dataclass
class Be21Packet:
    direction: str
    stream_offset: int
    cmd: int
    seq: int
    hdr_len: int
    body_len: int
    header_extra: bytes
    body: bytes

def _validate_be21_header(data: bytearray, off: int) -> bool:
    """验证 BE21 帧头的合法性"""
    if off + FIXED_HDR_LEN > len(data):
        return False
    cmd = int.from_bytes(data[off + 6:off + 8], "big")
    hdr_len = int.from_bytes(data[off + 13:off + 17], "big")
    body_len = int.from_bytes(data[off + 17:off + 21], "big")
    if cmd not in _KNOWN_CMD_RANGE:
        return False
    if hdr_len < FIXED_HDR_LEN:
        return False
    if (hdr_len + body_len) > 4 * 1024 * 1024:
        return False
    return True

def parse_be21_from_buffer(data: bytearray, direction: str, start: int) -> Tuple[List[Be21Packet], int]:
    """从缓冲区解析所有完整的 BE21 帧"""
    packets: List[Be21Packet] = []
    off = start
    size = len(data)
    while off + FIXED_HDR_LEN <= size:
        if data[off:off + 2] != MAGIC:
            nxt = data.find(MAGIC, off + 1)
            if nxt < 0:
                break
            off = nxt
            continue
        if not _validate_be21_header(data, off):
            off += 2
            continue
        cmd = int.from_bytes(data[off + 6:off + 8], "big")
        seq = int.from_bytes(data[off + 9:off + 13], "big")
        hdr_len = int.from_bytes(data[off + 13:off + 17], "big")
        body_len = int.from_bytes(data[off + 17:off + 21], "big")
        pkt_len = hdr_len + body_len
        if off + pkt_len > size:
            break
        packets.append(Be21Packet(
            direction=direction,
            stream_offset=off,
            cmd=cmd,
            seq=seq,
            hdr_len=hdr_len,
            body_len=body_len,
            header_extra=bytes(data[off + FIXED_HDR_LEN:off + hdr_len]),
            body=bytes(data[off + hdr_len:off + pkt_len]),
        ))
        off += pkt_len
    return packets, off
