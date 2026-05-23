# PRD: 精灵先天技能系统 (Innate Skill System)

## 1. Introduction / 概述

当前伤害预测系统只计算单次命中伤害，未考虑连击数（combo hit count）和精灵先天技能（innate skills）的修正效果。例如缠丝劲基础为 2 连击、25 威力，但实际战斗中因先天技能（如中毒层数增加连击数）可能打出 143×7 = 1001 总伤害，而系统仅预测 91。

本 PRD 添加先天技能系统，在伤害计算前后通过 hook 机制注入先天技能修正，使伤害预测准确反映连击总伤害和先天技能效果。

## 2. Goals / 目标

- 伤害预测准确反映连击技能的实际总伤害（per-hit × hit_count）
- 支持先天技能对伤害的修正（连击数增减、威力修正、防御修正、属性抵抗修正等）
- 先天技能数据以静态 JSON 文件存储在本地，启动时加载
- 通过战斗回放验证：缠丝劲等连击技能的预测伤害与实际战斗日志一致

## 3. User Stories / 用户故事

### US-001: 解析 BPT_COMBO_SKILL 协议事件

**Description:** 作为系统，我需要从 0x1324/0x13FC 的 entry_type=30（BPT_COMBO_SKILL）中提取 combo_index 和 combo_count，以便追踪实际连击数。

**Acceptance Criteria:**
- [ ] 在 `src/protocol/battle.py` 的 `_extract_1324_entry` 中添加 `entry_type == 30` 的处理分支
- [ ] 从 `BattleComboSkillCast` schema 中提取 `combo_index`（field 8）和 `combo_count`（field 9）
- [ ] 提取 skill_id（field 3）、caster_id（field 1）、target_id（field 2）
- [ ] 解析结果包含 kind="combo_skill_cast"，附有 combo_index、combo_count、skill_id 等字段
- [ ] 类型检查通过

### US-002: 创建先天技能数据文件

**Description:** 作为开发者，我需要一个 JSON 数据文件定义精灵的先天技能及其效果，供伤害计算使用。

**Acceptance Criteria:**
- [ ] 创建 `data/game/innate_skills.json`，结构为以宠物 base_id 为 key 的字典
- [ ] 每个先天技能条目包含：name、description、effect_type、effect_params
- [ ] effect_type 包括以下类别：
  - `combo_modify`：连击数修正（如"中毒层数+连击"、"固定连击数"）
  - `power_modify`：威力修正（如"应对成功威力翻倍"）
  - `stat_modify`：属性修正（如"HP<50%防御+40%"）
  - `type_resist_modify`：属性抵抗修正（如"无视属性抵抗"）
  - `energy_modify`：能量修正（如"每回合结束+1能量"）
- [ ] 至少包含以下已知先天技能数据（来自游戏解包 BUFF_CONF.json）：
  - S2 赛季天赋：免疫绝处逢生 (20030370)、能量充盈 (20170160)、临界防御 (20410080)、无视抵抗 (20420100)、先机虹吸 (20430060)
  - 连击修正：敌方每层中毒连击+1 (29990910)、翼系技能连击+1 (20350300)、连击+1 (20450020)、连击翻倍 (20450030)、通用连击+1 (20450050)
  - 条件连击：回合结束连击+1 (20170700)、虫系连击捆绑 (20170570)、翼加连击 (20172000)
- [ ] 类型检查通过

### US-003: 在 battle state 中追踪连击数和毒层数

**Description:** 作为系统，我需要在战斗状态中追踪每个精灵的连击数修正和中毒层数，以便先天技能 hook 使用这些信息。

**Acceptance Criteria:**
- [ ] `BattleStateTracker` 的宠物状态新增字段：`combo_bonus`（连击数修正值，int）、`poison_stacks`（中毒层数，int）
- [ ] 处理 `combo_skill_cast` 事件时更新 combo_bonus
- [ ] 处理 `effect_apply` 事件时，如果 effect 是中毒类 buff，更新 poison_stacks
- [ ] 换宠（change_pet）时重置 combo_bonus（新精灵从 0 开始）
- [ ] 类型检查通过

