"""AES-128-CBC 解密和密钥管理。"""
from __future__ import annotations
import logging
from pathlib import Path
from typing import Optional, Tuple
try:
    from Crypto.Cipher import AES
except ImportError as exc:
    raise SystemExit("缺少 pycryptodome。先执行: pip install pycryptodome") from exc

logger = logging.getLogger(__name__)

def printable_ascii(blob: bytes) -> Optional[str]:
    """检查字节是否为可打印 ASCII，返回字符串或 None"""
    return blob.decode("ascii", errors="replace") if blob and all(32 <= b < 127 for b in blob) else None

def parse_key_text(text: str) -> bytes:
    """解析密钥文本，支持 16 字节 ASCII 或 32 位 hex 格式"""
    raw = text.strip()
    hex_cand = "".join(c for c in raw if c in "0123456789abcdefABCDEF")
    if len(raw) == 16:
        try:
            key = raw.encode("ascii")
        except UnicodeEncodeError as exc:
            raise ValueError("key 必须是 16 字节 ASCII 或 32 位 hex") from exc
    elif len(hex_cand) == 32:
        key = bytes.fromhex(hex_cand)
    else:
        raise ValueError("key 必须是 16 字节 ASCII 或 32 位 hex")
    if len(key) != 16:
        raise ValueError("AES-128 key 必须正好 16 字节")
    return key

def load_key_from_file(path: str) -> Optional[bytes]:
    """从文件加载密钥"""
    from pathlib import Path as _Path
    p = _Path(path)
    if not p.is_file():
        return None
    text = p.read_text(encoding="utf-8", errors="ignore").strip()
    if not text:
        return None
    first = text.splitlines()[0].strip()
    if "=" not in first:
        try:
            return parse_key_text(first)
        except ValueError:
            return None
    for line in text.splitlines():
        if line.startswith("key_hex="):
            value = line.split("=", 1)[1].strip()
            if value:
                try:
                    return parse_key_text(value)
                except ValueError:
                    pass
        if line.startswith("key_ascii="):
            value = line.split("=", 1)[1].strip()
            if value:
                try:
                    return parse_key_text(value)
                except ValueError:
                    pass
    return None

def write_key_file(path: str, key: bytes, flow_id: str) -> None:
    """将密钥写入文件"""
    from datetime import datetime
    Path(path).write_text(
        f"key_hex={key.hex()}\nkey_ascii={printable_ascii(key) or ''}\n"
        f"flow={flow_id}\ncaptured_at={datetime.now().isoformat()}\n",
        encoding="utf-8",
    )

def decrypt_4013_body(key: bytes, body: bytes) -> Tuple[bytes, bytes]:
    """解密 0x4013 数据包
    Returns: (iv, plaintext)
    """
    if len(body) < 32:
        raise ValueError("0x4013 body 长度不足，无法拆出 IV + 密文")
    iv = body[:16]
    ct = body[16:]
    if len(ct) % 16 != 0:
        raise ValueError("0x4013 body[16:] 不是 16 字节对齐")
    return iv, AES.new(key, AES.MODE_CBC, iv).decrypt(ct)
