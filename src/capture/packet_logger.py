"""双轨日志系统：原始包文件 + 处理日志。

目录结构:
  logs/
    packets/                          # 原始 BE21 帧二进制文件
      2026-05-05_14-30-22/           # 按会话时间戳分目录
        s2c_1316_0001.bin            # 方向_cmd_序号.bin
        ...
    sniffer.log                      # 处理日志（文本，含解析详情和错误）
"""
from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
import os
import struct
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_LOG_DIR = _PROJECT_ROOT / "logs"
_DEFAULT_PACKET_DIR = _DEFAULT_LOG_DIR / "packets"

# 处理日志专用 logger（独立于 scapy 等第三方 logger）
_pkt_logger = logging.getLogger("raco.sniffer")


def setup_sniffer_logging(
    log_dir: Optional[str] = None,
    level: int = logging.DEBUG,
) -> logging.Logger:
    """初始化处理日志，输出到 logs/sniffer.log 和控制台。"""
    log_path = Path(log_dir) if log_dir else _DEFAULT_LOG_DIR
    log_path.mkdir(parents=True, exist_ok=True)

    _pkt_logger.setLevel(level)

    # 避免重复添加 handler
    if _pkt_logger.handlers:
        return _pkt_logger

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 文件 handler
    fh = RotatingFileHandler(
        log_path / "sniffer.log",
        maxBytes=3 * 1024 * 1024,  # 3 MB
        backupCount=4,              # sniffer.log + 4 rolled = 5 total
        encoding="utf-8",
    )
    fh.setLevel(level)
    fh.setFormatter(fmt)
    _pkt_logger.addHandler(fh)

    # 控制台 handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    _pkt_logger.addHandler(ch)

    return _pkt_logger


class PacketLogger:
    """将原始 BE21 帧写入二进制文件，同时记录处理日志。"""

    def __init__(self, session_id: Optional[str] = None, enabled: bool = True) -> None:
        self.enabled = enabled
        self._lock = threading.Lock()

        if not enabled:
            self._session_dir: Optional[Path] = None
            return

        ts = session_id or datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self._session_dir = _DEFAULT_PACKET_DIR / ts
        self._session_dir.mkdir(parents=True, exist_ok=True)

        # 写一个元信息文件
        meta = {"session_start": datetime.now().isoformat(), "session_id": ts}
        (self._session_dir / "_session.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        _pkt_logger.info("PacketLogger 初始化, 会话目录: %s", self._session_dir)

    def log_be21_frame(
        self,
        flow_id: str,
        direction: str,
        cmd: int,
        seq: int,
        header_extra: bytes,
        body: bytes,
        *,
        decrypted_body: Optional[bytes] = None,
        record: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> None:
        """记录一个 BE21 帧：原始二进制 + 处理日志。"""
        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]

        # --- 处理日志 ---
        cmd_hex = f"0x{cmd:04X}"
        if error:
            _pkt_logger.error(
                "[%s] %s %s cmd=%s seq=%d body=%dB 错误: %s",
                ts, flow_id, direction, cmd_hex, seq, len(body), error,
            )
        elif record:
            rtype = record.get("record_type", "?")
            if rtype == "business":
                opcode_hex = record.get("opcode_hex", "?")
                transport = record.get("transport_layout", "?")
                _pkt_logger.info(
                    "[%s] %s %s cmd=%s seq=%d body=%dB → %s opcode=%s layout=%s",
                    ts, flow_id, direction, cmd_hex, seq, len(body),
                    rtype, opcode_hex, transport,
                )
            else:
                tgcp_name = record.get("tgcp_command_name", "?")
                _pkt_logger.info(
                    "[%s] %s %s cmd=%s seq=%d body=%dB → %s(%s)",
                    ts, flow_id, direction, cmd_hex, seq, len(body),
                    rtype, tgcp_name,
                )
        elif decrypted_body is not None:
            _pkt_logger.debug(
                "[%s] %s %s cmd=%s seq=%d body=%dB 解密=%dB (未产出record)",
                ts, flow_id, direction, cmd_hex, seq, len(body), len(decrypted_body),
            )
        else:
            _pkt_logger.debug(
                "[%s] %s %s cmd=%s seq=%d body=%dB",
                ts, flow_id, direction, cmd_hex, seq, len(body),
            )

        if not self.enabled or self._session_dir is None:
            return

        # --- 原始包文件 ---
        # 文件名: 方向_cmd序号_时间戳.bin
        filename = f"{direction}_{cmd_hex}_{seq:04d}_{ts.replace(':', '')}.bin"
        filepath = self._session_dir / filename

        # 二进制格式:
        # [4B total_len] [2B magic] [2B cmd] [4B seq] [4B hdr_extra_len] [hdr_extra] [4B body_len] [body]
        # 如果有解密数据: [4B decrypted_len] [decrypted_body]
        with self._lock:
            try:
                with open(filepath, "wb") as f:
                    # 固定头部
                    f.write(MAGIC_V1)
                    f.write(struct.pack(">H", cmd))
                    f.write(struct.pack(">I", seq))
                    f.write(direction.encode("ascii").ljust(4, b"\x00")[:4])
                    # header_extra
                    f.write(struct.pack(">I", len(header_extra)))
                    f.write(header_extra)
                    # 原始 body
                    f.write(struct.pack(">I", len(body)))
                    f.write(body)
                    # 解密后 body（如果有）
                    if decrypted_body is not None:
                        f.write(struct.pack(">I", len(decrypted_body)))
                        f.write(decrypted_body)
                    else:
                        f.write(struct.pack(">I", 0))
                    # JSON 元信息
                    meta = {
                        "flow_id": flow_id,
                        "direction": direction,
                        "cmd": cmd_hex,
                        "seq": seq,
                        "ts": ts,
                        "body_len": len(body),
                        "decrypted": decrypted_body is not None,
                    }
                    if error:
                        meta["error"] = error
                    if record:
                        meta["record_type"] = record.get("record_type")
                        if record.get("opcode_hex"):
                            meta["opcode_hex"] = record["opcode_hex"]
                        if record.get("tgcp_command_name"):
                            meta["tgcp_command"] = record["tgcp_command_name"]
                    meta_bytes = json.dumps(meta, ensure_ascii=False).encode("utf-8")
                    f.write(struct.pack(">I", len(meta_bytes)))
                    f.write(meta_bytes)
            except Exception as exc:
                _pkt_logger.warning("写入包文件失败 %s: %s", filename, exc)

    def log_key_extracted(self, flow_id: str, key: bytes) -> None:
        _pkt_logger.info(
            "[%s] %s 密钥提取成功 key=%s",
            datetime.now().strftime("%H:%M:%S.%f")[:-3],
            flow_id, key.hex(),
        )

    def log_key_miss(self, flow_id: str, cmd_hex: str, seq: int) -> None:
        _pkt_logger.warning(
            "[%s] %s DATA帧(cmd=%s seq=%d) 无密钥，跳过解密",
            datetime.now().strftime("%H:%M:%S.%f")[:-3],
            flow_id, cmd_hex, seq,
        )

    @property
    def session_dir(self) -> Optional[Path]:
        return self._session_dir


# 文件格式 magic: "RC01"
MAGIC_V1 = b"RC01"
