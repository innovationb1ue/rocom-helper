"""TCP 包流向/关闭规则的独立测试。"""
from __future__ import annotations

from src.capture.packet_flow import flow_key_from_packet, packet_direction, tcp_close_reason


class _IP:
    pass


class _TCP:
    pass


class _FakeIp:
    def __init__(self, src: str, dst: str) -> None:
        self.src = src
        self.dst = dst


class _FakeTcp:
    def __init__(self, sport: int, dport: int, flags: int = 0) -> None:
        self.sport = sport
        self.dport = dport
        self.flags = flags


class _FakePacket:
    def __init__(self, ip: _FakeIp | None = None, tcp: _FakeTcp | None = None) -> None:
        self._layers = {}
        if ip is not None:
            self._layers[_IP] = ip
        if tcp is not None:
            self._layers[_TCP] = tcp

    def haslayer(self, layer: object) -> bool:
        return layer in self._layers

    def __getitem__(self, layer: object) -> object:
        return self._layers[layer]


def test_flow_key_from_client_to_server_packet():
    packet = _FakePacket(
        ip=_FakeIp(src="10.0.0.2", dst="10.0.0.9"),
        tcp=_FakeTcp(sport=51000, dport=8195),
    )

    assert flow_key_from_packet(packet, 8195, _IP, _TCP) == (
        "10.0.0.2",
        51000,
        "10.0.0.9",
        8195,
    )


def test_flow_key_from_server_to_client_packet_keeps_canonical_order():
    packet = _FakePacket(
        ip=_FakeIp(src="10.0.0.9", dst="10.0.0.2"),
        tcp=_FakeTcp(sport=8195, dport=51000),
    )

    assert flow_key_from_packet(packet, 8195, _IP, _TCP) == (
        "10.0.0.2",
        51000,
        "10.0.0.9",
        8195,
    )


def test_flow_key_ignores_non_target_tcp_packet_and_missing_layers():
    assert flow_key_from_packet(_FakePacket(tcp=_FakeTcp(1, 8195)), 8195, _IP, _TCP) is None

    packet = _FakePacket(
        ip=_FakeIp(src="10.0.0.2", dst="10.0.0.9"),
        tcp=_FakeTcp(sport=51000, dport=443),
    )
    assert flow_key_from_packet(packet, 8195, _IP, _TCP) is None


def test_packet_direction_uses_server_port():
    assert packet_direction(_FakeTcp(sport=51000, dport=8195), 8195) == "c2s"
    assert packet_direction(_FakeTcp(sport=8195, dport=51000), 8195) == "s2c"


def test_tcp_close_reason_prefers_rst_over_fin():
    assert tcp_close_reason(0) is None
    assert tcp_close_reason(0x01) == "FIN"
    assert tcp_close_reason(0x04) == "RST"
    assert tcp_close_reason(0x05) == "RST"
