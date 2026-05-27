"""TCP 流重组：处理乱序段、重传，重组为连续字节流后交给 BE21 解析。"""
from __future__ import annotations
import logging
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from src.capture.frame import Be21Packet, parse_be21_from_buffer

_MAX_BUFFER_SIZE = 16 * 1024 * 1024
_MAX_PENDING_BYTES = 8 * 1024 * 1024
_MAX_SEEN_ACKS = 256

logger = logging.getLogger(__name__)

class _BoundedAckSet:
    """有界去重集合"""
    def __init__(self, maxsize: int = _MAX_SEEN_ACKS) -> None:
        self._data: OrderedDict[Tuple[int, str], None] = OrderedDict()
        self._maxsize = maxsize

    def __contains__(self, item: Tuple[int, str]) -> bool:
        return item in self._data

    def add(self, item: Tuple[int, str]) -> None:
        if item in self._data:
            return
        if len(self._data) >= self._maxsize:
            self._data.popitem(last=False)
        self._data[item] = None

@dataclass
class DirectionState:
    """一个方向的 TCP 流状态"""
    direction: str
    buffer: bytearray = field(default_factory=bytearray)
    parse_offset: int = 0
    stream_base: int = 0
    _base_seq: Optional[int] = None
    _next_contig_seq: Optional[int] = None
    _pending: Dict[int, bytes] = field(default_factory=dict)
    _pending_bytes: int = 0

    def feed(self, seq: int, payload: bytes) -> List[Be21Packet]:
        """把 TCP 段按 seq 重组为连续字节流，再交给 BE21 解析器"""
        if not payload:
            return []
        if self._base_seq is None:
            self._base_seq = seq
            self.buffer.extend(payload)
            self._next_contig_seq = seq + len(payload)
        else:
            self._ingest_segment(seq, payload)
        if len(self.buffer) > _MAX_BUFFER_SIZE:
            self._trim_buffer()
        base = self.stream_base
        packets, new_off = parse_be21_from_buffer(self.buffer, self.direction, self.parse_offset)
        self.parse_offset = new_off
        for packet in packets:
            packet.stream_offset += base
        if self.parse_offset >= 0x10000 and self.parse_offset > len(self.buffer) // 2:
            trim = self.parse_offset
            del self.buffer[:trim]
            self.stream_base += trim
            if self._base_seq is not None:
                self._base_seq += trim
            self.parse_offset = 0
        return packets

    def _ingest_segment(self, seq: int, payload: bytes) -> None:
        assert self._base_seq is not None
        assert self._next_contig_seq is not None
        end = seq + len(payload)
        # Old segment entirely before base
        if seq < self._base_seq:
            if end < self._base_seq:
                return
            prepend_len = self._base_seq - seq
            if prepend_len > 0:
                self.buffer = bytearray(payload[:prepend_len]) + self.buffer
                self._base_seq = seq
                self.parse_offset += prepend_len
                self.stream_base = max(0, self.stream_base - prepend_len)
            if end <= self._next_contig_seq:
                return
            payload = payload[self._next_contig_seq - seq:]
            seq = self._next_contig_seq
            if not payload:
                return
        # In-order segment
        if seq <= self._next_contig_seq:
            start = seq - self._base_seq
            overlap = self._next_contig_seq - seq
            if overlap > 0 and start >= 0:
                overlap = min(overlap, len(payload))
                existing = bytes(self.buffer[start:start + overlap])
                incoming = payload[:overlap]
                if existing != incoming:
                    if start < self.parse_offset:
                        return
                    del self.buffer[start:]
                    self.buffer.extend(payload)
                    self._next_contig_seq = seq + len(payload)
                    self.parse_offset = min(self.parse_offset, start)
                    self._drain_pending()
                    return
            if overlap >= len(payload):
                return
            self.buffer.extend(payload[overlap:])
            self._next_contig_seq += len(payload) - overlap
            self._drain_pending()
            return
        # Out-of-order: store for later
        self._store_pending(seq, payload)

    def _store_pending(self, seq: int, payload: bytes) -> None:
        end = seq + len(payload)
        for old_seq, old_payload in list(self._pending.items()):
            old_end = old_seq + len(old_payload)
            if old_seq <= seq and old_end >= end:
                return
            if seq <= old_seq and end >= old_end:
                self._pending_bytes -= len(old_payload)
                del self._pending[old_seq]
        existing = self._pending.get(seq)
        if existing is not None:
            if len(existing) >= len(payload):
                return
            self._pending_bytes -= len(existing)
        self._pending[seq] = payload
        self._pending_bytes += len(payload)
        while self._pending_bytes > _MAX_PENDING_BYTES and self._pending:
            farthest_seq = max(self._pending)
            dropped = self._pending.pop(farthest_seq)
            self._pending_bytes -= len(dropped)

    def _drain_pending(self) -> None:
        assert self._next_contig_seq is not None
        while True:
            ready = [s for s in self._pending if s <= self._next_contig_seq]
            if not ready:
                return
            seq = min(ready)
            payload = self._pending.pop(seq)
            self._pending_bytes -= len(payload)
            overlap = self._next_contig_seq - seq
            if overlap >= len(payload):
                continue
            self.buffer.extend(payload[overlap:])
            self._next_contig_seq += len(payload) - overlap

    def _trim_buffer(self) -> None:
        if not self.buffer:
            return
        desired = _MAX_BUFFER_SIZE // 2
        if self.parse_offset > 0:
            trim = min(self.parse_offset, max(0, len(self.buffer) - desired))
        else:
            trim = max(0, len(self.buffer) - desired)
        if trim <= 0:
            return
        del self.buffer[:trim]
        self.stream_base += trim
        self.parse_offset = max(0, self.parse_offset - trim)
        if self._base_seq is not None:
            self._base_seq += trim

@dataclass
class FlowState:
    """双向 TCP 流状态"""
    flow_id: str
    client_ip: str
    client_port: int
    server_ip: str
    server_port: int
    c2s: DirectionState = field(default_factory=lambda: DirectionState("c2s"))
    s2c: DirectionState = field(default_factory=lambda: DirectionState("s2c"))
    seen_acks: _BoundedAckSet = field(default_factory=_BoundedAckSet)
    key: Optional[bytes] = None
    key_miss_count: int = 0
    key_missing_suppressed: bool = False
    key_missing_reported: bool = False

    def direction_state(self, direction: str) -> DirectionState:
        return self.c2s if direction == "c2s" else self.s2c
