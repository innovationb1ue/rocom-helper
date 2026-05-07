"""AES-128-CBC 解密测试。"""
from __future__ import annotations

import os
import pytest
from src.capture.crypto import (
    decrypt_4013_body,
    parse_key_text,
    printable_ascii,
    load_key_from_file,
    write_key_file,
)


class TestDecrypt4013Body:
    """AES-128-CBC 解密测试。"""

    def _make_encrypted_body(self, key: bytes, plaintext: bytes) -> bytes:
        """用 AES-128-CBC 加密明文，生成 4013 body 格式 (iv + ciphertext)。"""
        from Crypto.Cipher import AES
        from Crypto.Util.Padding import pad
        iv = os.urandom(16)
        cipher = AES.new(key, AES.MODE_CBC, iv)
        padded = pad(plaintext, AES.block_size)
        ciphertext = cipher.encrypt(padded)
        return iv + ciphertext

    def test_roundtrip(self):
        """加密后解密应得到原始明文（去除 padding 后）。"""
        key = os.urandom(16)
        plaintext = b"Hello Roco Kingdom Battle Protocol!"
        body = self._make_encrypted_body(key, plaintext)
        iv, decrypted = decrypt_4013_body(key, body)
        assert iv == body[:16]
        assert decrypted[:len(plaintext)] == plaintext

    def test_known_key_and_data(self):
        """使用已知密钥和数据进行确定性测试。"""
        key = bytes(range(16))  # 0x00..0x0F
        plaintext = b"\x08\x01\x12\x05hello"
        body = self._make_encrypted_body(key, plaintext)
        iv, decrypted = decrypt_4013_body(key, body)
        assert decrypted[:len(plaintext)] == plaintext

    def test_body_too_short_raises(self):
        """body 不足 32 字节（iv 16 + 至少 1 block 16）应抛出 ValueError。"""
        key = os.urandom(16)
        short_body = os.urandom(31)
        with pytest.raises(ValueError):
            decrypt_4013_body(key, short_body)

    def test_body_not_aligned_raises(self):
        """密文不是 16 字节对齐应抛出 ValueError。"""
        key = os.urandom(16)
        # iv(16) + 17 bytes of "ciphertext" = not aligned
        bad_body = os.urandom(33)
        with pytest.raises(ValueError):
            decrypt_4013_body(key, bad_body)

    def test_empty_plaintext_roundtrip(self):
        """空明文也能加密解密。"""
        key = os.urandom(16)
        plaintext = b""
        body = self._make_encrypted_body(key, plaintext)
        iv, decrypted = decrypt_4013_body(key, body)
        # padding only
        assert len(decrypted) == 16  # one block of padding


class TestParseKeyText:
    """密钥文本解析测试。"""

    def test_16_byte_ascii(self):
        text = "ABCDEFGHabcdefgh"
        key = parse_key_text(text)
        assert key == text.encode("ascii")
        assert len(key) == 16

    def test_32_hex(self):
        hex_str = "0102030405060708090a0b0c0d0e0f10"
        key = parse_key_text(hex_str)
        assert key == bytes.fromhex(hex_str)
        assert len(key) == 16

    def test_invalid_length_raises(self):
        with pytest.raises(ValueError):
            parse_key_text("short")

    def test_invalid_hex_raises(self):
        with pytest.raises(ValueError):
            parse_key_text("ZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZ")


class TestPrintableAscii:
    """ASCII 可打印检测测试。"""

    def test_all_printable(self):
        assert printable_ascii(b"Hello World!") == "Hello World!"

    def test_non_printable_returns_none(self):
        assert printable_ascii(b"\x00\x01\x02") is None

    def test_empty_returns_none(self):
        assert printable_ascii(b"") is None

    def test_mixed_returns_none(self):
        assert printable_ascii(b"Hello\x00World") is None


class TestKeyFileIO:
    """密钥文件读写测试。"""

    def test_write_and_load(self, tmp_path):
        key = os.urandom(16)
        key_file = tmp_path / "test_key.txt"
        write_key_file(key_file, key, "test-flow")
        loaded = load_key_from_file(key_file)
        assert loaded == key

    def test_load_nonexistent_returns_none(self, tmp_path):
        loaded = load_key_from_file(tmp_path / "nonexistent.txt")
        assert loaded is None
