# NRC_AI 参考

详细参考文档已从 CLAUDE.md 提取。

本地路径：`references/NRC_AI/`

洛克王国战斗 AI 模拟器 — 基于蒙特卡洛树搜索（MCTS）的自动对战模拟系统。最核心的价值在于其**效果引擎**（Effect Engine），对 100+ 种战斗效果原语做了完整的数据驱动实现。关键领域：
- **效果引擎**：`src/effect_engine.py`（Handler 注册表，执行效果原语）、`src/effect_models.py`（`E` 枚举：100+ 效果原语类型定义）、`src/effect_data.py`（59 个手工配置技能效果 + 68 个特性效果配置）
- **自动生成效果**：`src/skill_effects_generated.py`（455 个自动生成的技能效果配置）
- **战斗逻辑**：`src/battle.py`（回合流程、印记系统、状态管理）
- **数据模型**：`src/models.py`（Pokemon / Skill / BattleState 数据模型）、`src/effect_models.py`（Timing / SkillTiming 触发时机定义）
- **数据**：`data/nrc.db`（SQLite: 461 精灵 × 495 技能）、`scripts/`（爬虫 / 效果生成器 / 审计工具）
- **文档**：`docs/COVERAGE_MATRIX.md`（特性覆盖矩阵）、`docs/SKILLS_ABILITIES_CONFIG_GUIDE.md`（配置开发手册）

**何时参考此仓库：**
- 实现或扩展 `innate_hooks.py` 中的天赋/特性伤害修改逻辑时，参考 NRC_AI 的 `effect_data.py` 和 `effect_models.py` 了解特定效果原语的参数格式和行为定义
- 需要理解 buff/debuff/印记/状态的精确交互机制时（如层数叠加、触发时机、覆盖规则），参考 `effect_engine.py` 中的 Handler 实现和 `battle.py` 中的印记系统
- 扩展伤害计算管线（`damage_calc.py` 的 hook stages）时，参考 NRC_AI 的效果分类体系确认哪些效果属于威力修改、哪些属于最终伤害修改
- 验证技能效果的正确性时，用 `skill_effects_generated.py` 和 `effect_data.py` 交叉比对
- 需要查找宠物基础数值或技能数据库时，参考 `data/nrc.db` 和 `src/pokemon_db.py` / `src/skill_db.py`
