# Buff 与连击数追踪

本文档描述战斗系统中 buff 追踪、中毒层数追踪、连击数计算的完整流程。

## 数据流总览

```
协议包 (0x1324 action_resolve)
  │
  ▼
protocol/battle.py — 解析二进制 entry，提取 buff_id / buff_stack / combo_count 等
  │
  ▼
analysis/battle_state.py — 实时状态机，维护宠物 buff 列表、poison_stacks、combo_bonus
  │
  ▼
analysis/innate_hooks.py — 天赋 hook，根据 buff / pet 映射计算连击修正和伤害修正
  │
  ▼
analysis/damage_calc.py — 4 阶段 hook 管线，产出最终伤害和连击数
```

---

## 1. Buff 追踪

### 1.1 数据结构

每只宠物的 buff 列表存储在 `pet["buffs"]`，是一个 dict 列表：

```python
{
    "id": 20070011,            # buff ID
    "name": "中毒印记",         # 显示名
    "stage": 5,                # 当前层数/阶段
    "source_skill": "缠丝劲",   # 来源技能名（可选）
    "turns_applied": 3,        # 累计施加次数
    # 以下为协议原始字段（可选）：
    "change_type": 2,          # 1=ADD, 2=CHANGE, 3=REMOVE
    "buff_stack": 5,           # 协议提供的真实层数
    "buff_left_round": 3,      # 剩余回合数
    "buff_on_field_round": 0,  # 场上已存在回合数
    "is_hidden": False,        # 是否隐藏 buff
    "hidden_stack": 0,         # 隐藏层数
    "del_flag": 0,             # 删除标记
}
```

### 1.2 Buff 生命周期

状态机通过 `_handle_effect_apply_entry()` 处理 buff 事件（`src/analysis/battle_state.py`）：

| 事件 | change_type | 行为 |
|------|-------------|------|
| 施加新 buff | 1 (ADD) | 追加到 buffs 列表 |
| 更新已有 buff | 2 (CHANGE) | 更新 stage，合并额外字段，turns_applied +1 |
| 移除 buff | 3 (REMOVE) | 从 buffs 列表过滤移除 |

换宠时（`_handle_change_pet_entry`），新上场的宠物 buff 列表从协议数据重建。

### 1.3 协议解析层

`src/protocol/battle.py` 中 entry_type=2（effect_apply）从 `BattleBuffChange` 解析：

- **field 3** → `effect_id`（buff ID）
- **field 4** → `change_type`（ADD=1 / CHANGE=2 / REMOVE=3）
- **field 8.BattleBuffInfo**:
  - field 4 → `buff_stack`（真实层数，优先使用）
  - field 32 → `buff_left_round`
  - field 31 → `buff_on_field_round`
  - field 26 → `is_hidden`
  - field 27 → `hidden_stack`
  - field 30 → `del_flag`
- **field 12** → 来源技能信息（owner_side, skill_id, skill_name）

---

## 2. 中毒层数追踪

### 2.1 中毒 Buff ID

```python
POISON_BUFF_IDS = {20070010, 20070011, 20070012}
```

- `20070010` — 通用中毒
- `20070011` — 中毒印记
- `20070012` — 中毒印记（变体）

三种 buff 都计入中毒层数。

### 2.2 追踪逻辑

在 `_handle_effect_apply_entry()` 中，buff 更新完成后检查：

```python
if effect_id in POISON_BUFF_IDS:
    # 优先使用 buff_stack（协议提供的真实层数）
    # 其次使用 effect_stage
    # 最后递增已有值
    bstack = entry.get("buff_stack")
    if bstack is not None:
        active["poison_stacks"] = bstack
    else:
        stage = entry.get("effect_stage")
        if stage is not None:
            active["poison_stacks"] = stage
        else:
            active["poison_stacks"] = active.get("poison_stacks", 0) + 1
```

**关键**：`buff_stack` 优先于 `effect_stage`，因为 `effect_stage` 可能是 `change_type` 的别名（如 2=CHANGE），不代表真实层数。

### 2.3 使用位置

`poison_stacks` 被先天技能 hook 中的 `per_poison_stack` trigger 消费：

```python
# innate_hooks.py — combo_modify_hook
elif trigger == "per_poison_stack":
    stacks = defender.get("poison_stacks", 0)
    additive_bonus += params.get("value", 0) * stacks
```

---

## 3. 连击数计算

### 3.1 公式

```
total_hits = (base_hits + combo_bonus) × multiplier + additive_bonus
```

| 变量 | 来源 | 说明 |
|------|------|------|
| `base_hits` | 技能描述正则 `(\d+)连击` | 技能固有的连击次数，默认 1 |
| `combo_bonus` | 协议 combo_skill_cast (entry_type=30) | 协议提供的连击加成，目前测试数据中始终为 0 |
| `multiplier` | 先天技能 hook（`always` trigger, `multiplier > 1`） | 连击倍率，多个 multiplier 取 max |
| `additive_bonus` | 先天技能 hook（多个来源累加） | 连击加法修正 |

### 3.2 additive_bonus 来源

`combo_modify_hook` 遍历所有 `effect_type == "combo_modify"` 的先天技能，根据 trigger 累加：

| Trigger | 条件 | 效果 |
|---------|------|------|
| `always` | 无条件 | `+value` |
| `per_poison_stack` | 防守方有中毒层数 | `+value × poison_stacks` |
| `skill_element_used` | 当前技能属性匹配 | `+value` |
| `specific_skill` | 当前技能 ID 匹配 | `+value` |

### 3.3 先天技能发现机制

先天技能有两个来源（`_get_all_innate_skills`）：

