# 战斗状态追踪系统缺陷全景报告

**审查日期**: 2026-05-16
**审查范围**: battle_state.py, battle.py, event_formatter.py, battle_processor.py, constants.py, innate_hooks.py, damage_calc.py
**审查方法**: 5 个并行 code-reviewer 子代理，分别覆盖状态追踪、协议解析、事件格式化、处理器集成、天赋伤害

---

## CRITICAL (1)

### C1: 跨战斗侧边槽位映射污染

**文件**: `src/analysis/battle_state.py:138-183`

`_handle_battle_enter` 重置 `state["events"]`、`state["result"]` 和宠物列表，但**不重置**以下私有字段：
- `_opponent_slots`
- `_player_slots`
- `_opponent_actor_id`
- `_player_actor_id`

这些字段只在 `__init__` 中设置（第 70-73 行）。

**复现场景**: 第一场战斗对手换宠到槽位 3，`_opponent_slots = {3}`。第二场战斗我方宠物在槽位 3，`_is_mine(3)` 检查 `3 in self._opponent_slots` 返回 `False`，我方所有事件路由到 `opp_active`。

**修复**: 在 `_handle_battle_enter` 顶部添加：
```python
self._opponent_slots.clear()
self._player_slots.clear()
self._opponent_actor_id = None
self._player_actor_id = None
```

---

## HIGH (22)

### 状态追踪 (battle_state.py)

#### H1: _handle_change_pet_entry 直接 mutate 入参 entry

**文件**: `battle_state.py:402`

```python
entry["_prev_active_name"] = active.get("name", "?")
```

直接修改调用者传入的 `detail["entries"]` 列表中的 entry 字典。由于 `handle_event` 将同一 `detail` 存入 `state["events"]`（第 89-90 行），且同一事件可能被 formatter/hooks/replay 消费，这是共享可变状态突变。

**修复**: 将 `_prev_active_name` 存储在 tracker 独立字段或副本中。

---

#### H2: effect_links/triggered_effects/skill_states 无限增长

**文件**: `battle_state.py:503-508, 517-523, 609-615`

这些列表/字典在宠物上追加但**永不清除**——换宠时也不清理。`_handle_change_pet_entry` 清除了 `buffs` 和 `combo_bonus`（第 427-428 行），但保留了 `effect_links`、`triggered_effects`、`skill_states`、`used_skills`。

30 回合战斗中 `triggered_effects` 可积累数百条目，每次 `get_state()` 的 `deepcopy` 都复制全部累积数据。

**修复**: 换宠时清除 `effect_links`、`triggered_effects`、`skill_states`。考虑将 `triggered_effects` 改为每回合滑动窗口。

---

#### H3: _update_pets_from_wrappers 用 `side == 1` 判断我方

**文件**: `battle_state.py:657-726`

第 661 行 `is_mine` 检查为 `side == 1 or side == "我方"`。但多槽位场景下我方 side 可以是 2、3 等。如果 `round_start` wrapper 中 `side = 2`，会被路由到 `opp_pets`，为我方宠物创建虚假对手条目。

**修复**: 使用 `_is_mine(side)` 替代硬编码 `side == 1`。

---

#### H4: _handle_defeat_entry 字段名不一致

**文件**: `battle_state.py:294`

击败处理器读取 `entry.get("target_side", "")`，但测试发送 `defeat_target_side`，formatter 读取 `entry.get("target_side")` 和 `entry.get("actor_side")`。如果协议发送 `defeat_target_side`，状态跟踪器将无法更新 HP。

**修复**: 统一字段名，添加 `entry.get("defeat_target_side")` 回退。

---

#### H5: _is_mine 回退逻辑对未知槽位不正确

**文件**: `battle_state.py:203`

当槽位不在 `_opponent_slots` 或 `_player_slots` 中时，回退为 `return 1 <= v <= 6`。结合 C1（跨战斗槽位映射不重置），如果 `_opponent_slots` 为空且对手在槽位 3，`_is_mine(3)` 返回 `True`，对手事件路由到 `my_active`。

