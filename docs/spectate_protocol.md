# 观战模式协议分析

## 概述

观战（spectate）模式下，玩家作为旁观者观看两名玩家的 PvP 对战。协议结构与普通 PvP 有显著差异，主要体现在数据可见性、HP 追踪机制和身份标识方面。

## 测试数据

- **观战记录**: `tests/fixtures/packets/spectate_session_1/` (32 回合, 353 包)
- **来源会话**: `logs/packets/2026-05-17_23-44-14_monitor/`
- **对局双方**: 玩家A (UIN=1701281) vs 玩家B (UIN=403074280)
- **结果**: RUNAWAY (一方逃跑), 持续 655 秒

---

## 关键差异对比

### 1. battle_enter (0x1316) — 双方阵容全亮

| 属性 | 普通 PvP | 观战 |
|------|----------|------|
| wrappers 数量 | **7** (己方6 + 对手首发1) | **12** (双方各6) |
| 己方宠物 battle_stats | 完整 `[HP, 物攻, 物防, 特攻, 特防, 速度]` | 完整 |
| 对手宠物 battle_stats | 仅 `[HP, 0, 0, 0, 0, 速度]` | 仅 `[HP, 0, 0, 0, 0, 速度]` |
| 己方 equipped_skills | 4 个技能（完整） | 4 个技能（完整） |
| 对手 equipped_skills | 0 (空) | 0 (空) |
| 对手宠物可见性 | 仅首发 1 只 | **全部 6 只** |
| side 字段 | 己方=1, 对手=401 | 己方=1, 对手=401/None |
| data_seq_num | 0 | 5 |

**核心差异**: 观战模式下，双方所有精灵在 battle_enter 时即可见（12 个 wrapper），但对手的完整属性（物攻/物防/特攻/特防）和装备技能仍然不可见，与普通 PvP 一致。

### 2. 伤害包 (0x130B/0x130C) — 完全缺失

| Opcode | 普通 PvP (s2c) | 普通 PvP (c2s) | 观战 (s2c) | 观战 (c2s) |
|--------|---------------|---------------|-----------|-----------|
| 0x130B | 17 | 17 | **0** | **0** |
| 0x130C | 17 | 0 | **0** | 0 |

**影响**:
- **HP 无法通过伤害包追踪** — 当前 BattleStateTracker 依赖 0x130B/0x130C 来更新 HP，观战中全部为 None
- 伤害信息只存在于 action_resolve (0x1324) 的 skill_cast 条目中，但观战的 skill_cast 不包含 `damage`、`hp_before`、`hp_after` 字段
- **替代 HP 数据来源**: change_pet 事件中的 `new_pet_current_hp` 和 heal 事件中的 `target_hp_after`

### 3. 身份标识 — 使用玩家 UIN

普通 PvP 使用固定 side 标识 (1=己方, 401=敌方)，观战模式使用玩家 UIN：

| 场景 | 普通 PvP | 观战 |
|------|----------|------|
| skill_cast actor_side | 1 或 401 | 玩家 UIN (如 1701281, 403074280) |
| skill_declare actor_side | 1 或 401 | 玩家 UIN |
| change_pet actor_side | 1 或 401 | 玩家 UIN |
| effect actor_side | 1 或 401 | 5 或 401 |
| energy actor_side | 1 或 401 | 0 (系统) |
| battle_enter wrapper side | 1 或 401 | 1, 401, 或 None |

**注意**: actor_side 在不同事件类型中使用不同的值系统：
- skill_cast/change_pet/skill_declare: 使用玩家 UIN
- effect_stage/effect_apply/effect_trigger: 使用 5 (玩家A) 和 401 (玩家B)
- energy: 使用 0 (系统操作)
- battle_enter wrapper: 使用 1 (玩家A) 和 401/None (玩家B)

### 4. 客户端发送包 — 仅 round_confirm

| c2s Opcode | 普通 PvP | 观战 |
|------------|----------|------|
| 0x1313 (round_confirm) | 34 | 73 |
| 0x130B (damage_confirm) | 17 | **0** |

观战者只发送 round_confirm，不发送 damage_confirm。round_confirm 数量更多是因为观战有更多回合（32 vs 17）。

