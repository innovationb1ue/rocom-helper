"""BE21 ACK 密钥帧处理逻辑。"""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional

from src.capture.crypto import printable_ascii, write_key_file
from src.capture.key_capture import extract_key_from_ack, is_ack_packet

logger = logging.getLogger(__name__)


def handle_ack_key_frame(
    *,
    flow: Any,
    be21: Any,
    key_file: str,
    emit: Callable[[str, Dict[str, Any]], None],
    packet_logger: Optional[Any] = None,
) -> bool:
    """处理 ACK key 帧；若该帧属于 ACK key 流程则返回 True。"""
    if not is_ack_packet(be21):
        return False

    key = extract_key_from_ack(be21)
    if key:
        dedupe = (be21.seq, key.hex())
        if dedupe not in flow.seen_acks:
            flow.seen_acks.add(dedupe)
            flow.key = key
            flow.key_from_preset = False
            flow.key_miss_count = 0
            flow.key_missing_suppressed = False
            flow.key_missing_reported = False
            flow.stale_key_parse_fail_count = 0
            write_key_file(key_file, key, flow.flow_id)
            logger.info(
                "[ack_0x1002] flow=%s key=%s",
                flow.flow_id,
                printable_ascii(key) or key.hex(),
            )
            emit("key_captured", {"flow_id": flow.flow_id, "key_hex": key.hex()})
            if packet_logger:
                packet_logger.log_key_extracted(flow.flow_id, key)

    if packet_logger:
        packet_logger.log_be21_frame(
            flow.flow_id,
            be21.direction,
            be21.cmd,
            be21.seq,
            be21.header_extra,
            be21.body,
        )
    return True
