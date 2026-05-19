# 观战模式协议分析

## 概述

观战（spectate）模式下，玩家作为旁观者观看两名玩家的 PvP 对战。协议结构与普通 PvP 存在一些差异，但核心数据（HP、技能、BUFF 等）均可完整追踪。

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

### 2. 伤害数据 — 嵌入 action_resolve，无独立包

| Opcode | 普通 PvP (s2c) | 普通 PvP (c2s) | 观战 (s2c) | 观战 (c2s) |
|--------|---------------|---------------|-----------|-----------|
| 0x130B | 17 | 17 | **0** | **0** |
| 0x130C | 17 | 0 | **0** | 0 |

观战模式**不发送独立的 0x130B/0x130C 伤害包**，但伤害数据**完整嵌入在 action_resolve (0x1324) 的 damage 条目（type=4）中**：

```json
{
  "kind": "damage",
  "skill_name": "暴风雪",
  "damage": 112,
  "target_hp_after": 254,
  "damage_target_side": 3,
  "is_critical": false,
  "restraint_type": 0
}
```

每个 damage 条目包含：
- `damage`: 伤害数值
- `target_hp_after`: 受伤后 HP（完整 HP 追踪）
- `skill_id` / `skill_name`: 造成伤害的技能
- `restraint_type`: 克制关系 (-1/0/1)
- `is_critical`: 是否暴击

**HP 追踪正常工作** — BattleStateTracker 的 `_handle_damage_entry` 通过 `target_hp_after` 更新双方 HP。实测数据：

```
R 1: My=化蝶    HP= 311/311  Opp=迷途羔羊   HP= 445/445
R 3: My=寒音蛇   HP= 254/401  Opp=尖嘴狐仙   HP= 480/480  (受伤 147)
R 6: My=圆号鱼   HP= 522/522  Opp=尖嘴狐仙   HP= 399/480  (受伤 81)
R11: My=圆号鱼   HP= 222/522  Opp=尖嘴狐仙   HP= 480/480  (受伤 300)
R28: My=圆号鱼   HP=   0/467  Opp=迷途羔羊   HP= 445/445  (阵亡)
R30: My=寒音蛇   HP= 254/366  Opp=寂灭骨龙   HP=   0/425  (击杀)
```

### 3. Side 标识 — 动态编号，非固定值

普通 PvP 使用固定 side 标识 (1=己方, 401=敌方)，观战模式使用**动态 pet 级别编号**：

| 事件类型 | 普通 PvP side 值 | 观战 side 值 |
|----------|-----------------|-------------|
| battle_enter wrapper | 1, 401 | 1, 401, None |
| action_resolve entries | 1, 401 | **每个宠物独立编号** |
| change_pet actor_side | 1, 401 | 玩家 UIN (1701281, 403074280) |
| skill_declare actor_side | 1, 401 | 玩家 UIN |

**action_resolve 中的 side 编号规则**：

- **我方 (side < 100)**: 3, 4, 5, 6 — 每个精灵有独立编号
- **敌方 (side >= 401)**: 401, 402, 403, 404, 405, 406 — 每个精灵有独立编号
- **系统**: 0 (energy 事件)

`_is_mine()` 的 fallback `1 <= v <= 6` 规则**正确区分**了我方 (3-6) 和敌方 (401-406)。

完整 side 值分布：

| Side 值 | 标签 | 事件数 | 说明 |
|---------|------|--------|------|
| 3 | 我方 | 209 | 玩家A精灵1 |
| 4 | 我方 | 43 | 玩家A精灵2 |
| 5 | 我方 | 128 | 玩家A精灵3 |
| 6 | 我方 | 758 | 玩家A精灵4（最常见） |
| 401 | 敌方 | 444 | 玩家B精灵1 |
| 402 | 敌方 | 51 | 玩家B精灵2 |
| 403 | 敌方 | 88 | 玩家B精灵3 |
| 404 | 敌方 | 142 | 玩家B精灵4 |
| 405 | 敌方 | 38 | 玩家B精灵5 |
| 406 | 敌方 | 145 | 玩家B精灵6 |

### 4. 客户端发送包 — 仅 round_confirm

| c2s Opcode | 普通 PvP | 观战 |
|------------|----------|------|
| 0x1313 (round_confirm) | 34 | 73 |
| 0x130B (damage_confirm) | 17 | **0** |

观战者只发送 round_confirm，不发送 damage_confirm。round_confirm 数量更多是因为观战有更多回合（32 vs 17）。

### 5. battle_finish (0x132C) — 无 PVP 积分

