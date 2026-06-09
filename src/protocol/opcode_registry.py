"""Opcode registry primitives."""
from __future__ import annotations

from typing import Any, Callable, Dict, Optional, Tuple

OpcodeHandler = Callable[[Any, Optional[Any]], Dict[str, Any]]
OpcodeRegistry = Dict[int, Tuple[str, OpcodeHandler]]

OPCODE_REGISTRY: OpcodeRegistry = {}
INNER_REGISTRY: OpcodeRegistry = {}


def make_detail_handler(extractor: Callable[[Any], Dict[str, Any]]) -> OpcodeHandler:
    """Wrap an extractor in the standard summarize detail payload shape."""

    def _handler(record: Any, inner: Optional[Any]) -> Dict[str, Any]:
        return {"detail": extractor(record)}

    return _handler


def register_opcode(opcode: int, kind: str) -> Callable[[OpcodeHandler], OpcodeHandler]:
    """Register a main opcode handler."""

    def _decorator(func: OpcodeHandler) -> OpcodeHandler:
        OPCODE_REGISTRY[opcode] = (kind, func)
        return func

    return _decorator


def register_inner(message_id: int, kind: str) -> Callable[[OpcodeHandler], OpcodeHandler]:
    """Register an opcode 0x0414 inner-message handler."""

    def _decorator(func: OpcodeHandler) -> OpcodeHandler:
        INNER_REGISTRY[message_id] = (kind, func)
        return func

    return _decorator
