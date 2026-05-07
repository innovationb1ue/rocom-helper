"""密钥提取：从 0x1002 ACK 帧中提取 AES-128-CBC 会话密钥。"""
from __future__ import annotations

import logging
from typing import Optional

from src.capture.frame import Be21Packet

logger = logging.getLogger(__name__)

_ACK_CMD = 0x1002
_KEY_OFFSET = 2
_KEY_LENGTH = 16


def extract_key_from_ack(packet: Be21Packet) -> Optional[bytes]:
    """从 BE21 ACK (0x1002) 包的 header_extra 中提取 16 字节 AES 密钥。

    密钥位于 header_extra[2:18]。
    """
    if packet.cmd != _ACK_CMD:
        return None
    extra = packet.header_extra
    if len(extra) < _KEY_OFFSET + _KEY_LENGTH:
        return None
    key = extra[_KEY_OFFSET:_KEY_OFFSET + _KEY_LENGTH]
    if len(key) != _KEY_LENGTH:
        return None
    return key


def is_ack_packet(packet: Be21Packet) -> bool:
    return packet.cmd == _ACK_CMD