### 5. skill_declare (0x1322) — 仅显示技能槽位

观战中的 skill_declare 包含以下字段：
- `actor_side`: 玩家 UIN
- `battle_token`: 玩家 UIN
- `skill_id`: **技能槽位索引** (3, 4, 5)，不是实际技能 ID
- `target_side`: 玩家侧编号 (5, 6)

大部分 skill_declare (89/93) 没有详细信息（detail=None）。

### 6. battle_finish (0x132C) — 无 PVP 积分

| 属性 | 普通 PvP | 观战 |
|------|----------|------|
| result_code | 66 (WIN_HP) | 12 (RUNAWAY) |
| pvp_score | 72000 | **不存在** |
| rounds | 17 | 32 |
| seconds | 303 | 655 |

---

## 可用的 HP 数据替代方案

虽然观战模式缺少独立的伤害包，但以下事件提供部分 HP 信息：

### change_pet 事件 (type=13)
```json
{
  "kind": "change_pet",
  "new_pet_name": "圆号鱼",
  "new_pet_current_hp": 370,
  "new_pet_max_hp": 522,
  "new_pet_energy": 10,
  "actor_side": 1701281
}
```
- 精灵切换上场时，`new_pet_current_hp` 反映切换时刻的实际 HP
- 可用于推断切换期间受到的伤害
- **注意**: `new_pet_max_hp` 可能因 buff 而变化（如 圆号鱼 522→467→522）

### heal 事件 (type=5)
```json
{
  "kind": "heal",
  "target_hp_after": 434,
  "actor_side": 5,
  "heal_type": 1
}
```
- 治疗事件提供治疗后的 HP 值

### data_update 事件 (type=35)
```json
{
  "kind": "data_update",
  "uin": 403074280
}
```
- 包含玩家 UIN，但当前解析器未提取其中的详细数据
- 原始 protobuf 中可能包含更多 HP/状态信息，需要进一步分析

---

## 观战模式完整 Opcode 分布

| Opcode | 名称 | 观战数量 | 普通数量 | 差异说明 |
|--------|------|---------|---------|---------|
| 0x1316 | battle_enter | 1 | 1 | 观战 12 wrappers vs 普通 7 |
| 0x131A | round_start | 37 | 17 | 更多回合 |
| 0x1313 | round_confirm (c2s) | 73 | 34 | 每阶段确认 |
| 0x1314 | round_confirm_rsp | 73 | 34 | 服务器响应 |
| 0x1322 | skill_declare | 93 | 17 | 观战更多声明 |
| 0x1324 | action_resolve | 72 | 33 | 核心行动事件 |
| 0x132C | battle_finish | 1 | 1 | 观战无 pvp_score |
| 0x13FC | special_refresh | 3 | 4 | |
| 0x130B | damage | **0** | 17 | **观战完全缺失** |
| 0x130C | damage_result | **0** | 17 | **观战完全缺失** |
| 0x13F3 | 未知 | **0** | 1 | **观战缺失** |

---

## 对工具的影响

### 当前工具对观战的局限性

1. **HP 追踪完全失效**: BattleStateTracker 依赖 0x130B/0x130C 更新 HP，观战中无法工作
2. **伤害预测无意义**: 无法验证预测准确性（没有实际伤害数据）
3. **阵容分析价值降低**: 虽然双方阵容可见，但没有技能信息的一方无法做 counter-pick
4. **side 映射错误**: 观战使用 UIN 作为 side 标识，当前 side 判定逻辑不兼容

### 可改进方向

1. **利用 change_pet 事件追踪 HP**: 切宠时的 HP 值可以作为离散 HP 采样点
2. **利用 heal 事件补充 HP**: 治疗后的 HP 值可更新状态
3. **解析 data_update 事件**: 原始 protobuf 可能包含完整的 HP/状态数据
4. **基于双方已知阵容做策略分析**: 观战模式下双方精灵全部可见，可以做更全面的阵容对比分析
5. **数据收集价值**: 高段位观战可以收集到高端玩家的技能搭配、使用模式、换宠策略等数据