### US-004: 实现伤害计算 hook 系统

**Description:** 作为开发者，我需要在伤害计算器中添加 hook 机制，让先天技能可以在计算前后修改参数和结果。

**Acceptance Criteria:**
- [ ] `DamageCalculator` 类新增 `hooks` 列表，存储 hook 函数
- [ ] 每个 hook 函数签名：`(stage: str, context: dict) -> dict`，其中 stage 为 "pre_power"、"post_base"、"pre_final" 等
- [ ] `pre_power` hook：可以修改技能威力（如应对成功威力翻倍）
- [ ] `post_base` hook：可以修改基础伤害值、攻防属性（如防御+40%）
- [ ] `pre_final` hook：可以修改最终伤害乘数（如无视属性抵抗）
- [ ] `post_calc` hook：可以修改最终结果（如连击数修正、吸血效果）
- [ ] 内置 hook 注册函数 `register_hook(hook_fn)`
- [ ] 类型检查通过

### US-005: 实现先天技能 hook 函数

**Description:** 作为系统，我需要将先天技能数据转换为具体的 hook 函数，注入到伤害计算器中。

**Acceptance Criteria:**
- [ ] 创建 `src/analysis/innate_hooks.py` 模块
- [ ] 实现 `get_innate_hooks_for_pet(pet_data, innate_skills_data) -> list[hook_fn]`
- [ ] 实现 combo_modify hook：根据 defender 的 poison_stacks 增加 combo_count
- [ ] 实现 stat_modify hook：根据 HP 阈值修改防御属性（如 HP<50% DEF+40%）
- [ ] 实现 type_resist_modify hook：将 effectiveness 下限设为 1.0（无视抵抗）
- [ ] 实现 power_modify hook：根据条件修改威力
- [ ] hook 函数从 battle state 的 context 中读取当前状态（poison_stacks、hp_pct 等）
- [ ] 类型检查通过

### US-006: DamageResult 支持连击伤害

**Description:** 作为系统，我需要在伤害预测结果中包含连击数和总伤害范围，以便前端正确展示。

**Acceptance Criteria:**
- [ ] `DamageResult` 新增字段：`hit_count`（int，默认 1）、`total_min_damage`（int）、`total_max_damage`（int）
- [ ] `hit_count` 从技能基础连击数 + 先天技能修正计算得出
- [ ] `total_min_damage = min_damage * hit_count`，`total_max_damage = max_damage * hit_count`
- [ ] `can_ko` 判断使用 total_min_damage 而非 min_damage
- [ ] `pct_hp_range` 使用总伤害计算百分比
- [ ] 技能基础连击数从 skill_map.json 的 desc 字段解析（如 "2连击" → 2），或从 skill_result 的 effect_id 判断
- [ ] `warnings` 中包含连击信息，如 "2连击+5中毒加成=7总连击"
- [ ] 类型检查通过

### US-007: 连击伤害前端展示

**Description:** 作为用户，我需要在战斗界面看到连击技能的总伤害预测，而不仅仅是单次命中伤害。

**Acceptance Criteria:**
- [ ] BattleLive 页面的伤害预测卡片显示总伤害范围（如 "1001~1176 (7连击)"）
- [ ] 当 hit_count > 1 时，额外显示单次伤害和连击数的分解信息
- [ ] 先天技能修正信息显示在 warnings 中（如 "中毒5层→连击+5"）
- [ ] 类型检查通过
- [ ] Verify in browser using dev-browser skill

### US-008: 集成验证 - 战斗回放分析

**Description:** 作为开发者，我需要使用现有 battle_session_1 回放数据验证先天技能系统的正确性。

