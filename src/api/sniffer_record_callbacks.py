"""Sniffer record callback 注册与线程安全分发。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


class SnifferRecordCallbacks:
    """维护抓包 record 回调，并通过 runtime loop 分发。"""

    def __init__(self) -> None:
        self._callbacks: List[Any] = []

    @property
    def callbacks(self) -> List[Any]:
        return self._callbacks

    def register(self, callback: Any) -> None:
        self._callbacks.append(callback)

    def dispatch(self, record: Optional[Dict[str, Any]], *, runtime: Any) -> None:
        for callback in self._callbacks:
            runtime.call_soon_threadsafe(callback, record)