**修复**: 使用 `_is_mine()` 或在 `battle_enter` 时从 wrapper 数据预填充槽位映射。

---

#### H6: get_state() 每次 deepcopy 整个 state

**文件**: `battle_state.py:115-124`

每次 `handle_event` 返回 `self.get_state()`，执行 `copy.deepcopy(self.state)`。30 回合战斗可产生 200+ 事件，每个事件 10+ entries。`BattleProcessor.process_event` 调用 `handle_event`（deepcopy 一次），然后 `battle_active()` 又调用 `get_state()`（再 deepcopy 一次），加上 formatter/hooks 可能再次读取。

**修复**: (a) 将 events 从 state 分离，单独存储不参与 deepcopy；(b) 缓存 state 直到下次 handle_event；(c) battle_active() 直接读 tracker.state 而非 get_state()。

---

### 协议解析 (battle.py)

#### H7: 多段伤害合并依赖启发式而非协议字段

**文件**: `battle.py:427-465`, `event_formatter.py:654-699`

伤害条目未从协议提取 `hit_count`。`_merge_damage_events` 通过相同 `target_side` + `damage` 值分组合并，产生误报（两次碰巧相同伤害被合并）和漏报（多段伤害每段不同时无法合并）。

协议已有 `is_last_hit`（第 401 行）和 `exec_index`（第 402 行），但未用于合并逻辑。

**修复**: 从协议提取 `is_last_hit`/`exec_index`，合并逻辑使用这些字段而非启发式。

---

#### H8: extract_1316_enter 原始回退缺少多个字段

**文件**: `battle.py:1085-1109` vs `1048-1083`

Schema 优先路径提取了原始回退路径省略的字段：

| 字段 | Schema 路径 | 原始回退 |
|------|------------|---------|
| `weather_expire_round` | 有 | **缺失** |
| `battle_state` | 有 | **缺失** |
| `battle_state_name` | 有 | **缺失** |
| `battle_cfg_ids` (列表) | 有 | **缺失**（只有单个 `battle_cfg_id`） |
| `battle_start_time` | 有 | **缺失** |

`battle_state.py:156` 的 `_handle_battle_enter` 调用 `detail.get("weather_expire_round")`，原始路径时将返回 `None`。

**修复**: 原始回退路径必须补全所有 schema 路径的字段。

---

#### H9: extract_132c_finish 原始回退缺少宠物级字段

**文件**: `battle.py:1251-1293` vs `1198-1249`

Schema 路径的 `finish_pet_infos` 包含 6 个字段（`pet_gid`/`remain_hp`/`remain_energy`/`mod_energy`/`battle_max_hp`/`uin`），原始路径只有 4 个（缺少 `mod_energy` 和 `uin`）。此外 `total_pvp_score`/`max_pvp_score`/`create_battle_ret` 也缺失。

**修复**: 补全原始回退路径的所有字段。

---

#### H10: 伤害 IR 子消息启发式失败时静默默认 0

**文件**: `battle.py:444-465`

伤害提取通过 IR 子项（field 12）启发式匹配伤害子消息。当匹配失败时，`dmg_sub` 为 `None`，damage 字段不存在，`_handle_damage_entry` 使用 `entry.get("damage", 0)` 默认为 0，无日志警告。

**修复**: 添加回退机制和日志警告。

---

### 事件格式化 (event_formatter.py)

#### H11: 暴击未在伤害摘要中显示

**文件**: `event_formatter.py:115-119`

`is_critical` 存在于 detail 字典中（第 130 行），但摘要字符串不包含暴击指示。用户无法从时间线判断是否暴击。

**修复**: 暴击时在摘要中显示 "暴击" 标记。

---

#### H12: 属性克制未在伤害摘要中显示

**文件**: `event_formatter.py:115-119, 133`