**Acceptance Criteria:**
- [ ] 使用 `python -m scripts.replay_to_frontend --delay 80 --session battle_session_1` 回放战斗
- [ ] 分析回放日志中的连击伤害事件（BPT_COMBO_SKILL entry_type=30）
- [ ] 对比伤害预测值与实际伤害值，确认在合理误差范围内
- [ ] 如果回放数据不包含连击/先天技能场景，编写单元测试用已知数据（缠丝劲 143×7 案例）验证
- [ ] 所有 pytest 测试通过

## 4. Functional Requirements / 功能需求

- **FR-1:** 系统必须从 `BattleComboSkillCast` 协议消息（entry_type=30）中提取 combo_index 和 combo_count
- **FR-2:** 系统必须从 `data/game/innate_skills.json` 加载先天技能数据，以宠物 base_id 为 key
- **FR-3:** 伤害计算器必须支持 hook 机制，允许先天技能在 pre_power、post_base、pre_final、post_calc 四个阶段修改计算
- **FR-4:** 伤害计算器在计算连击技能时，必须将单次伤害 × 连击数得出总伤害
- **FR-5:** 连击数 = 技能基础连击数 + 先天技能修正（中毒层数加成、翼系技能加成等）
- **FR-6:** `DamageResult` 必须包含 hit_count、total_min_damage、total_max_damage 字段
- **FR-7:** 技能基础连击数从 skill_map.json 解析：优先从 desc 字段（"X连击"），其次从 skill_result 的 effect_id 匹配连击类 buff
- **FR-8:** 战斗状态追踪器必须追踪 poison_stacks 和 combo_bonus
- **FR-9:** 先天技能效果包括：连击数修正、威力修正、属性修正（HP阈值防御提升）、属性抵抗修正（无视抵抗）、能量修正（每回合+1）
- **FR-10:** 前端伤害预测必须显示总伤害范围和连击信息

## 5. Non-Goals / 不在范围内

- 不实现先天技能的实时协议获取（使用静态数据文件）
- 不实现先天技能的自动更新/爬取
- 不实现应对系统（应对攻击/状态/防御）的伤害修正（未来扩展）
- 不实现迅捷（Quick）机制的伤害修正
- 不实现吸血效果的伤害计算（仅作为 warning 提示）
- 不修改 buff_map.json 或 skill_map.json 的数据结构

## 6. Technical Considerations / 技术考虑

### 6.1 Hook 系统设计

```python
# Hook 函数签名
HookContext = Dict[str, Any]  # 包含 attacker, defender, skill_meta, battle_state 等
HookStage = Literal["pre_power", "post_base", "pre_final", "post_calc"]
HookFn = Callable[[HookStage, HookContext], HookContext]

class DamageCalculator:
    def __init__(self, type_chart=None):
        self.chart = type_chart or TypeChart()
        self._hooks: List[HookFn] = []

    def register_hook(self, hook: HookFn) -> None:
        self._hooks.append(hook)

    def _apply_hooks(self, stage: HookStage, context: HookContext) -> HookContext:
        for hook in self._hooks:
            context = hook(stage, context)
        return context
```

### 6.2 连击数计算公式

```
base_hits = parse_from_skill_desc(skill_meta)  # e.g. 2 from "2连击"
combo_bonus = sum(innate_combo_modifiers)       # from poison stacks, wing skills, etc.
total_hits = base_hits + combo_bonus
total_damage = per_hit_damage * total_hits
```

### 6.3 先天技能数据结构

```json
{
  "<base_id>": {
    "name": "精灵名称",
    "innate_skills": [
      {
        "id": "poison_combo",
        "name": "毒连击",
        "description": "敌方每有1层中毒，对他的攻击连击数+1",
        "effect_type": "combo_modify",
        "effect_params": {
          "trigger": "per_poison_stack",
          "value": 1,
          "scope": "attack_against_self"
        },
        "source_buff_ids": [29990910]
      }
    ]
  }
}
```

