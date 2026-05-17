"""顶层捕获编排器：封装 Scapy AsyncSniffer，管理 TCP 流重组和密钥提取。"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

try:
    from scapy.all import AsyncSniffer, TCP, IP  # type: ignore
    HAS_SCAPY = True
except ImportError:
    HAS_SCAPY = False

from src.capture.frame import Be21Packet
from src.capture.reassembly import FlowState
from src.capture.key_capture import extract_key_from_ack, is_ack_packet
from src.capture.crypto import decrypt_4013_body, write_key_file, printable_ascii
from src.protocol.proto_core import parse_record, parse_tgcp_control_packet, extract_inner_message
from src.protocol.opcodes import summarize

_DEFAULT_PORT = 8195
_DEFAULT_BPF = "tcp port 8195"


def _flow_key_from_packet(packet: Any, port: int) -> Optional[Tuple[str, int, str, int]]:
    """从 TCP 包提取流标识 (client_ip, client_port, server_ip, server_port)。"""
    if not packet.haslayer(IP) or not packet.haslayer(TCP):
        return None
    src_ip = packet[IP].src
    dst_ip = packet[IP].dst
    src_port = packet[TCP].sport
    dst_port = packet[TCP].dport
    if dst_port == port:
        return (src_ip, src_port, dst_ip, dst_port)
    elif src_port == port:
        return (dst_ip, dst_port, src_ip, src_port)
    return None


class Sniffer:
    """网络抓包编排器。

    事件回调:
        on_event(event_type, data) — 连接生命周期事件
            "flow_created"   — 新 TCP 流建立 {"flow_id": ...}
            "flow_closed"    — TCP 流关闭 (FIN/RST) {"flow_id": ...}
            "key_captured"   — 密钥捕获 {"flow_id": ..., "key_hex": ...}
            "record"         — 解析出的业务/控制包 {"record": ...}
    """

    def __init__(self, port: int = _DEFAULT_PORT, key_file: str = "session_key.txt",
                 preset_key: Optional[bytes] = None,
                 on_record: Optional[Callable[[Dict[str, Any]], None]] = None,
                 packet_logger: Optional[Any] = None,
                 on_event: Optional[Callable[[str, Dict[str, Any]], None]] = None) -> None:
        if not HAS_SCAPY:
            raise RuntimeError("Scapy not installed. Install with: pip install scapy")
        self.port = port
        self.key_file = key_file
        self.preset_key = preset_key
        self.on_record = on_record
        self.pkt_logger = packet_logger
        self.on_event = on_event
        self.flows: Dict[Tuple[str, int, str, int], FlowState] = {}
        self._sniffer: Optional[AsyncSniffer] = None
        self._running = False
        self._lock = threading.Lock()
        self.stats: Dict[str, int] = {"decrypt_ok": 0, "decrypt_fail": 0, "key_miss": 0}

    def _emit(self, event_type: str, data: Dict[str, Any]) -> None:
        if self.on_event:
            try:
                self.on_event(event_type, data)
            except Exception:
                logger.debug("on_event callback raised", exc_info=True)

    def _get_or_create_flow(self, fk: Tuple[str, int, str, int]) -> FlowState:
        with self._lock:
            flow = self.flows.get(fk)
            if flow is None:
                client_ip, client_port, server_ip, server_port = fk
                flow_id = f"{client_ip}:{client_port}-{server_ip}:{server_port}"
                flow = FlowState(
                    flow_id=flow_id,
                    client_ip=client_ip,
                    client_port=client_port,
                    server_ip=server_ip,
                    server_port=server_port,
                    key=self.preset_key,
                )
                self.flows[fk] = flow
                if self.preset_key:
                    write_key_file(self.key_file, self.preset_key, flow_id)
                logger.info("新 TCP 流: %s", flow_id)
            return flow

    def _process_packet(self, packet: Any) -> None:
        """处理一个 Scapy 捕获的包。"""
        if not packet.haslayer(TCP):
            return

        tcp = packet[TCP]
        payload = bytes(tcp.payload)

        # 检测 FIN/RST（连接关闭）
        flags = int(tcp.flags)
        is_fin = bool(flags & 0x01)
        is_rst = bool(flags & 0x04)

        if is_fin or is_rst:
            fk = _flow_key_from_packet(packet, self.port)
            if fk is not None:
                with self._lock:
                    flow = self.flows.get(fk)
                if flow is not None:
                    reason = "RST" if is_rst else "FIN"
                    logger.info("TCP %s: %s", reason, flow.flow_id)
                    self._emit("flow_closed", {"flow_id": flow.flow_id, "reason": reason})
            return

        # 只有有 payload 的包才做流重组和解析
        if not payload:
            return

        fk = _flow_key_from_packet(packet, self.port)
        if fk is None:
            return

        flow = self._get_or_create_flow(fk)

        # 首次创建 flow 时通知
        if flow.c2s._base_seq is None and flow.s2c._base_seq is None:
            # 第一个有 payload 的包，确认 flow 是新的
            pass

        direction = "c2s" if tcp.dport == self.port else "s2c"
        seq = int(tcp.seq)
        for be21 in flow.direction_state(direction).feed(seq, payload):
            self._handle_be21(flow, be21)

    def _handle_be21(self, flow: FlowState, be21: Be21Packet) -> None:
        """处理一个 BE21 帧：密钥提取或解密解析。"""
        plog = self.pkt_logger

        # 密钥提取
        if is_ack_packet(be21):
            key = extract_key_from_ack(be21)
            if key:
                dedupe = (be21.seq, key.hex())
                if dedupe not in flow.seen_acks:
                    flow.seen_acks.add(dedupe)
                    flow.key = key
                    write_key_file(self.key_file, key, flow.flow_id)
                    logger.info("[ack_0x1002] flow=%s key=%s", flow.flow_id,
                                printable_ascii(key) or key.hex())
                    self._emit("key_captured", {"flow_id": flow.flow_id, "key_hex": key.hex()})
                    if plog:
                        plog.log_key_extracted(flow.flow_id, key)
            if plog:
                plog.log_be21_frame(
                    flow.flow_id, be21.direction, be21.cmd, be21.seq,
                    be21.header_extra, be21.body,
                )
            return

        # 只处理 DATA 帧
        if be21.cmd != 0x4013:
            pkt_dict = {
                "cmd": be21.cmd, "direction": be21.direction,
                "seq": be21.seq, "body_len": be21.body_len,
                "header_extra_hex": be21.header_extra.hex(),
                "body_hex": be21.body.hex(),
            }
            record = parse_tgcp_control_packet(pkt_dict)
            if plog:
                plog.log_be21_frame(
                    flow.flow_id, be21.direction, be21.cmd, be21.seq,
                    be21.header_extra, be21.body, record=record,
                )
            if record and self.on_record:
                self.on_record(record)
                self._emit("record", {"record": record})
            return

        # 解密 DATA 帧
        if flow.key is None:
            self.stats["key_miss"] += 1
            if plog:
                plog.log_key_miss(flow.flow_id, f"0x{be21.cmd:04X}", be21.seq)
            return
        try:
            iv, plain = decrypt_4013_body(flow.key, be21.body)
        except ValueError as exc:
            self.stats["decrypt_fail"] += 1
            if plog:
                plog.log_be21_frame(
                    flow.flow_id, be21.direction, be21.cmd, be21.seq,
                    be21.header_extra, be21.body,
                    error=f"解密失败: {exc}",
                )
            return

        pkt_dict = {
            "cmd": 0x4013, "direction": be21.direction,
            "seq": be21.seq, "body_len": be21.body_len,
            "header_extra_hex": be21.header_extra.hex(),
            "body_hex": be21.body.hex(),
            "decrypted_body_hex": plain.hex(),
        }
        record = parse_record(pkt_dict)
        if record is None:
            if plog:
                plog.log_be21_frame(
                    flow.flow_id, be21.direction, be21.cmd, be21.seq,
                    be21.header_extra, be21.body,
                    decrypted_body=plain,
                    error="parse_record 返回 None",
                )
            return

        if record.get("opcode") == 0x0414:
            return

        inner = None

        kind, summary = summarize(record, inner)
        record["_summary_kind"] = kind
        record["_summary"] = summary
        self.stats["decrypt_ok"] += 1

        if plog:
            plog.log_be21_frame(
                flow.flow_id, be21.direction, be21.cmd, be21.seq,
                be21.header_extra, be21.body,
                decrypted_body=plain, record=record,
            )

        if self.on_record:
            self.on_record(record)
        self._emit("record", {"record": record})

    def start(self) -> None:
        """开始抓包。"""
        if self._running:
            return
        self._running = True
        self._sniffer = AsyncSniffer(
            filter=_DEFAULT_BPF,
            prn=self._process_packet,
            store=False,
        )
        self._sniffer.start()
        logger.info("Sniffer started on port %d", self.port)

    def stop(self) -> None:
        """停止抓包。"""
        if not self._running:
            return
        if self._sniffer:
            self._sniffer.stop()
            self._sniffer = None
        self._running = False
        logger.info("Sniffer stopped")

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def flow_count(self) -> int:
        with self._lock:
            return len(self.flows)

    def has_active_flows(self) -> bool:
        """是否有活跃的 TCP 流。"""
        with self._lock:
            return len(self.flows) > 0

    def get_status(self) -> Dict[str, Any]:
        """获取当前状态快照。"""
        with self._lock:
            flows_info = []
            for _fk, flow in self.flows.items():
                flows_info.append({
                    "flow_id": flow.flow_id,
                    "has_key": flow.key is not None,
                })
            return {
                "running": self._running,
                "flow_count": len(self.flows),
                "flows": flows_info,
                "stats": dict(self.stats),
            }