`restraint_type`（-3 到 +3）存在于 detail 字典中，但摘要只显示原始伤害。对于 Pokemon 风格的战斗分析器，属性克制是最关键的信息。

**修复**: 显示 "效果拔群"/"收效甚微" 等克制标签。

---

#### H13: _merge_damage_events 合并忽略字段差异

**文件**: `event_formatter.py:654-699`

合并只比较 `target_side`/`damage`/`skill_name`，不检查 `has_shield`/`is_critical`/`is_hit`。导致：
- 普攻 + 暴击被错误合并，暴击标记丢失
- 未命中 (is_hit=False, damage=0) 可能与另一次匹配合并

**修复**: 合并条件增加 `is_hit`/`is_critical` 差异检查。

---

#### H14: 天气格式化器显示原始 ID

**文件**: `event_formatter.py:358-380`

`_fmt_weather_change` 尝试 `entry.get("weather_name")`，但协议层从未提取该字段。回退到 `str(weather_id)`，显示 "天气变化: 3"。

**修复**: 使用 `loader.get_attr_name(weather_id)` 解析天气名称，或在协议层提取。

---

#### H15: 治疗格式化器不显示治疗量

**文件**: `event_formatter.py:217-234`

协议只提取 `target_hp_after`（第 563-565 行），不提取实际治疗量。摘要显示 "治疗: 我方→我方 HP→280"，无法判断恢复了多少。

**修复**: 在协议层提取治疗量，或在 state tracker 中计算 HP 差值。

---

### 处理器集成 (battle_processor + constants)

#### H16: Hooks 硬编码 opcode 检查，PVP_PERFORM/PREPLAY 被静默忽略

**文件**: `hooks/opponent_tracker.py:53-56`, `hooks/switch_advisor.py:71`

processor 的 `opcode_to_triggers()` 正确将 `0x13FC`/`0x13F3` 路由到 `ON_ACTION_RESOLVE` 触发器。但 `OpponentTrackerHook.process()` 和 `SwitchAdvisorHook.process()` 内部用 `ctx.opcode == OPCODE_ACTION_RESOLVE` 硬编码检查。当 0x13FC 或 0x13F3 到达时，hook 被调用但主体跳过所有逻辑。

**影响**: **整个 PVP_PERFORM/PREPLAY 扩展代码是死代码**。对手技能和换宠模式追踪有缺口。

**修复**: 使用集合匹配：
```python
ACTION_OPCODES = {OPCODE_ACTION_RESOLVE, OPCODE_PVP_PERFORM, OPCODE_PREPLAY}
if ctx.opcode in ACTION_OPCODES:
```
或在 HookContext 上设置 `is_action_resolve: bool` 标志。

---

#### H17: formatter 和 state tracker 的 side 判定逻辑不一致

**文件**: `event_formatter.py:52-58` vs `battle_state.py:191-203`

formatter 的 `_is_mine()` 用简单范围检查 `1 <= v <= 6`。state tracker 的 `_is_mine()` 额外检查 `_opponent_slots`/`_player_slots` 集合。首次 change_pet 更新槽位映射后，两者可能对同一 side 值产生不同判定。

**修复**: formatter 使用 state 中已解析的 side 信息，或共享槽位映射逻辑。

---

#### H18: BATTLE_ENTER 在 DAMAGE_OPCODES 中导致首包就计算伤害

**文件**: `battle_processor.py:90`

`BATTLE_ENTER` (0x1316) 在 `DAMAGE_OPCODES` 集合中。battle_enter 后 `battle_active()` 返回 True，触发 `_compute_damage_analysis()`。此时对手没有装备技能（协议只提供我方），状态未进入 resolving 阶段，产生误导性伤害预测。

**修复**: 从 `DAMAGE_OPCODES` 移除 `OPCODE_BATTLE_ENTER`，或添加 phase guard (`state.get("round", 0) > 0`)。

---

#### H19: Revive handler 更新活跃宠物而非被复活宠物

**文件**: `battle_state.py:525-541`