### 6.4 技能连击数解析

从 `skill_map.json` 的 `desc` 字段提取连击数：
- `"造成物伤，2连击。"` → 2
- `"造成物伤，3连击"` → 3
- 无连击描述 → 1

也可通过 `skill_result` 中的 effect_id 匹配已知连击类 buff（如 1032002 是缠丝劲的连击效果 ID）。

### 6.5 完整 Buff 列表（来自游戏解包数据）

以下数据来自 `P0pola/Roco-Kingdom-World-Data` 仓库的 `Bin/BinDataCompressed/BUFF_CONF.json` 和 `BUFFBASE_CONF.json`，是游戏客户端的官方配置。

#### 6.5.1 S2 赛季天赋 Buff（5个）

| Buff ID | BuffBase ID | 名称 | 描述 | type | 伤害计算 hook 阶段 |
|---------|------------|------|------|------|-------------------|
| 20030370 | 2003037 | 免疫绝处逢生 | 免疫绝处逢生复活机制 | 3 (被动) | 无直接影响 |
| 20170160 | 2017016 | 能量充盈 | 每回合结束获得1能量 | 3 (被动) | 无直接影响 |
| 20410080 | 2041008 | 临界防御 | 生命值低于50%时，双攻+40% | 4 (条件触发) | `post_base`: 修改攻击属性 |
| 20420100 | 2042010 | — | 无视敌方的系别抵抗 | 4 (条件触发) | `pre_final`: effectiveness 下限=1.0 |
| 20430060 | 2043004 | 先机虹吸 | 先手攻击时，额外吸血30% | 3 (被动) | `post_calc`: 增加 warning 提示 |

**BuffBase 参数详情：**

- **2003037 (免疫绝处逢生)**: `client_trigger_type=-1`, params: `[6, 20380120]` — 屏蔽特定 buff ID 20380120
- **2017016 (能量充盈)**: `trigger_type=7` (回合结束), `client_trigger_type=15`, params: `[1019001, 10000, 0, 0]` — 添加 buff 1019001，100% 概率
- **2041008 (临界防御)**: `client_trigger_type=-1`, params: `[1, 50, 20110462, 0]` — HP ≤ 50% 时触发，关联 buff 20110462
- **2042010 (无视抵抗)**: `client_trigger_type=11`, params: `[0, 0, 100, 0]` — 100% 无视抵抗
- **2043004 (先机虹吸)**: `client_trigger_type=-1`, params: `[0, 0, 0, 1011008, 0, 0, 2]` — 吸血关联 buff 1011008

#### 6.5.2 连击修正 Buff（55个，来自 BUFF_CONF）

按功能分类：

**A. 连击数 +1 类（通用）：**

| Buff ID | BuffBase ID | editor_name | type | add_max | 参数说明 |
|---------|------------|-------------|------|---------|---------|
| 20450010 | 2045001 | 规则--连击次数+1 | 3 | 99 | trigger=12, param1=1(增加量), param2=810170(关联技能) |
| 20450020 | 2045002 | 连击次数+1 | 3 | 99 | trigger=12, param1=1(增加量) |
| 20450050 | 2045005 | 通用连击次数+1 | 1 | 99 | trigger=12, param1=1(增加量) |
| 20450053 | 2045005 | (被动版)连击+1 | 4 | 1 | 被动型，base 同 2045005 |
| 20450054 | 2045005 | 朔夜伊芙连击+1 | 1 | 99 | base 同 2045005 |
| 20450070 | 2045007 | 虫咬虫鸣技能，连击次数+1 | 4 | 99 | 仅限技能 7130100/7130130 |

**B. 连击数 -1 类：**

| Buff ID | BuffBase ID | editor_name | type | add_max |
|---------|------------|-------------|------|---------|
| 20450090 | 2045009 | 通用连击次数-1 | 2 | 99 | trigger=12, param1=-1 |

