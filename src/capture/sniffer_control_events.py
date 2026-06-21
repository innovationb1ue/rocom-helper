"""BE21 非 DATA 控制帧处理逻辑。"""
from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from src.protocol.proto_core import parse_tgcp_control_packet

_DATA_CMD = 0x4013


def handle_control_frame(
    *,
    flow: Any,
    be21: Any,
    emit: Callable[[str, Dict[str, Any]], None],
    record_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    packet_logger: Optional[Any] = None,
) -> bool:
    """处理非 DATA BE21 控制帧；若该帧被消费则返回 True。"""
    if be21.cmd == _DATA_CMD:
        return False

    pkt_dict = {
        "cmd": be21.cmd,
        "direction": be21.direction,
        "seq": be21.seq,
        "body_len": be21.body_len,
        "header_extra_hex": be21.header_extra.hex(),
        "body_hex": be21.body.hex(),
    }
    record = parse_tgcp_control_packet(pkt_dict)

    if packet_logger:
        packet_logger.log_be21_frame(
            flow.flow_id,
            be21.direction,
            be21.cmd,
            be21.seq,
            be21.header_extra,
            be21.body,
            record=record,
        )

    if record and record_callback:
        record_callback(record)
        emit("record", {"record": record})

    return True