`_handle_revive_entry` 使用 `self._get_active_for_side(target_side)` 找到要更新的宠物。如果被复活的宠物在替补席（非当前活跃宠物），HP 和 revive_count 更新到了错误的宠物。

**修复**: 使用 `revive_pet_id` 在 `my_pets`/`opp_pets` 中搜索正确目标。

---

### 天赋与伤害 (innate_hooks + damage_calc)

#### H20: combo_modify_hook 属性触发完全失效

**文件**: `innate_hooks.py:67-69`, `data/game/innate_skills.json:77,137,150`

两层错误：
1. Hook 读取 `skill_dam_type`（SDT 值，2-21 范围），直接与 `innate_skills.json` 的 `element` 字段（属性图表 ID）比较。从未进行 SDT→属性图表 ID 转换。
2. JSON 中翼系技能 element=14 实为机械系（应为 9）。

**复现**: 翼系宠物使用翼系技能（SDT=10, type_chart=9），hook 比较 SDT 10 vs element 14，不匹配，连击加成永远不触发。

测试 `test_combo_element_trigger` 用 `skill_dam_type=14` 掩盖了此 bug。

**修复**:
```python
from src.analysis.constants import SDT_TO_TYPE
raw_sdt = ctx.get("skill_meta", {}).get("skill_dam_type", 0)
skill_element = SDT_TO_TYPE.get(raw_sdt, raw_sdt)
```
并修正 `innate_skills.json` 中翼系 element 为 9。

---

#### H21: eff_label 在 pre_final hooks 之前计算，hooks 修改后标签过期

**文件**: `damage_calc.py:264`

```python
eff_label = self.chart.get_effectiveness_label(effectiveness)  # hooks 之前
ctx = self._run_hooks("pre_final", {...})  # hooks 可能改 effectiveness
return dmg, effectiveness, stab_mult, ..., eff_label, is_stab  # 返回过期标签
```

`type_resist_modify_hook` 可将 effectiveness 从 0.5 改为 1.0，但 `eff_label` 仍显示 "resisted"。

**修复**: 将 `eff_label` 计算移到 pre_final hooks 之后。

---

#### H22: stat_modify_hook 忽略 damage_type

**文件**: `innate_hooks.py:88-109`

"临界防御" 定义 `stat: "ATK"`，应只加成物理攻击。但 hook 不读取 `damage_type`，40% 加成应用到所有伤害类型。

**修复**: 按 `effect_params.stat` 过滤：ATK 只匹配物理（damage_type=2），SPA 只匹配特殊（damage_type=3）。

---

## MEDIUM (25)

### 状态追踪

| # | 问题 | 文件:行 |
|---|------|---------|
| M1 | events 列表无限增长，每次 deepcopy O(N)，WebSocket 推送 O(N²) | `battle_state.py:89-90` |
| M2 | `_handle_special_refresh` 只处理 energy_bottle，其他 refresh kind 被忽略 | `battle_state.py:560-567` |
| M3 | `_handle_battle_enter` 不检查宠物是否在场上就设为 active（无条件 `my_pets[0]`） | `battle_state.py:180-183` |
| M4 | `_handle_revive_entry` 回退 HP 设为 `max(1, current_hp)`，但 current_hp 可能非零 | `battle_state.py:538` |
| M5 | `_handle_skill_state_entry` 将宠物技能状态写入双方 active，对手获得幽灵条目 | `battle_state.py:609-615` |
| M6 | `_handle_effect_apply_entry` change_type==2 且 buff_stack 缺失时跳过 stage 更新 | `battle_state.py:474` |

### 协议解析

| # | 问题 | 文件:行 |
|---|------|---------|
| M7 | `effect_stage` 命名误导——实为 "效果触发" 而非 "阶段" | `battle.py:511-523` |
| M8 | 治疗条目不提取实际治疗量，只有 HP 快照 | `battle.py:549-566` |
| M9 | `combo_skill_cast` 缺少与原始 `skill_cast` 的关联机制 | `battle.py:657-677` |
| M10 | `effect_apply` 不提取 `buff_base_id` 值 | `battle.py:467-509` |
| M11 | 原始回退 `extract_1316_enter` 在 root 为 None 时可能 KeyError | `battle.py:1086` |
| M12 | change_pet battle_stats 注释误导（标注 `[HP,...]` 实为 `[other, max_hp, ...]`） | `battle.py:644` |

