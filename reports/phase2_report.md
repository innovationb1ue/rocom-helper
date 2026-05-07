# Phase 2-3 报告：游戏逻辑 + PvP 分析引擎

## 概述

Phase 2 完成了属性克制系统、种族值计算、技能评分模块。Phase 3 完成了覆盖度分析、队伍构建器、反制推荐、威胁评估、实时战斗状态追踪器。

## 新增模块

### src/game/type_chart.py — 属性克制计算器

| 符号 | 说明 |
|------|------|
| `TypeChart` | 主类，加载 `data/game/type_chart.json` |
| `get_multiplier(atk, defend_types)` | 计算攻击属性对防御方（可能双属性）的倍率 |
| `get_effectiveness_label(multiplier)` | 倍率 → 中文标签 |
| `get_weaknesses(defend_types)` | 所有对防御方克制的属性及倍率 |
| `get_resistances(defend_types)` | 所有对防御方抵抗的属性及倍率 |
| `get_immunities(defend_types)` | 免疫的属性列表 |
| `get_coverage(attack_types)` | 给定攻击属性组，对每个防御类型的最佳倍率 |
| `offensive_coverage_score(attack_types)` | 进攻覆盖度评分 (0-100) |
| `defensive_rating(defend_types)` | 防守评分 (0-100) |

### data/game/type_chart.json — 21 种属性克制矩阵

- 18 种常规属性 + 3 种神属性
- 21×21 克制关系表，仅存储非 1.0 的条目
- 包含：火→草(2x), 水→火(2x), 草→水(2x), 电→地面(0x), 幽灵→普通(0x) 等
- 神属性：对常规 1.5x，循环克制 2x（神火→神草→神水→神火）
- 光属性：对所有属性 1.0x（无克制关系）

### src/game/stats.py — 种族值/能力值计算

| 符号 | 说明 |
|------|------|
| `calc_hp(base, iv, ev, level)` | HP 公式 |
| `calc_stat(base, iv, ev, level, nature_modifier)` | 非HP属性公式 |
| `get_nature_modifier(nature, stat_index)` | 性格修正值 |
| `calc_all_stats(bases, ivs, evs, level, nature)` | 一次性计算所有属性 |
| `normalize_stat(value, max_value)` | 归一化到 0-100 |
| `NATURE_EFFECTS` | 20 种性格修正表 |

### src/game/skill_eval.py — 技能评分系统

| 符号 | 说明 |
|------|------|
| `score_skill(skill, type_chart)` | 综合评分 (0-100)，6 因子加权 |
| `rank_skills(skills, type_chart)` | 技能列表打分并排序 |

评分因子: 威力(30%) + 能量效率(20%) + 命中率(15%) + PP(10%) + 属性覆盖(15%) + 效果(10%)

### src/analysis/coverage.py — 属性覆盖度分析

| 符号 | 说明 |
|------|------|
| `CoverageAnalyzer` | 覆盖度分析器 |
| `offensive_coverage(team_pets)` | 进攻覆盖度：对每种防御属性的最佳倍率 |
| `defensive_coverage(team_pets)` | 防守弱点：被克制的精灵列表 |
| `coverage_score(team_pets)` | 综合覆盖度评分 (0-100) |
| `uncovered_types(team_pets)` | 缺少覆盖的属性列表 |
| `shared_weaknesses(team_pets)` | 全队共同弱点 |

### src/analysis/team_builder.py — 队伍分析和推荐

| 符号 | 说明 |
|------|------|
| `TeamBuilder` | 队伍构建器 |
| `analyze_team(pets)` | 综合分析（评分+覆盖+角色+速度线+建议） |
| `suggest_teammates(core_pets, pool)` | 从精灵池推荐队友 |

### src/analysis/counter.py — 反制推荐引擎

| 符号 | 说明 |
|------|------|
| `CounterPicker` | 反制选择器 |
| `find_counters(opponent_team, my_pool)` | 找出最佳反制精灵 |
| `find_counter_skills(my_pet, opponent_pet)` | 找出最有效的技能 |

### src/analysis/threat.py — 威胁评估

| 符号 | 说明 |
|------|------|
| `ThreatAssessor` | 威胁评估器 |
| `assess_threats(opponent_team, my_team)` | 威胁等级评估 |
| `suggest_target_order(opponent_team, my_active)` | 建议击杀顺序 |

### src/analysis/battle_state.py — 实时战斗状态追踪器

| 符号 | 说明 |
|------|------|
| `BattleStateTracker` | 战斗状态追踪器 |
| `handle_event(opcode, detail)` | 处理协议事件，更新状态 |
| `get_state()` | 获取当前状态快照 |
| `get_suggestions()` | 基于状态给出实时建议 |

支持的 opcode: 0x1316(进入), 0x131A(回合), 0x1324(动作), 0x132C(结束), 0x130B(选技), 0x13F4(刷新), 0x1322(声明), 0x1312(回合流)

## 测试结果

```
177 passed in 6.56s
```

| 测试文件 | 测试数 | 说明 |
|----------|--------|------|
| test_frame.py | 16 | BE21 帧解析 |
| test_crypto.py | 15 | AES 解密 |
| test_loader.py | 23 | 数据加载器 |
| test_type_chart.py | 50 | 属性克制：单属性/双属性/神属性/光属性/弱点/抗性/免疫/覆盖/标签 |
| test_stats.py | 21 | 种族值：HP/属性计算/性格修正/归一化 |
| test_skill_eval.py | 8 | 技能评分：基础/威力对比/效果/排序 |
| test_coverage.py | 13 | 覆盖度：进攻/防守/评分/未覆盖/共同弱点 |
| test_counter.py | 9 | 反制推荐：排序/克制/技能选择 |
| test_team_builder.py | 9 | 队伍分析：评分/覆盖/角色/队友推荐 |
| test_battle_state.py | 13 | 战斗状态：初始化/伤害/技能/击败/结束/完整流程/建议 |

所有测试使用真实数据，不使用 mock。
