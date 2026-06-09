"""BE21 DATA 帧解密、解析和分发逻辑。"""
from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from src.capture.crypto import decrypt_4013_body
from src.capture.sniffer_events import handle_missing_key_frame, handle_parse_record_none
from src.protocol.opcodes import summarize
from src.protocol.proto_core import parse_record

_DATA_CMD = 0x4013


def handle_data_frame(
    *,
    flow: Any,
    be21: Any,
    stats: Dict[str, int],
    emit: Callable[[str, Dict[str, Any]], None],
    record_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    packet_logger: Optional[Any] = None,
) -> bool:
    """处理 DATA BE21 帧；若该帧被消费则返回 True。"""
    if be21.cmd != _DATA_CMD:
        return False

    if flow.key is None:
        handle_missing_key_frame(
            flow=flow,
            be21=be21,
            stats=stats,
            emit=emit,
            packet_logger=packet_logger,
        )
        return True

    try:
        _iv, plain = decrypt_4013_body(flow.key, be21.body)
    except ValueError as exc:
        stats["decrypt_fail"] += 1
        if packet_logger:
            packet_logger.log_be21_frame(
                flow.flow_id,
                be21.direction,
                be21.cmd,
                be21.seq,
                be21.header_extra,
                be21.body,
                error=f"解密失败: {exc}",
            )
        emit("decrypt_fail", {
            "flow_id": flow.flow_id,
            "cmd": be21.cmd,
            "seq": be21.seq,
            "reason": str(exc),
            "key_hex": flow.key.hex() if flow.key else None,
            "count": stats["decrypt_fail"],
        })
        return True

    pkt_dict = {
        "cmd": _DATA_CMD,
        "direction": be21.direction,
        "seq": be21.seq,
        "body_len": be21.body_len,
        "header_extra_hex": be21.header_extra.hex(),
        "body_hex": be21.body.hex(),
        "decrypted_body_hex": plain.hex(),
    }
    record = parse_record(pkt_dict)
    if record is None:
        if packet_logger:
            packet_logger.log_be21_frame(
                flow.flow_id,
                be21.direction,
                be21.cmd,
                be21.seq,
                be21.header_extra,
                be21.body,
                decrypted_body=plain,
                error="parse_record 返回 None",
            )
        handle_parse_record_none(
            flow_id=flow.flow_id,
            direction=be21.direction,
            seq=be21.seq,
            stats=stats,
            emit=emit,
        )
        return True

    if record.get("opcode") == 0x0414:
        return True

    kind, summary = summarize(record, None)
    record["_summary_kind"] = kind
    record["_summary"] = summary
    stats["decrypt_ok"] += 1

    if packet_logger:
        packet_logger.log_be21_frame(
            flow.flow_id,
            be21.direction,
            be21.cmd,
            be21.seq,
            be21.header_extra,
            be21.body,
            decrypted_body=plain,
            record=record,
        )

    if record_callback:
        record_callback(record)
    emit("record", {"record": record})
    return True