**C. 连击数翻倍：**

| Buff ID | BuffBase ID | editor_name | type | add_max | 参数说明 |
|---------|------------|-------------|------|---------|---------|
| 20450030 | 2045003 | 连击次数翻倍 | 1 | 99 | param1=100(百分比翻倍) |
| 20450031 | 2045003 | (被动版)连击翻倍 | 3 | 1 | base 同 2045003 |

**D. 连击数固定：**

| Buff ID | BuffBase ID | editor_name | type | add_max | 参数说明 |
|---------|------------|-------------|------|---------|---------|
| 20450100 | 2045010 | 连击数固定为3 | 3 | 2 | param1=2(固定到3), param4=1(固定模式) |
| 20920080 | 2092008 | (规则)连击固定为3 | 4 | 2 | base=20450100, count=3 |
| 20920140 | 2092014 | (规则)连击固定为2 | 4 | 2 | base=20450100, count=2 |

**E. 特定技能连击+N：**

| Buff ID | BuffBase ID | editor_name | type | add_max | 关联技能 |
|---------|------------|-------------|------|---------|---------|
| 20450110 | 2045011 | 特定技能连击+2 | 3 | 99 | 7140270 |
| 20450120 | 2045012 | 特定技能连击+2 | 3 | 99 | 7180340 |
| 20450130 | 2045013 | (被动)特定技能连击+2 | 4 | 1 | — |
| 20450140 | 2045014 | (被动)连击固定为3 | 4 | 1 | — |
| 20450150 | 2045015 | 孢子爆散连击数+1 | 3 | 99 | 7030450 |
| 20450160 | 2045016 | 聚盐连击数+1 | 3 | 99 | 7030500 |

**F. 条件触发连击：**

| Buff ID | BuffBase ID | editor_name | type | add_max | 触发条件 |
|---------|------------|-------------|------|---------|---------|
| 20170320 | 2017032 | 敌方每有1层毒效果，连击+1 | 3 | 1 | 每层中毒 |
| 20350300 | 2035030 | 每使用1次翼系技能，连击+1 | 3 | 1 | 翼系技能使用 |
| 20170700 | 2017070 | 回合结束连击数+1 | 4 | 1 | trigger=7(回合结束) |
| 29990910 | 2999091 | 敌方每有一层中毒，连击+1 | 3 | 1 | param1=20070010(中毒buff), param2=1(每层+1) |
| 20640620 | 2064062 | 动态修正连击 | 3 | 99 | 技能7140270，3层→+2连击 |
| 20640630 | 2064063 | 动态修正连击 | 3 | 99 | 技能7180340，3层→+2连击 |
| 20670080 | 2067008 | 朔夜伊芙连击+1 | 3 | 1 | base=20450110 |

**G. 新增buff91系列（中毒+连击变体）：**

| Buff ID | BuffBase IDs | 说明 |
|---------|-------------|------|
| 20910010 | [2091001, 2091009, 2091010] | 中毒层数关联连击（变体1） |
| 20910020 | [2091002] | 关联 buff 20940010/20940011 星陨 |
| 20910030 | [2091003] | 关联 buff 20010791 萌化→连击 |
| 20910040 | [2091004] | 关联 buff 20010791 萌化→连击变体 |
| 20910060 | [2091006] | 关联 buff 20010791 萌化→连击变体2 |

**H. 战斗规则类连击：**

| Buff ID | BuffBase ID | editor_name | type | add_max |
|---------|------------|-------------|------|---------|
| 43240 | 2045010 | 所有人连击数固定为3 | 4 | — |
| 43239 | — | 所有精灵技能连击数固定为2 | 4 | — |
| 43386 | — | 敌人连击数固定为2-领地试炼 | 4 | — |
| 46690 | — | 1号位置连击+1 | 4 | — |
| 46714 | — | 3号位置连击+1 | 4 | — |
| 46762 | — | 3号位置连击+30 | 4 | — |

