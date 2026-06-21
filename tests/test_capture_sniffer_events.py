"""抓包 Sniffer 事件辅助逻辑测试。"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from src.capture.sniffer_events import handle_missing_key_frame, handle_parse_record_none


def test_missing_key_frame_counts_logs_until_suppression_and_emits_once():
    flow = SimpleNamespace(
        flow_id="127.0.0.1:10000-127.0.0.1:8195",
        key_miss_count=0,
        key_missing_suppressed=False,
        key_missing_reported=False,
    )
    be21 = SimpleNamespace(cmd=0x4013, seq=1)
    stats = {"key_miss": 0}
    events = []
    packet_logger = MagicMock()

    for seq in range(1, 6):
        be21.seq = seq
        handle_missing_key_frame(
            flow=flow,
            be21=be21,
            stats=stats,
            emit=lambda event_type, data: events.append((event_type, data)),
            packet_logger=packet_logger,
        )

    assert stats["key_miss"] == 5
    assert flow.key_miss_count == 5
    assert flow.key_missing_suppressed is True
    assert flow.key_missing_reported is True
    assert packet_logger.log_key_miss.call_count == 3
    assert events == [
        (
            "key_missing_suppressed",
            {
                "flow_id": flow.flow_id,
                "cmd": 0x4013,
                "seq": 3,
                "key_miss_count": 3,
                "reason": "已捕获到加密 DATA 帧但未捕获会话密钥，后续该连接将降级静默",
            },
        ),
    ]


def test_parse_record_none_reports_only_s2c():
    stats = {"parse_fail": 0}
    events = []

    c2s_reported = handle_parse_record_none(
        flow_id="flow-1",
        direction="c2s",
        seq=1,
        stats=stats,
        emit=lambda event_type, data: events.append((event_type, data)),
    )
    s2c_reported = handle_parse_record_none(
        flow_id="flow-1",
        direction="s2c",
        seq=2,
        stats=stats,
        emit=lambda event_type, data: events.append((event_type, data)),
    )

    assert c2s_reported is False
    assert s2c_reported is True
    assert stats["parse_fail"] == 1
    assert events == [
        ("parse_fail", {"flow_id": "flow-1", "seq": 2, "count": 1}),
    ]
