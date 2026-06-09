"""Sniffer key 持久化测试。"""
from __future__ import annotations

from src.api.sniffer_key_store import save_persistent_key
from src.capture import crypto


def test_save_persistent_key_writes_bytes_and_flow_id(monkeypatch, tmp_path):
    calls = []

    def fake_write_key_file(path, key, flow_id):
        calls.append((path, key, flow_id))

    monkeypatch.setattr(crypto, "write_key_file", fake_write_key_file)

    key_file = tmp_path / "nested" / "session_key.txt"
    save_persistent_key(key_file, "31323334353637383930616263646566", "flow-1")

    assert key_file.parent.exists()
    assert calls == [
        (str(key_file), b"1234567890abcdef", "flow-1"),
    ]


def test_save_persistent_key_clears_missing_key(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(crypto, "write_key_file", lambda *args: calls.append(args))
    key_file = tmp_path / "session_key.txt"
    key_file.write_bytes(b"stale")

    save_persistent_key(key_file, None, "flow-1")

    assert calls == []
    assert not key_file.exists()
