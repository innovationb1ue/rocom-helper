"""Sniffer 会话密钥持久化。"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def save_persistent_key(path: Path, key_hex: Optional[str], flow_id: str) -> None:
    """把捕获到的 AES key 写入持久化文件。"""
    if not key_hex:
        try:
            path.unlink(missing_ok=True)
        except Exception as exc:
            logger.warning("清理密钥失败: %s", exc)
        return
    try:
        key = bytes.fromhex(key_hex)
        path.parent.mkdir(parents=True, exist_ok=True)
        from src.capture.crypto import write_key_file

        write_key_file(str(path), key, flow_id)
        logger.info("密钥已保存到 %s", path)
    except Exception as exc:
        logger.warning("保存密钥失败: %s", exc)
