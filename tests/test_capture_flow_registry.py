"""FlowRegistry 生命周期测试。"""
from __future__ import annotations

from src.capture.flow_registry import FlowRegistry


def test_get_or_create_creates_canonical_flow_and_reuses_it(tmp_path):
    registry = FlowRegistry(key_file=str(tmp_path / "session_key.txt"))
    fk = ("127.0.0.1", 10000, "127.0.0.1", 8195)

    flow = registry.get_or_create(fk)
    same_flow = registry.get_or_create(fk)

    assert same_flow is flow
    assert flow.flow_id == "127.0.0.1:10000-127.0.0.1:8195"
    assert flow.client_port == 10000
    assert flow.server_port == 8195
    assert registry.count() == 1
    assert registry.has_active() is True


def test_get_or_create_applies_preset_key_and_writes_key_file(tmp_path):
    key_file = tmp_path / "session_key.txt"
    key = b"1234567890abcdef"
    registry = FlowRegistry(key_file=str(key_file), preset_key=key)

    flow = registry.get_or_create(("10.0.0.2", 51000, "10.0.0.9", 8195))

    assert flow.key == key
    assert key_file.exists()
    text = key_file.read_text(encoding="utf-8")
    assert key.hex() in text
    assert flow.flow_id in text


def test_get_and_status_snapshot(tmp_path):
    registry = FlowRegistry(key_file=str(tmp_path / "session_key.txt"))
    fk = ("10.0.0.2", 51000, "10.0.0.9", 8195)
    flow = registry.get_or_create(fk)
    flow.key = b"1234567890abcdef"

    assert registry.get(fk) is flow
    assert registry.get(("x", 1, "y", 2)) is None
    assert registry.status(
        running=True,
        stats={"decrypt_ok": 2, "parse_fail": 1},
    ) == {
        "running": True,
        "flow_count": 1,
        "flows": [
            {
                "flow_id": "10.0.0.2:51000-10.0.0.9:8195",
                "has_key": True,
            },
        ],
        "stats": {"decrypt_ok": 2, "parse_fail": 1},
    }
