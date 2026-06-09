"""顶层捕获编排器：封装 Scapy AsyncSniffer，管理 TCP 流重组和密钥提取。"""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

try:
    from scapy.all import AsyncSniffer, TCP, IP  # type: ignore
    HAS_SCAPY = True
except ImportError:
    HAS_SCAPY = False

from src.capture.frame import Be21Packet
from src.capture.flow_registry import FlowRegistry
from src.capture.packet_flow import flow_key_from_packet, packet_direction, tcp_close_reason
from src.capture.reassembly import FlowState
from src.capture.sniffer_control_events import handle_control_frame
from src.capture.sniffer_data_events import handle_data_frame
from src.capture.sniffer_key_events import handle_ack_key_frame
from src.config import settings

_DEFAULT_PORT = settings.capture_port
_DEFAULT_BPF = f"tcp port {_DEFAULT_PORT}"


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
        self._flow_registry = FlowRegistry(key_file=key_file, preset_key=preset_key)
        self.flows = self._flow_registry.flows
        self._sniffer: Optional[AsyncSniffer] = None
        self._running = False
        self.stats: Dict[str, int] = {"decrypt_ok": 0, "decrypt_fail": 0, "key_miss": 0, "parse_fail": 0}

    def _emit(self, event_type: str, data: Dict[str, Any]) -> None:
        if event_type == "key_missing_suppressed":
            self.preset_key = None
            self._flow_registry.clear_preset_key()
        if self.on_event:
            try:
                self.on_event(event_type, data)
            except Exception:
                logger.debug("on_event callback raised", exc_info=True)

    def _get_or_create_flow(self, fk: Tuple[str, int, str, int]) -> FlowState:
        return self._flow_registry.get_or_create(fk)

    def _process_packet(self, packet: Any) -> None:
        """处理一个 Scapy 捕获的包。"""
        if not packet.haslayer(TCP):
            return

        tcp = packet[TCP]
        payload = bytes(tcp.payload)

        close_reason = tcp_close_reason(tcp.flags)
        if close_reason:
            fk = flow_key_from_packet(packet, self.port, IP, TCP)
            if fk is not None:
                flow = self._flow_registry.get(fk)
                if flow is not None:
                    logger.info("TCP %s: %s", close_reason, flow.flow_id)
                    self._emit("flow_closed", {"flow_id": flow.flow_id, "reason": close_reason})
            return

        # 只有有 payload 的包才做流重组和解析
        if not payload:
            return

        fk = flow_key_from_packet(packet, self.port, IP, TCP)
        if fk is None:
            return

        flow = self._get_or_create_flow(fk)

        # 首次创建 flow 时通知
        if flow.c2s._base_seq is None and flow.s2c._base_seq is None:
            # 第一个有 payload 的包，确认 flow 是新的
            pass

        direction = packet_direction(tcp, self.port)
        seq = int(tcp.seq)
        for be21 in flow.direction_state(direction).feed(seq, payload):
            self._handle_be21(flow, be21)

    def _handle_be21(self, flow: FlowState, be21: Be21Packet) -> None:
        """处理一个 BE21 帧：密钥提取或解密解析。"""
        plog = self.pkt_logger

        if handle_ack_key_frame(
            flow=flow,
            be21=be21,
            key_file=self.key_file,
            emit=self._emit,
            packet_logger=plog,
        ):
            return

        if handle_control_frame(
            flow=flow,
            be21=be21,
            emit=self._emit,
            record_callback=self.on_record,
            packet_logger=plog,
        ):
            return

        handle_data_frame(
            flow=flow,
            be21=be21,
            stats=self.stats,
            emit=self._emit,
            record_callback=self.on_record,
            packet_logger=plog,
        )

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
        return self._flow_registry.count()

    def has_active_flows(self) -> bool:
        """是否有活跃的 TCP 流。"""
        return self._flow_registry.has_active()

    def get_status(self) -> Dict[str, Any]:
        """获取当前状态快照。"""
        return self._flow_registry.status(running=self._running, stats=self.stats)
