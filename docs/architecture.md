# 架构说明

本文档记录后端核心模块边界和允许的依赖方向。目标是让实时抓包、无头回放和前端展示共用同一套战斗语义与分析管线。

## 分层主线

```text
capture -> protocol -> analysis -> api -> web
              ^           ^
              |           |
          data/game/config
```

- `src/capture/`：只负责网络流量、TCP 重组、BE21 帧、解密和抓包记录，不承担战斗业务判断。
- `src/protocol/`：把 TGCP/Protobuf 记录转换为 opcode 语义 detail。`protocol.battle` 是兼容门面，内部 helper 负责 schema/raw fallback 与通用行动提取。
- `src/analysis/`：消费 opcode detail，维护战斗状态、格式化事件、伤害预测、hook 建议和战术推荐。实时路径与回放路径都从 `BattleProcessor` 进入。
- `src/api/`：只做 FastAPI/WebSocket 编排、sniffer 生命周期和 replay service，不直接承载协议语义。
- `web/`：消费 API/WebSocket 消息并展示，不反向编码协议解析规则。

## 依赖规则

- 允许：`capture -> protocol`、`analysis -> protocol/data/game`、`api -> analysis/capture`、`web -> api contract`。
- 禁止：`protocol -> analysis/api`、`data -> analysis/api`、`game -> analysis/api`。
- `src.data.loader` 是兼容门面；新增数据领域逻辑应优先放入 `src/data/*` 内部模块，再由 loader re-export。
- 使用 `py -m scripts.check_architecture` 或 `pytest tests/test_architecture.py -v` 检查 import cycle 和禁止依赖边。

## 实时与回放共享路径

- 实时抓包：`SnifferManager -> BattleManager -> BattleProcessor -> build_battle_messages -> WebSocket`。
- 无头回放：`BattleReplayRunner -> BattleProcessor -> ReplayResult`。
- API fixture 回放：`routes_battle -> replay_service -> BattleManager -> BattleProcessor`。

三条路径都应保持相同的 opcode detail 和状态更新语义。新增战斗行为时，优先在 `BattleProcessor`/`BattleStateTracker`/`event_formatter`/hook 中实现一次，再由实时和回放复用。

## 兼容门面

- `src.protocol.battle` 保留现有 `extract_*` 函数名；内部可继续拆分到 `battle_schema.py`、`battle_actions.py` 和后续 opcode 子模块。
- `src.analysis.battle_state.BattleStateTracker` 保留状态 dict 形状；纯工具放在 `state_helpers.py`。
- `src.analysis.tactical_engine.TacticalEngine` 保留 `recommend(state)`；展示文案和分类规则放在 `analysis/tactical/`。
- `src.data.loader` 保留旧导入路径；基础 catalog 缓存已拆到 `data/catalog.py`。

## WebSocket 消息契约

`/ws/battle` 继续推送以下兼容消息：

- `connected`
- `state_update`
- `battle_event` / `battle_events`
- `battle_summary`
- `skill_analysis`
- `hook_advice`
- `suggestions`
- `tactical_recommendations`

新增字段应保持可选和向后兼容；不要替换现有字段含义。前端类型说明位于 `web/src/types/battle.ts`。