### 格式化与事件

| # | 问题 | 文件:行 |
|---|------|---------|
| M13 | `effect_apply` "stage" 标签应为 "层数" | `event_formatter.py:160-185` |
| M14 | `effect_stage` 输出调试风格文本（`base=ID`） | `event_formatter.py:188-200` |
| M15 | `skill_state` 用原始 pet_id 而非名称 | `event_formatter.py:383-395` |
| M16 | 8 个 IN_BATTLE_OPCODES 无处理器被静默丢弃（含 PET_SWITCH/PET_DEFEAT） | `constants.py:43-50` |
| M17 | combo 总伤害显示 `50x3` 而非 `50x3=150` | `event_formatter.py:687-694` |
| M18 | 缺失重要事件类型：SP_ENERGY、ROLE_SKILL_CAST、BATTLER_ESCAPE、PET_EVOLUTION 等 | `event_formatter.py:435-453` |
| M19 | formatter 的 `_fmt_change_pet` side 判定与 state tracker 不同 | `event_formatter.py:258-263` |

### 伤害计算

| # | 问题 | 文件:行 |
|---|------|---------|
| M20 | 多段伤害总伤害 KO 场景高估（`dmg * hit_count` 未考虑中途 KO） | `damage_calc.py:318` |
| M21 | Lifesteal 按单次伤害计算而非总伤害（3 连击时低估 3 倍） | `innate_hooks.py:175` |
| M22 | combo_bonus 可能与协议值重复计算（协议已含天赋加成时） | `innate_hooks.py:76` |
| M23 | 所有 hooks 直接 mutate ctx 字典，违反不可变原则 | `innate_hooks.py` 多处 |
| M24 | combo_modify_hook 用 `max()` 合并乘法修饰——两个 x2 得 x2 而非 x4 | `innate_hooks.py:59` |
| M25 | `battle_active()` 触发冗余 deepcopy（只读两个标量字段） | `battle_processor.py:187-189` |

---

## 数据覆盖度

- **天赋技能**: 仅 16 种 innate skill 定义，仅 2/6575 只宠物映射。NRC_AI 参考 309 技能效果 + 172 特性效果
- **事件类型**: 协议定义 50+ BattlePerformType，当前仅处理约 14 种
- **双路径一致性**: `extract_1316_enter` 和 `extract_132c_finish` 的原始回退路径字段不完整

---

## 修复优先级

### P0 — 影响正确性，必须立即修复
1. C1: battle_enter 重置槽位映射
2. H20: combo_modify_hook SDT→属性图表转换 + JSON 数据修正
3. H16: Hook opcode 检查改为集合匹配
4. H19: Revive 使用 revive_pet_id 匹配
5. H3: _update_pets_from_wrappers 使用 _is_mine()

### P1 — 影响 UI/用户体验
6. H11+H12: 伤害摘要显示暴击和属性克制
7. H21: eff_label 移到 hooks 后重新计算
8. H22: stat_modify_hook 按伤害类型过滤
9. H7: 多段伤害使用协议字段合并
10. H14+H15: 天气名称和治疗量显示
11. H4: 击败事件字段名统一

### P2 — 性能优化
12. H6: deepcopy 优化（分离 events、缓存 state）
13. H2: 清理换宠时的 effect_links/triggered_effects
14. M25: battle_active() 直接读 tracker.state

### P3 — 数据补全
15. H8+H9: 原始回退路径补全字段
16. 天赋技能数据扩展（当前 2→目标 100+ 宠物映射）
17. 事件类型覆盖（14→目标 30+ BattlePerformType）
