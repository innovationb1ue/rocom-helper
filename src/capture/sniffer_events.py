"""Sniffer 事件计数和上报辅助逻辑。"""
from __future__ import annotations

from typing import Any, Callable, Dict

_KEY_MISSING_SUPPRESS_THRESHOLD = 3


def handle_missing_key_frame(
    *,
    flow: Any,
    be21: Any,
    stats: Dict[str, int],
    emit: Callable[[str, Dict[str, Any]], None],
    packet_logger: Any = None,
    suppress_threshold: int = _KEY_MISSING_SUPPRESS_THRESHOLD,
) -> None:
    """处理无密钥 DATA 帧的计数、限量日志和 suppression 事件。"""
    flow.key_miss_count += 1
    stats["key_miss"] += 1
    if packet_logger and not flow.key_missing_suppressed:
        packet_logger.log_key_miss(flow.flow_id, f"0x{be21.cmd:04X}", be21.seq)
    if flow.key_miss_count < suppress_threshold:
        return

    flow.key_missing_suppressed = True
    if flow.key_missing_reported:
        return

    flow.key_missing_reported = True
    emit("key_missing_suppressed", {
        "flow_id": flow.flow_id,
        "cmd": be21.cmd,
        "seq": be21.seq,
        "key_miss_count": flow.key_miss_count,
        "reason": "已捕获到加密 DATA 帧但未捕获会话密钥，后续该连接将降级静默",
    })


def handle_parse_record_none(
    *,
    flow_id: str,
    direction: str,
    seq: int,
    stats: Dict[str, int],
    emit: Callable[[str, Dict[str, Any]], None],
) -> bool:
    """处理 parse_record 返回 None 的方向性统计。

    s2c 解析失败代表协议问题，需要计数和上报；c2s 中的握手/心跳等未知形状是正常情况。
    返回值表示是否上报了 parse_fail。
    """
    if direction != "s2c":
        return False

    stats["parse_fail"] += 1
    emit("parse_fail", {
        "flow_id": flow_id,
        "seq": seq,
        "count": stats["parse_fail"],
    })
    return True