**I. 其他战斗连击效果：**

| Buff ID | BuffBase ID | editor_name | type | add_max |
|---------|------------|-------------|------|---------|
| 20170570 | 2017057 | 虫系连击捆绑 | 3 | 99 |
| 20171930 | 2017193 | 地降低速度和连击 | 3 | 10 |
| 20172000 | 2017200 | 翼加连击 | 3 | 10 |
| 20172120 | 2017212 | 地降低速度和连击(兽花蕾) | 3 | 10 |
| 20172190 | 2017219 | 翼加连击(兽花蕾) | 3 | 10 |
| 20172460 | 2017246 | 连击捆绑(含中毒) | 3 | 10 |
| 20460160 | 2046016 | 应对成功强化连击 | 3 | 1 |
| 21070020 | 2107002 | 击败敌人后连击+2 | 3 | 1 |
| 21070050 | 2107005 | 若敌方本回合入场连击+1 | 3 | 1 |
| 45107 | — | 若敌方本回合入场则连击+2 | 3 | — |
| 45179 | — | 若敌方本回合入场则连击翻倍 | 3 | — |

#### 6.5.3 BuffBase 参数模式总结

BuffBase 中的 `buffbase_param` 数组结构（以 order=45 的连击类为例）：

```
param[0]: 连击数变化量 (1=+1, -1=-1, 2=+2, 100=翻倍)
param[1]: 关联技能ID (0=所有技能, 7140270=特定技能)
param[2]: 0 或 1 (条件标记)
param[3]: 0 或 1 (固定模式标记, 1=固定而非增减)
```

`client_trigger_type` 含义：
- `-1`: 无特殊触发
- `7`: 攻击时触发
- `9`: 应对成功时触发
- `11`: 计算伤害时触发
- `15`: 回合结束时触发

`trigger_type` 含义：
- `7`: 回合结束
- `12`: 技能施放时

### 6.6 已知约束

- `BattleComboSkillCast` 在 `proto_schema.json` 中有完整定义，field 8 = combo_index, field 9 = combo_count
- entry_type 30 目前未被 `_extract_1324_entry` 处理，需要新增分支
- 先天技能 S2 天赋 buff ID：20030370, 20170160, 20410080, 20420100, 20430060
- 中毒+连击 buff：29990910（param 关联中毒 buff 20070010）
- 连击基础 buff 修改器：2045001~2045016（order=45，定义了连击数的基本增减规则）
- 游戏数据来源：`P0pola/Roco-Kingdom-World-Data` 仓库 `Bin/BinDataCompressed/` 下的 `BUFF_CONF.json` 和 `BUFFBASE_CONF.json`

## 7. Success Metrics / 成功指标

- 伤害预测对连击技能的准确率：总伤害预测值与实际伤害的误差 < 20%（考虑随机因子）
- 缠丝劲案例：预测值应接近 143×7 = 1001，而非当前的 91
- 所有现有测试通过，新增测试覆盖先天技能 hook 和连击伤害计算

## 8. Open Questions / 待确认问题

1. 先天技能（宠物固定天赋）数据需要从哪些来源收集？`PET_TALENT_CONF.json` 中的天赋主要是世界探索类（采集、挖矿），非战斗类。战斗类先天技能可能通过 `PET_BLOOD_CONF.json`（血脉）或 `SKILL_RES_CONF.json`（技能效果）关联
2. 宠物到先天技能的映射关系已通过 `pet_species.pet_feature` 从 BinData 导入（818 个宠物），无需外部补充
3. 战斗回放 battle_session_1 是否包含连击/先天技能场景？如果不包含，是否需要录制新的战斗数据？
4. 连击伤害是否需要考虑每击独立随机因子（每击伤害可能不同），还是统一按同一伤害计算？