| 属性 | 普通 PvP | 观战 |
|------|----------|------|
| result_code | 66 (WIN_HP) | 12 (RUNAWAY) |
| pvp_score | 72000 | **不存在** |
| rounds | 17 | 32 |
| seconds | 303 | 655 |

---

## 已正确解析的数据

### 技能 — 己方完整可见

观战模式下"己方"（side=1）精灵的 4 个装备技能完整可提取，与普通 PvP 一致：

```
化蝶: 退化, 食腐, 超级糖果, 毒孢子
公平鸽: 吞噬, 影袭, 天旋地转, 啮合传递
贝古斯: 火焰护盾, 霜降, 倾泻, 燃尽
幽影树: 勾魂, 幽灵爆发, 移花接木, 酶浓度调整
圆号鱼: 甜心续航, 泡沫幻影, 水炮, 洗礼
寒音蛇: 月光合奏, 连续毒针, 示弱, 有效预防
```

### HP — 双方完整追踪

通过 action_resolve 的 damage/heal/defeat 条目，双方 HP 完整可追踪：

- **damage 条目 (type=4)**: 25 次，每次包含 `target_hp_after`
- **heal 条目 (type=5)**: 5 次，包含 `target_hp_after`
- **defeat 条目 (type=7)**: 3 次，HP 设为 0
- **change_pet 条目 (type=13)**: 18 次，包含 `new_pet_current_hp`/`new_pet_max_hp`

最终状态验证：
```
My: 圆号鱼 HP=0/467 (阵亡), 寒音蛇 HP=254/366 (存活)
Opp: 蜜瓜摇摇冰 HP=0/442 (阵亡), 寂灭骨龙 HP=0/425 (阵亡),
     翠顶夫人 HP=189/501 (存活), 尖嘴狐仙 HP=480/480 (满血)
```

### BUFF/效果 — 完整可见

观战模式下所有效果事件完整可见：
- effect_stage (type=3): 358 次
- effect_apply (type=2): 362 次
- effect_trigger (type=9): 88 次
- effect_link (type=10): 80 次
- weather_change (type=22): 6 次

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
| 0x130B | damage | **0** | 17 | **观战缺失，数据嵌入 0x1324** |
| 0x130C | damage_result | **0** | 17 | **观战缺失，数据嵌入 0x1324** |
| 0x13F3 | 未知 | **0** | 1 | **观战缺失** |

### action_resolve 条目类型分布

| Type | Kind | 数量 | 说明 |
|------|------|------|------|
| 1 | skill_cast | 70 | 技能释放（含完整技能信息） |
| 2 | effect_apply | 362 | 效果施加 |
| 3 | effect_stage | 358 | 效果阶段 |
| 4 | **damage** | **25** | **伤害（含 target_hp_after）** |
| 5 | heal | 5 | 治疗（含 target_hp_after） |
| 6 | energy | 21 | 能量变化 |
| 7 | defeat | 3 | 击败 |
| 9 | effect_trigger | 88 | 效果触发 |
| 10 | effect_link | 80 | 效果链接 |
| 13 | change_pet | 18 | 换宠（含 new_pet_current_hp） |
| 22 | weather_change | 6 | 天气变化 |
| 24 | unknown_type_24 | 7 | 未知 |
| 25 | ai_action | 94 | AI 行为 |
| 35 | data_update | 125 | 数据更新 |
| 37 | supply_pet | 3 | 补充精灵 |

---

## 对工具的影响

### 已正常工作的功能

1. **HP 追踪**: 通过 action_resolve 的 damage/heal/defeat 条目完整追踪
2. **己方技能提取**: 4 个装备技能完整可见
3. **BUFF/效果追踪**: 所有效果事件完整可解析
4. **换宠追踪**: change_pet 事件含 HP、速度、能量等完整数据
5. **天气系统**: weather_change 事件正常解析

### 观战特有的额外数据

1. **双方阵容全亮**: battle_enter 时双方 12 只精灵全部可见，可以做完整阵容对比分析
2. **对手速度已知**: 所有 6 只对手精灵的速度值（battle_stats[5]）在战斗开始时即可获取
3. **对手使用技能可追踪**: 通过 skill_cast 事件逐步积累对手的 used_skills
4. **data_update 事件 (type=35)**: 出现 125 次，可能包含更多状态数据，值得进一步解析

### 与普通 PvP 一致的已知局限

1. **对手装备技能不可见**: 对手的 equipped_skills 始终为空，只能通过战斗中使用的技能逐步推断
2. **对手属性不可见**: 对手的物攻/物防/特攻/特防始终为 0
3. **round_start HP 重置**: round_start 的 wrapper 数据会重置对手 HP（普通 PvP 也有此问题）