1. **Buff 扫描**：遍历宠物 `buffs` 列表，对每个 buff_id 调用 `get_innate_skill(buff_id)` 匹配 `innate_skills.json` 的 `skills` 定义
2. **Pet 映射**：通过宠物的 `base_id` 调用 `get_innate_skills_for_pet(base_id)` 查找 `innate_skills.json` 的 `pets` 映射

两个来源合并去重。这确保了不以 buff 形式出现的被动天赋（如侵蚀/毒连击 29990910）也能被发现。

### 3.4 已定义的 combo_modify 天赋

| buff_id | 名称 | trigger | 效果 |
|---------|------|---------|------|
| 29990910 | 毒连击（侵蚀） | `per_poison_stack` | 每层中毒 +1 连击 |
| 20450020 | 连击+1 | `always` | 连击 +1 |
| 20450050 | 通用连击+1 | `always` | 连击 +1 |
| 21080150 | 仅精灵连击+1 | `always` | 连击 +1 |
| 20460160 | 击败后连击+2 | `always` | 连击 +2 |
| 20450030 | 连击翻倍 | `always` | multiplier=2 |
| 20450120 | 特定技能连击+2 | `specific_skill` (skill_id=7180340) | 趁火打劫 +2 连击 |
| 20350300 | 翼系连击 | `skill_element_used` (element=14) | 翼系技能 +1 |
| 20172000 | 翼加连击 | `skill_element_used` (element=14) | 翼系技能 +1 |
| 20170570 | 虫系连击捆绑 | `skill_element_used` (element=12) | 虫系技能 +1 |
| 20170700 | 回合结束连击+1 | `turn_end` | 回合结束 +1（hook 中未实现此 trigger） |

### 3.5 Pet 被动天赋映射

`data/game/innate_skills.json` 中的 `pets` 字段：

```json
{
  "pets": {
    "3419": ["29990910"],
    "3420": ["29990910"]
  }
}
```

- 3419（厉毒小萝）→ 侵蚀（毒连击）
- 3420（厉毒修萝）→ 侵蚀（毒连击）

同一进化链的精灵共享被动天赋。

### 3.6 计算示例

**厉毒修罗 使用 缠丝劲 vs 身上 5 层中毒印记的白发路路**：

```
base_hits = 2            # 缠丝劲描述 "2连击"
combo_bonus = 0          # 协议未提供
multiplier = 1           # 无翻倍天赋
additive_bonus = 5       # 侵蚀(29990910): per_poison_stack × 5 层

total_hits = (2 + 0) × 1 + 5 = 7
```

**厉毒修罗 使用 趁火打劫 vs 同上对手（且持有 buff 20450120）**：

```
base_hits = 2            # 趁火打劫描述 "2连击"
combo_bonus = 0
multiplier = 1
additive_bonus = 5 + 2   # 侵蚀 5 层 + 特定技能连击+2 (趁火打劫 id=7180340)

total_hits = (2 + 0) × 1 + 7 = 9
```

---

## 4. 其他先天技能 Hook

### 4.1 属性修正 — `stat_modify_hook`（post_base 阶段）

| trigger | 条件 | 效果 |
|---------|------|------|
| `hp_below` | 当前 HP ≤ 阈值 | 基础伤害 × (1 + modifier_pct) |

已定义：`20410080` 临界防御 — HP ≤ 50% 时 ATK +40%。

### 4.2 属性抵抗修正 — `type_resist_modify_hook`（pre_final 阶段）

将属性克制倍率下限提升至 `min_effectiveness`。

已定义：`20420100` 无视抵抗 — 倍率下限 1.0（被克制时变为 1.0×）。

### 4.3 威力修正 — `power_modify_hook`（post_calc 阶段）

| trigger | 条件 | 效果 |
|---------|------|------|
| `first_strike` | 攻击方先手 | 附加吸血（lifesteal_pct%） |

已定义：`20430060` 先机虹吸 — 先手攻击时吸血 30%。

### 4.4 伤害减免 — `damage_reduction_hook`（pre_final 阶段）

根据防守方 buff 的 `buffbase` 参数降低基础伤害。从 `buff_map.json` 和 `buffbase_map.json` 查询每个 buff 的减免率和适用伤害类型（物理=2 / 特殊=3），按层数累加，上限 95%。

---

## 5. 伤害计算 Hook 管线

```
DamageCalculator.calculate(attacker, defender, skill)
  │
  ├── Phase 1: pre_power       — 修改技能威力（暂无 hook）
  ├── Phase 2: 战斗属性计算     — 从 buff 查询攻防修正
  ├── Phase 3: 基础伤害 + post_base
  │     └── stat_modify_hook   — HP 低于阈值 → 基础伤害 +40%
  ├── Phase 4: 乘区修正 + pre_final
  │     ├── type_resist_modify_hook — 属性克制下限提升
  │     └── damage_reduction_hook   — buff 伤害减免
  └── Phase 5: 最终化 + post_calc
        ├── combo_modify_hook   — 连击数修正 → total_damage = per_hit × hit_count
        └── power_modify_hook   — 先手吸血等附加效果
```

---

## 6. 关键文件索引

| 文件 | 职责 |
|------|------|
| `src/analysis/battle_state.py` | 状态机：buff 列表维护、poison_stacks、combo_bonus |
| `src/analysis/innate_hooks.py` | 天赋 hook：combo/stat/type/power 四种修正 |
| `src/analysis/damage_calc.py` | 伤害计算引擎：4 阶段 hook 管线 |
| `data/game/innate_skills.json` | 天赋技能定义 + pet 被动天赋映射 |
| `src/data/loader.py` | 数据访问：`get_innate_skill`、`get_innate_skills_for_pet`、`get_buff_damage_reduction`、`get_buff_stat_modifiers`、`get_speed_buff_modifiers` |
| `src/protocol/battle.py` | 协议解析：buff 字段提取、combo_skill_cast 解析 |
