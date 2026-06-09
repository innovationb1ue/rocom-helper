"""TCP flow 生命周期和状态快照管理。"""
from __future__ import annotations

import logging
import threading
from typing import Any, Dict, Optional

from src.capture.crypto import write_key_file
from src.capture.packet_flow import FlowKey
from src.capture.reassembly import FlowState

logger = logging.getLogger(__name__)


class FlowRegistry:
    """线程安全的 FlowState 注册表。"""

    def __init__(self, *, key_file: str, preset_key: Optional[bytes] = None) -> None:
        self.key_file = key_file
        self.preset_key = preset_key
        self.flows: Dict[FlowKey, FlowState] = {}
        self._lock = threading.Lock()

    def get_or_create(self, fk: FlowKey) -> FlowState:
        """获取或创建标准 flow。"""
        with self._lock:
            flow = self.flows.get(fk)
            if flow is not None:
                return flow

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

    def get(self, fk: FlowKey) -> Optional[FlowState]:
        """获取已有 flow。"""
        with self._lock:
            return self.flows.get(fk)

    def count(self) -> int:
        """当前 flow 数量。"""
        with self._lock:
            return len(self.flows)

    def has_active(self) -> bool:
        """是否有活跃 flow。"""
        return self.count() > 0

    def status(self, *, running: bool, stats: Dict[str, int]) -> Dict[str, Any]:
        """构建 Sniffer status payload。"""
        with self._lock:
            flows_info = [
                {
                    "flow_id": flow.flow_id,
                    "has_key": flow.key is not None,
                }
                for flow in self.flows.values()
            ]
            return {
                "running": running,
                "flow_count": len(self.flows),
                "flows": flows_info,
                "stats": dict(stats),
            }
