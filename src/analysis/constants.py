"""战斗分析模块共享常量 — opcode 定义、类型映射、标签。

集中管理分析层和 API 层使用的 opcode 常量，消除魔数和反向依赖。
"""
from __future__ import annotations

from typing import Dict

# ---------------------------------------------------------------------------
# Battle opcodes — 单一真相源
# ---------------------------------------------------------------------------

OPCODE_BATTLE_ENTER = 0x1316      # 进入战斗
OPCODE_ROUND_START = 0x131A       # 回合开始
OPCODE_ACTION_RESOLVE = 0x1324    # 行动结算（伤害/效果/换宠/击杀）
OPCODE_BATTLE_FINISH = 0x132C     # 战斗结束
OPCODE_SKILL_SELECT = 0x130B      # 客户端技能选择
OPCODE_SKILL_DECLARE = 0x1322     # 服务端技能声明
OPCODE_SPECIAL_REFRESH = 0x13F4   # 特殊刷新（能量瓶等）
OPCODE_ROUND_FLOW = 0x1312        # 回合流
OPCODE_ACTION_ACK = 0x130C        # 服务端行动确认
OPCODE_ROSTER_INIT = 0x0102       # 阵容初始化
OPCODE_PVP_PERFORM = 0x13FC       # PvP 演出
OPCODE_PREPLAY = 0x13F3           # 预演出
OPCODE_ACTION_RESULT = 0x01A9     # 行动结果
OPCODE_BATTLE_MSG = 0x0220        # 战斗消息
OPCODE_SKILL_EFFECT = 0x1326      # 技能效果
OPCODE_ROLE_LEAVE = 0x132A        # 角色离线（RoleLeaveNotify）
OPCODE_BATTLE_SETTLE = 0x132D     # 战斗结算
OPCODE_PET_DEFEAT = 0x1334        # 宠物战败
OPCODE_ROUND_SETTLE = 0x133C      # 回合结算
OPCODE_BATTLE_ACTION = 0x13F6     # 战斗行动
OPCODE_ROUND_CONFIRM = 0x1313     # 回合流完成确认
OPCODE_ROUND_CONFIRM_RSP = 0x1314 # 回合流完成确认响应

# 战斗辅助 opcode：进入审计/日志，但默认不驱动核心状态机
OPCODE_LOAD_FINISH_REQ = 0x1305
OPCODE_LOAD_FINISH_RSP = 0x1306
OPCODE_SUPPLY_PET_REQ = 0x1309
OPCODE_SUPPLY_PET_RSP = 0x130A
OPCODE_PLAYER_RUNAWAY_REQ = 0x132E
OPCODE_PLAYER_RUNAWAY_RSP = 0x132F
OPCODE_ROUND_OP_QUERY_REQ = 0x1335
OPCODE_ROUND_OP_QUERY_RSP = 0x1336
OPCODE_PK_AGAIN = 0x13F9

# ---------------------------------------------------------------------------
# Opcode 分组集合
# ---------------------------------------------------------------------------

LIFECYCLE_OPCODES = {
    OPCODE_BATTLE_ENTER, OPCODE_ROUND_START,
    OPCODE_BATTLE_FINISH, OPCODE_ROSTER_INIT,
}

IN_BATTLE_OPCODES = {
    OPCODE_SKILL_SELECT, OPCODE_SKILL_DECLARE, OPCODE_ACTION_RESOLVE,
    OPCODE_SPECIAL_REFRESH, OPCODE_ACTION_ACK,
    OPCODE_ACTION_RESULT, OPCODE_BATTLE_MSG, OPCODE_PVP_PERFORM,
    OPCODE_PREPLAY, OPCODE_ROUND_FLOW,
    OPCODE_ROUND_CONFIRM, OPCODE_ROUND_CONFIRM_RSP,
    OPCODE_SKILL_EFFECT, OPCODE_ROLE_LEAVE, OPCODE_BATTLE_SETTLE,
    OPCODE_PET_DEFEAT, OPCODE_ROUND_SETTLE, OPCODE_BATTLE_ACTION,
}

AUX_BATTLE_OPCODES = {
    OPCODE_LOAD_FINISH_REQ, OPCODE_LOAD_FINISH_RSP,
    OPCODE_SUPPLY_PET_REQ, OPCODE_SUPPLY_PET_RSP,
    OPCODE_PLAYER_RUNAWAY_REQ, OPCODE_PLAYER_RUNAWAY_RSP,
    OPCODE_ROUND_OP_QUERY_REQ, OPCODE_ROUND_OP_QUERY_RSP,
    OPCODE_PK_AGAIN,
}

DAMAGE_OPCODES = {
    OPCODE_BATTLE_ENTER, OPCODE_ROUND_START,
    OPCODE_ACTION_RESOLVE, OPCODE_SPECIAL_REFRESH,
}

# ---------------------------------------------------------------------------
# Opcode 标签（用于战斗摘要统计）
# ---------------------------------------------------------------------------

OPCODE_LABELS: Dict[int, str] = {
    OPCODE_BATTLE_ENTER: "battle_enter",
    OPCODE_ROUND_START: "round_start",
    OPCODE_SKILL_SELECT: "client_skill_select",
    OPCODE_SKILL_DECLARE: "server_skill_declare",
    OPCODE_ACTION_RESOLVE: "action_resolve",
    OPCODE_ACTION_ACK: "server_action_ack",
    OPCODE_BATTLE_FINISH: "battle_finish",
    OPCODE_SPECIAL_REFRESH: "special_refresh",
    OPCODE_PVP_PERFORM: "pvp_perform",
    OPCODE_PREPLAY: "preplay",
    OPCODE_ROUND_FLOW: "round_flow",
    OPCODE_ROUND_CONFIRM: "round_confirm",
    OPCODE_ROUND_CONFIRM_RSP: "round_confirm_rsp",
    OPCODE_SUPPLY_PET_REQ: "supply_pet_req",
    OPCODE_SUPPLY_PET_RSP: "supply_pet_rsp",
    OPCODE_PLAYER_RUNAWAY_REQ: "player_runaway_req",
    OPCODE_PLAYER_RUNAWAY_RSP: "player_runaway_rsp",
    OPCODE_ROUND_OP_QUERY_REQ: "round_op_query_req",
    OPCODE_ROUND_OP_QUERY_RSP: "round_op_query_rsp",
    OPCODE_PK_AGAIN: "pk_again",
}

# ---------------------------------------------------------------------------
# 伤害类型到属性类型的映射（从 protocol 层 re-export）
# ---------------------------------------------------------------------------

from src.protocol.proto_core import SDT_TO_TYPE  # noqa: E402
