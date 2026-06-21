"""TCP 包到捕获流的轻量路由规则。

该模块刻意不导入 Scapy，调用方通过 ``ip_layer``/``tcp_layer`` 注入
实际 layer 类型，便于用普通 fake packet 做单元测试。
"""
from __future__ import annotations

from typing import Any, Optional, Tuple

FlowKey = Tuple[str, int, str, int]

_TCP_FIN = 0x01
_TCP_RST = 0x04


def flow_key_from_packet(packet: Any, port: int, ip_layer: Any, tcp_layer: Any) -> Optional[FlowKey]:
    """从 TCP 包提取标准流标识 (client_ip, client_port, server_ip, server_port)。"""
    if not packet.haslayer(ip_layer) or not packet.haslayer(tcp_layer):
        return None

    ip = packet[ip_layer]
    tcp = packet[tcp_layer]
    src_ip = ip.src
    dst_ip = ip.dst
    src_port = int(tcp.sport)
    dst_port = int(tcp.dport)

    if dst_port == port:
        return (src_ip, src_port, dst_ip, dst_port)
    if src_port == port:
        return (dst_ip, dst_port, src_ip, src_port)
    return None


def packet_direction(tcp: Any, port: int) -> str:
    """根据服务端端口判断包方向。调用前应已确认该包属于目标流。"""
    return "c2s" if int(tcp.dport) == port else "s2c"


def tcp_close_reason(flags: Any) -> Optional[str]:
    """把 TCP flags 解析成连接关闭原因。RST 优先于 FIN。"""
    flags_int = int(flags)
    if flags_int & _TCP_RST:
        return "RST"
    if flags_int & _TCP_FIN:
        return "FIN"
    return None
