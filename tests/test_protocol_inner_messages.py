"""0x0414 内嵌消息解析测试。"""
from __future__ import annotations

from src.protocol.inner_messages import (
    parse_inner1_detail,
    parse_inner51_detail,
    parse_inner200_detail,
    parse_inner390_detail,
)


def msg(*fields):
    return {"fields": list(fields)}


def val(field: int, value: int):
    return {"field": field, "wire": 0, "value": value}


def sub(field: int, value):
    return {"field": field, "wire": 2, "sub": value}


def test_parse_inner390_pair_context_and_sides():
    fields = msg(
        val(1, 77),
        sub(2, msg(
            sub(3, msg(val(2, 1001), val(3, 31), val(10, 1))),
            sub(4, msg(val(1, 9), val(2, 2002), val(4, 42), val(10, 2))),
        )),
    )

    assert parse_inner390_detail(fields) == {
        "pair_ctx": 77,
        "friendly": {
            "pet_id": 1001,
            "side_flag": 1,
            "arg3": 31,
            "arg4": None,
            "arg5": None,
            "arg6": None,
        },
        "enemy": {
            "pet_id": 2002,
            "side_flag": 2,
            "arg3": None,
            "arg4": 42,
            "arg5": None,
            "arg6": None,
            "arg1": 9,
        },
    }


def test_parse_inner200_commit_detail():
    fields = msg(
        val(1, 88),
        sub(2, msg(val(1, 1), val(2, 123), val(3, 456), val(4, 7))),
    )

    assert parse_inner200_detail(fields) == {
        "pair_ctx": 88,
        "commit": {
            "flag": 1,
            "arg2_ms_like": 123,
            "event_time_ms": 456,
            "code": 7,
        },
    }


def test_parse_inner51_event_detail():
    fields = msg(val(1, 99), sub(2, msg(val(1, 3), val(2, 4), val(3, 5))))

    assert parse_inner51_detail(fields) == {
        "token": 99,
        "kind": 3,
        "value2": 4,
        "value3": 5,
    }


def test_parse_inner1_effect_detail():
    fields = msg(sub(11, msg(
        sub(1, msg(val(1, 10), val(2, 20), val(3, 30), val(5, 50), val(6, 60))),
        sub(3, msg(val(1, 7001), val(4, 2), val(11, 99), val(32, 320))),
    )))

    assert parse_inner1_detail(fields) == {
        "header": {
            "kind": 10,
            "actor_token": 20,
            "actor_aux": 30,
            "actor_ref": 50,
            "target_ctx": 60,
            "arg10": None,
            "arg11": None,
        },
        "effect": {
            "effect_id": 7001,
            "code": 2,
            "arg10": None,
            "amount": 99,
            "arg12": None,
            "arg13": None,
            "arg15": None,
            "arg16": None,
            "arg27": None,
            "arg32": 320,
        },
    }
