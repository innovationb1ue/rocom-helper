# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Roco PvP Helper (洛克王国 PvP 辅助工具) — a real-time battle analysis and suggestion tool for Roco Kingdom PvP. It passively monitors game network traffic on port 8195, decrypts the custom BE21 protocol, tracks live battle state, and provides actionable suggestions (type counters, threat assessment, team composition) during PvP battles. The tool is purely passive — it only reads traffic, never sends packets to the game.

## Tech Stack

- **Backend**: Python 3.9+, FastAPI, Scapy, PyCryptodome, uvicorn
- **Python launcher**: Use `py` (not `python`) to run Python on Windows — `python` is not on PATH
- **Frontend**: React 19, TypeScript, Ant Design 6, Zustand, Vite 8, React Router 7
- **Protocol**: Custom BE21 binary framing with AES-128-CBC encryption, protobuf-like message payloads

## Commands

### Backend
```bash
py -m src.main                   # Start FastAPI server on :8000 (with hot reload)
pytest                          # Run all tests
pytest tests/test_crypto.py     # Run a single test file
pytest -k "test_name"           # Run tests matching a name pattern
```

### Headless Replay (后端自闭环)
```bash
py -m scripts.replay_headless --session battle_session_1       # Text summary with events, predictions, hooks
py -m scripts.replay_headless --session battle_session_1 --json  # Full JSON output (written to tmp/)
py -m scripts.replay_headless --round 7                        # Stop at round 7
py -m scripts.generate_battle_report --json                    # Generate report file (docs/battle_report.txt)
py -m scripts.replay_to_frontend --delay 80 --session battle_session_1  # Push replay to WebSocket frontend
py -m scripts.replay_to_frontend --delay 80 --session battle_session_1 --round 7  # Replay to round 7
```

### Frontend (from `web/`)
```bash
npm run dev                     # Vite dev server on :5173
npm run build                   # TypeScript compile + Vite production build
npm run lint                    # ESLint
```

## Development Workflow

**Mandatory after every development task** — complete all steps in order:

### 1. Run Full Test Suite
```bash
pytest
```
All tests must pass before proceeding. Fix any failures before moving on.

### 2. Start Backend & Frontend
```bash
# Terminal 1 — Backend
py -m src.main

# Terminal 2 — Frontend
cd web && npm run dev
```

### 3. MCP Battle Replay Verification (完整的前后端回放验证)

当要求进行"完整的前后端回放验证"时，必须使用 MCP Chrome DevTools 工具进行自动化验证，而非手动操作浏览器。

**步骤：**

1. **导航到战斗页面** — 使用 `mcp__chrome-devtools__navigate_page` 打开 `http://localhost:5173/battle`
2. **建立 WebSocket 连接** — 使用 `mcp__chrome-devtools__take_snapshot` 获取页面快照，找到"连接战斗"按钮的 uid，使用 `mcp__chrome-devtools__click` 点击连接
3. **确认连接成功** — 使用 `mcp__chrome-devtools__take_snapshot` 验证连接状态（如按钮文本变化或状态提示）
4. **运行回放脚本** — 使用 Bash 后台运行：
   ```bash
   # 完整回放
   py -m scripts.replay_to_frontend --delay 80 --session battle_session_1

   # 回放到指定回合（如 R7）停止，用于测试中间状态
   py -m scripts.replay_to_frontend --delay 80 --session battle_session_1 --round 7
   ```
5. **等待回放完成** — 等待脚本执行完毕后，再等待 10 秒缓冲，确保前端完成所有渲染
6. **截图检查页面状态** — 使用 `mcp__chrome-devtools__take_screenshot` 截取页面截图，观察：
   - HP、能量、buff 状态更新是否正确
   - 宠物切换是否正确显示
   - 战斗事件时间线是否正常渲染
   - 属性克制和 counter-pick 建议是否正确显示
7. **检查浏览器日志** — 使用 `mcp__chrome-devtools__list_console_messages` 检查是否有 JS 错误或异常
8. **检查后端日志** — 查看后端控制台输出是否有异常或报错
9. **汇报结果** — 总结验证结果，如有问题则定位并修复

如果发现任何异常，必须调查并修复后才能标记任务完成。

### 4. Screenshot Cleanup

**Always delete screenshot files immediately after reviewing them.** When taking screenshots (via MCP `take_screenshot` or any other method), delete the file as soon as you've analyzed it. Never leave `.png`/`.jpg`/`.jpeg` screenshot files lingering in the project directory. This applies to both main agent and subagent usage.

### 5. Headless Replay Verification (后端自闭环回放验证)

当要求进行"后端自闭环验证"时，使用 `BattleReplayRunner` 进行纯后端验证，无需启动服务器或前端。

**步骤：**

1. **运行 headless replay** — 使用 Bash 运行：
   ```bash
   py -m scripts.replay_headless --session battle_session_1
   ```
2. **检查输出完整性** — 验证输出包含：
   - 每回合的格式化事件（skill_cast, damage, defeat, effect_apply 等）
   - 每回合的伤害预测（技能名称、预期伤害、效果标签、KO 标记）
   - 建议（低血量、低能量、击杀提示等）
   - Hook 建议（换宠建议、能量监控、对手行为分析）
   - 最终状态（双方阵容 HP）
3. **运行 JSON 输出对比** — 使用 `--json` 生成结构化数据进行字段级验证
4. **运行相关测试** — `pytest tests/test_replay_runner.py -v` 确保所有回放测试通过

## Architecture

The system is a layered pipeline with clear boundaries between capture, parsing, analysis, and presentation:

```
Network Traffic (port 8195)
  │
  ▼
capture/sniffer.py ── Scapy AsyncSniffer, orchestrates the pipeline
  │
  ├── capture/key_capture.py ── Extract AES session key from ACK packets
  ├── capture/reassembly.py ── TCP stream reassembly into ordered flows
  ├── capture/frame.py ── BE21 frame parsing (header + body extraction)
  ├── capture/crypto.py ── AES-128-CBC decryption of encrypted bodies
  │
  ▼
protocol/
  ├── proto_core.py ── Protobuf parser, TGCP transport (4 formats), creature/state extraction, game constants
  ├── opcodes.py ── Decorator-based opcode/inner-message registry with dispatch
  ├── battle.py ── Battle-specific extraction (dual: schema-first + raw field fallback)
  │
  ▼
analysis/
  ├── constants.py ── Shared opcode constants, OPCODE_LABELS, SDT_TO_TYPE re-export (single source of truth)
  ├── pet_info.py ── PetInfo construction factory (from_wrapper/from_change_pet → to_dict), unifies pet dict construction
  ├── battle_state.py ── Real-time battle state machine (HP, energy, buffs, turn tracking)
  ├── battle_processor.py ── Pure sync event processor (state + formatting + damage + hooks), shared by BattleManager and ReplayRunner
  ├── battle_advisor.py ── Battle analysis coordinator (skill analysis + damage prediction + state suggestions)
  ├── damage_calc.py ── Damage calculation engine with 4-stage hook pipeline
  ├── innate_hooks.py ── Innate skill damage hooks (combo/stat/type/power modifications)
  ├── event_formatter.py ── Protocol events → UI-ready formatted events
  ├── replay_runner.py ── Headless replay runner (no FastAPI/WebSocket), produces ReplayResult with per-event snapshots
  ├── hook_registry.py ── Extensible analysis hook system (ABC-based, lifecycle-aware)
  ├── hooks/
  │   ├── __init__.py ── Default hook factory
  │   ├── opponent_tracker.py ── Opponent skill/switch pattern tracking
  │   ├── energy_monitor.py ── Energy monitoring with attack window detection
  │   └── switch_advisor.py ── Type-based switch recommendations
  ├── coverage.py ── Offensive/defensive type coverage calculation
  ├── counter.py ── Counter-pick logic based on type matchups
  ├── threat.py ── Threat assessment for opponent pets
  ├── team_builder.py ── Team composition suggestions
  │
  ▼
game/
  ├── type_chart.py ── TypeChart class: 18-type effectiveness matrix, weakness/resistance queries, coverage scores
  ├── stats.py ── Base stat calculator (HP + 5 stat formulas), nature modifiers, stat ratings
  ├── skill_eval.py ── Skill scoring engine (power, efficiency, accuracy, PP, type coverage, effects)
  │
  ▼
api/ (FastAPI)
  ├── app.py ── Application factory (create_app), CORS, router mounting
  ├── battle_manager.py ── Global singleton: sniffer bridge, WS push, hook dispatch
  ├── sniffer_manager.py ── Packet capture session management
  ├── routes_battle.py ── WebSocket (/ws/battle) + REST + replay endpoints
  ├── routes_sniffer.py ── Packet capture control API
  ├── routes_teams.py ── Team analysis endpoints
  ├── routes_pets.py ── Pet data queries
  ├── routes_data.py ── Static game data serving
  │
  ▼
web/ (React SPA)
  ├── stores/ ── Zustand stores (battleStore, snifferStore, petsStore)
  ├── hooks/ ── useBattle (WebSocket), usePets (REST), useSnifferMonitor
  ├── pages/ ── Dashboard, PetBrowser, TeamBuilder, TypeChart, BattleLive, BattleHistory
  ├── components/ ── PetCard, TeamSlot, TypeBadge, BattleTimeline, BattleEventLog,
  │                  DamagePredictionPanel, SkillPanel, HookAdvicePanel,
  │                  BattleSummaryPanel, TeamRoster, CoverageRadar
```

### Data Files

Static game data lives in `data/game/` as JSON files (~24MB total). Key files:

**Core databases:**
- `pet_map.json` (706K) — Pet definitions (ID, name, base stats, types)
- `skill_map.json` (1.2M) — Skill definitions (power, element, energy cost, target type)
- `pet_skill_map.json` — Pet-to-skill mapping (which skills each pet can learn)
- `type_chart.json` (2.8K) — 18-type effectiveness matrix
- `attr_map.json` (12K) — Attribute/type name lookup

**Protocol and schemas:**
- `proto_schema.json` (3.1M) — Protobuf message schema definitions
- `opcode_pb_map.json` (315K) — Opcode-to-protobuf-message mapping
- `pb_message_index.json` (1.8M) — Protobuf message name index

**Battle data:**
- `innate_skills.json` (4.5K) — Innate skill definitions for the damage hook system
- `buff_map.json` (891K) — Buff/effect definitions (IDs, names, descriptions)
- `buffbase_map.json` (1.1M) — Base buff definitions

**Monster and wiki data:**
- `monster_map.json` (7.3M) — In-game monster ID mapping
- `wiki_pets.json` (217K) — Wiki-sourced pet data (fallback stats)
- `wiki_skills.json` (90K) — Wiki-sourced skill data
- `special_move_map.json` (86K) — Special move definitions

The `src/data/loader.py` module provides typed access to this data; `src/data/scraper.py` and `src/data/updater.py` handle scraping from game wikis.

### Key Design Patterns

- **Backend entry point**: `src/main.py` runs uvicorn with `src.api.app:app` (factory pattern via `create_app()`)
- **Route registration**: All routers are mounted in `app.py` with `/api` prefix (except battle WebSocket at root)
- **CORS**: Allowed origins are `localhost:5173` and `127.0.0.1:5173` (Vite dev server)
- **State management**: Zustand stores on frontend; WebSocket for battle state, REST for pet/team data
- **API client**: `web/src/utils/api.ts` centralizes Axios calls to the backend
- **Battle manager singleton**: `get_battle_manager()` provides global access to `BattleManager`, which bridges the packet sniffer to WebSocket clients and the analysis pipeline
- **Opcode dispatch**: `opcodes.py` uses decorator registries (`_OPCODE_REGISTRY` for main opcodes, `_INNER_REGISTRY` for inner-message dispatch on opcode 0x0414). The `summarize()` function falls back to `opcode_pb_map.json` metadata for unknown opcodes.
- **Opcode constants**: `src/analysis/constants.py` centralizes all opcode constants (`OPCODE_BATTLE_ENTER`, `OPCODE_ACTION_RESOLVE`, etc.), opcode sets (`LIFECYCLE_OPCODES`, `DAMAGE_OPCODES`, `IN_BATTLE_OPCODES`), `OPCODE_LABELS`, and re-exports `SDT_TO_TYPE`. All analysis and API modules import from this file instead of using hex literals.

### Key Architectural Concepts

**Dual Hook Systems:**

The project has two separate hook systems serving different purposes:

1. **Damage Calculation Hooks** (`damage_calc.py`) — A 4-stage pipeline within `DamageCalculator` that modifies damage computation:
   - `pre_power` — Modify skill power before calculation
   - `post_base` — Modify base damage after core formula
   - `pre_final` — Modify effectiveness/STAB before final multiplication
   - `post_calc` — Modify final damage values, hit counts
   - Innate skill hooks (`innate_hooks.py`) use this system: `stat_modify_hook` (post_base), `type_resist_modify_hook` (pre_final), `combo_modify_hook` and `power_modify_hook` (post_calc).

2. **Analysis Hook System** (`hook_registry.py`) — An ABC-based event-driven hook system triggered by battle lifecycle events:
   - Triggers: `ON_BATTLE_ENTER`, `ON_ROUND_START`, `ON_ACTION_RESOLVE`, `ON_SPECIAL_REFRESH`, `ON_BATTLE_FINISH`, `ON_CHANGE_PET`, `ON_DEFEAT`
   - Hooks implement `AnalysisHook` ABC and return `HookAdvice` dataclass
   - Default hooks: `OpponentTrackerHook`, `EnergyMonitorHook`, `SwitchAdvisorHook`

**Note:** `register_innate_hooks()` is called automatically by `BattleAdvisor`, so damage analysis triggered via `BattleManager` has innate hooks active. However, if `DamageCalculator` is instantiated directly (e.g., in tests or standalone scripts), `register_innate_hooks()` must be called explicitly for innate skill effects to apply.

**Dual Extraction Strategy (battle.py):**

All major extractors in `battle.py` use a dual approach:
1. **Schema-first**: Decode via `proto_schema.json` definitions for structured, type-safe access
2. **Raw fallback**: Manual protobuf field parsing when schema data is unavailable

Both paths produce the same output shape. The `_schema_quality()` helper tags each result with `parse_quality`.

**Battle Lifecycle:**

```
idle → selecting (0x1316 battle_enter) → resolving (0x131A round_start)
  → [action events: 0x1324, 0x130C, 0x13F4, ...]
  → [repeat per round]
  → finished (0x132C battle_finish)
```

**WebSocket Message Types:**

The `/ws/battle` endpoint pushes these message types to connected clients:
- `connected` — Initial connection confirmation
- `state_update` — Full battle state snapshot after every event
- `battle_event` / `battle_events` — Formatted battle event(s) for timeline
- `battle_summary` — End-of-battle summary (computed at 0x132C)
- `skill_analysis` — Damage prediction for all equipped skills (with optional `traits`)
- `hook_advice` — Analysis hook recommendations (energy, switches, opponent patterns)
- `suggestions` — Simple rule-based suggestions (low HP, low energy, etc.)

**Sniffer Bridge:**

`BattleManager` registers a callback with `SnifferManager` via `_ensure_bridge()`. When the sniffer captures a TGCP DATA packet, the bridge decodes the opcode and dispatches it through the full pipeline (tracker → formatter → analysis → WebSocket push). Only `_LIFECYCLE_OPCODES` (0x1316, 0x131A, 0x132C, 0x0102) and `_IN_BATTLE_OPCODES` are processed.

## Testing

Tests live in `tests/` and mirror the module structure. The suite contains **640+ tests** across ~30 test files. Key test areas:

- **Protocol parsing**: `test_opcodes.py`, `test_frame.py`, `test_crypto.py`, `test_skill_extraction.py`, `test_type_extraction.py`
- **Game mechanics**: `test_type_chart.py` (50 tests), `test_stats.py` (21 tests), `test_skill_eval.py` (8 tests)
- **Battle state**: `test_battle_state.py`, `test_event_formatter.py`, `test_battle_replay.py`
- **Damage calculation**: `test_damage_calc.py`, `test_innate_hooks.py` (24 tests), `test_innate_integration.py` (17 end-to-end tests)
- **Analysis hooks**: `test_hook_registry.py`, `test_hook_opponent_tracker.py`, `test_hook_energy_monitor.py`, `test_hook_switch_advisor.py`
- **Strategy**: `test_counter.py`, `test_coverage.py`, `test_team_builder.py`, `test_threat.py`
- **API**: `test_api.py`, `test_replay_api.py`, `test_battle_advisor.py`, `test_battle_advisor_integration.py`
- **Data**: `test_loader.py`

Test fixtures are in `tests/fixtures/` (including `packets/battle_session_1/` and `packets/battle_session_2/` for replay testing). All tests use real data, not mocks.

### Headless Testing Data Structures

The `BattleReplayRunner` produces structured output via three dataclasses. Understanding these is essential for writing analysis tests:

**`ReplayResult`** (top-level, from `src/analysis/replay_runner.py`):
```python
@dataclass
class ReplayResult:
    total_packets: int                           # Events processed
    events: List[ReplayEventSnapshot]            # Flat per-event snapshots
    rounds: List[RoundSnapshot]                  # Per-round aggregation
    final_state: Dict[str, Any]                  # Final BattleStateTracker state
    battle_summary: Dict[str, Any]               # From compute_battle_summary()
    stopped_early: bool                          # Whether stop_round triggered
```

**`RoundSnapshot`** (per-round aggregation):
- `round_num`, `state_at_start`, `state_at_end`
- `damage_predictions` — List of per-skill damage prediction dicts
- `formatted_events` — Aggregated UI-ready event dicts (kind/summary/icon/color)
- `suggestions` — Aggregated suggestion dicts (type/message)

**`ReplayEventSnapshot`** (per-event, most granular):
- `opcode`, `kind`, `round_num`
- `state_before`, `state_after` — Battle state before/after this event
- `battle_advice` — Dict with `skill_analysis` (damage predictions) and `opp_traits`
- `hook_advice` — List of dicts (hook_id/title/priority/messages)
- `suggestions` — List of dicts (type/message)

**`ProcessResult`** (from `BattleProcessor.process_event()`):
- `state` — Updated battle state dict
- `formatted_events` — List of FormattedEvent
- `battle_advice` — Skill analysis dict (or None)
- `hook_advice` — List of hook advice dicts
- `suggestions` — List of suggestion dicts

**`battle_advice` dict structure** (when present):
- `skill_analysis` — List of dicts per skill: `skill_name`, `expected_damage`, `can_ko`, `effectiveness`, `effectiveness_label`, `energy_cost`, `hit_count`, `damage_breakdown`, `warnings`
- `opp_traits` — List of detected opponent innate traits

**`hook_advice` dict structure** (each entry):
- `hook_id` — e.g., `"opponent_tracker"`, `"energy_monitor"`, `"switch_advisor"`
- `priority` — 0=urgent, 1=important, 2=info
- `title` — Human-readable title
- `messages` — List of dicts with `message` key

### Analysis Test Patterns

**Pattern 1: Full replay integration test** (tests the entire pipeline with real packets):
```python
from tests.packet_reader import load_battle_packets
from src.analysis.replay_runner import BattleReplayRunner

packets = load_battle_packets("tests/fixtures/packets/battle_session_1")
runner = BattleReplayRunner()
result = runner.run(packets)

# Assertions on final state
assert result.final_state["round"] == 17
assert result.final_state["result"] == "WIN_HP"
# Assertions on per-round predictions
for rs in result.rounds:
    if rs.damage_predictions:
        for pred in rs.damage_predictions:
            assert "expected_damage" in pred
            assert "can_ko" in pred
```

**Pattern 2: Single-event processor test** (tests BattleProcessor with constructed events):
```python
from src.analysis.battle_processor import BattleProcessor

processor = BattleProcessor()
pr = processor.process_event(0x1316, battle_enter_detail)
assert len(pr.state["my_pets"]) == 6
assert pr.formatted_events  # Should produce at least one event
```

**Pattern 3: State tracker unit test** (tests state transitions step by step):
```python
from src.analysis.battle_state import BattleStateTracker

tracker = BattleStateTracker()
tracker.handle_event(0x1316, battle_enter_detail)
state = tracker.get_state()
assert state["phase"] == "selecting"
assert state["my_active"] is not None
```

**Pattern 4: Targeted stop-round test** (tests intermediate battle states):
```python
runner = BattleReplayRunner()
result = runner.run(packets, stop_round=5)
assert result.stopped_early is True
# Check state at round 5
round5 = result.rounds[-1]
assert round5.round_num == 5
```

**Pattern 5: Flag-based selective testing** (disable expensive computations):
```python
runner = BattleReplayRunner(include_analysis=False, include_hooks=False)
result = runner.run(packets)  # Only state tracking, no damage/hook computation
assert result.final_state is not None
assert all(rs.battle_advice is None for rs in result.rounds)
```

### Headless Replay CLI Output Guide

`replay_headless` text output structure (one section per round):
```
=== Round N ===
  My: {name} HP {cur}/{max} Energy {n}  |  Opp: {name} HP {cur}/{max}
  [kind] summary text                    ← formatted events
  SUGGEST: [type] message                ← suggestions
  {skill_name}  dmg: {n} range: [{min}-{max}] eff: {label} [KO]  ← damage predictions
  HOOK: [hook_id] title                  ← hook advice
    - message text
```

JSON output (`--json`, written to `tmp/`): structured `ReplayResult` serialization with all fields above.

## Reference Repositories

These external repositories are useful references for protocol parsing and game data:

All reference repos are cloned locally under `references/`.

### Roco-Kingdom-Protocol-Parser (RKPP)

Local path: `references/Roco-Kingdom-Protocol-Parser/`

洛克王国战斗协议解析器 — the primary reference for battle protocol parsing. Key areas of overlap:
- **Protocol parsing**: `rkpp_proto_core.py` (proto-tree parsing), `rkpp_proto_battle.py` (battle semantics) — mirrors our `protocol/proto_core.py` and `protocol/battle.py`
- **Network layer**: `rkpp_network.py` (TCP reassembly, BE21 framing, AES-CBC decryption, key extraction) — mirrors our `capture/` modules
- **Battle analysis**: `rkpp_analysis.py` (schema-driven field decoding), `rkpp_reporter.py` (battle summaries) — mirrors our `analysis/battle_state.py`
- **Data**: `Data.py` / `Data/` — runtime data access and offline index data
- **Server doc**: `Server.md` — server protocol documentation

Use this repo to cross-reference opcode meanings, protobuf field structures, battle state transitions, and any protocol details not yet covered in our implementation.

### Roco-Kingdom-World-Data

Local path: `references/Roco-Kingdom-World-Data/`

洛克王国游戏完整解包数据 — 游戏本地所有配置的真实数据源，包含 676 个 JSON 配置文件 + 64 个 protobuf 定义文件。所有 JSON 统一结构为 `{"RocoDataRows": {"ID": {...}}}`。

#### PvP 核心数据（按重要性排列）

**宠物与种族值：**
- `Bin/BinDataCompressed/PETBASE_CONF.json` (4.3M) — **最关键的宠物数据**：种族值（`hp_max_race`/`phy_attack_race`/`spe_attack_race`/`phy_defence_race`/`spe_defence_race`/`speed_race`/`SUM_race`）、属性类型（`unit_type`）、品质（`quality`）、进化链 ID、天赋概率（`talent_normal_chance`/`talent_good_chance`/`talent_amazing_chance`/`talent_perfect_chance`）、暴击倍率（`critical_dam`，20000=200%）、性格池（`nature_ids`）
- `Bin/BinDataCompressed/PET_CONF.json` (800K) — 宠物实例配置，`base_id` 链接到 PETBASE_CONF
- `Bin/BinDataCompressed/MONSTER_CONF.json` (11M) — NPC/怪物配置：等级、难度、个体值（`individuality`）、性格（`nature_id`）、AI 行为树
- `Bin/BinDataCompressed/PET_EVOLUTION_CONF.json` (240K) — 完整进化链：`evolution_chain` 数组包含各阶段 petbase_id、名称、等级要求；`pvp_mute_group` 标记 PvP 中视为同组的进化链
- `Bin/BinDataCompressed/NATURE_CONF.json` — 性格系统：`positive_effect`(80=物攻 81=物防 82=特攻 83=特防 84=特防 85=速度)、`positive_effect_proportion`(1000=+10%)、`negative_effect`、`negative_effect_proportion`

**技能系统：**
- `Bin/BinDataCompressed/SKILL_CONF.json` (1.6M) — **技能权威定义**：`energy_cost`（能量消耗）、`dam_para`（威力参数）、`type`（技能类型，2=被动）、`skill_dam_type`（伤害类型）、`damage_type`（物/特）、`skill_priority`（优先度）、`target_type`（目标类型）、`cd_round`（冷却回合）、`hit_para`（命中率，10000=100%）、`skill_result`（效果数组，含 `effect_id`/`success_rate`/`cast_moment`/`result_target_type`/`buff_group_level`）
- `Bin/BinDataCompressed/LEVEL_SKILL_CONF.json` (2.4M) — 等级技能学习表
- `Bin/BinDataCompressed/MONSTER_SKILLBANK_CONF.json` (6.3M) — 怪物技能库
- `Bin/BinDataCompressed/SPECIAL_MOVE_CONF.json` (1.2M) — 特殊招式定义
- `Bin/BinDataCompressed/SKILL_TIME_CONF.json` (560K) — 技能时间配置

**属性克制：**
- `Bin/BinDataCompressed/TYPE_DICTIONARY.json` — **属性克制权威数据**：`type_restraint{N}` 字段（N=目标属性 ID，1=克制，-1=被克制）、`type_name`（属性名）、`short_name`（简称）、`type_immunity`（免疫 buff ID 列表）。共 18+ 种属性

**Buff/效果系统：**
- `Bin/BinDataCompressed/BUFF_CONF.json` (1.2M) — buff 定义：`buff_base_ids`（关联 BUFFBASE）、`buff_groupsigns`（分组标记，同组互斥）、`buff_list_priority`（优先级）、`add_max`（叠加上限）、`is_clean_when_rest`（休息时清除）、`connect_buff`/`field_buff`（联动 buff）
- `Bin/BinDataCompressed/BUFFBASE_CONF.json` (1.3M) — buff 基础定义：`editor_name`（如"物攻等级提升10"）、`buffbase_param[].params`（数值参数，如 [29, 0, 1000] = 100%物理攻击提升）

**战斗与 PvP 配置：**
- `Bin/BinDataCompressed/BATTLE_CONF.json` (4.7M) — 战斗配置：队伍人数（`challanger_unit_num`/`bechallanger_unit_num`）、回合限制（`max_round`）、超时设置、可逃跑/可换宠/可捕捉标志
- `Bin/BinDataCompressed/BATTLE_RULE_CONF.json` — 战斗规则
- `Bin/BinDataCompressed/BATTLE_TYPE_CONF.json` — 战斗类型
- `Bin/BinDataCompressed/BATTLE_GLOBAL_CONFIG.json` — 战斗全局参数
- `Bin/BinDataCompressed/PVP_CONF.json` — PvP 模式配置：标准对战/命运对决/激流对决等模式的 NPC、队伍类型、匹配方式
- `Bin/BinDataCompressed/PVP_RANK_CONF.json` + `PVP_RANK_*.json` — 天梯排名、赛季、机器人配置
- `Bin/BinDataCompressed/PVP_RANDOM_PET_LIBRARY_CONF.json` + `PVP_RANDOM_SKILL_LIBRARY_CONF.json` — 随机对战精灵/技能库
- `Bin/BinDataCompressed/WEATHER_CONF.json` — 天气系统

**物品系统：**
- `Bin/BinDataCompressed/BAG_ITEM_CONF.json` (4.6M) — 物品定义：咕噜球、药品、装备等
- `Bin/BinDataCompressed/BATTLE_ITEM_CONF.json` — 战斗物品
- `Bin/BinDataCompressed/PET_CARRYON_ITEM.json` + `PET_CARRYON_UPGRADE.json` — 宠物携带物/强化

**其他有用数据：**
- `Bin/BinDataCompressed/PET_TALENT_CONF.json` — 宠物天赋配置
- `Bin/BinDataCompressed/ATTRIBUTE_CONF.json` — 属性配置
- `Bin/BinDataCompressed/BASE_POINT_CONF.json` — 基础点数（努力值）
- `Bin/BinDataCompressed/PET_BLOOD_CONF.json` — 血脉系统
- `Bin/BinDataCompressed/PET_INFO_CONF.json` (640K) — 宠物详细信息
- `Bin/BinDataCompressed/EFFECT_CONF.json` (540K) — 效果定义
- `Bin/BinDataCompressed/ACTION_RESULT_TYPE_CONF.json` — 技能效果结果类型
- `Bin/BinDataCompressed/BASIC_QUALITY_CONFIG_CONF.json` — 品质基础配置

#### Protobuf 定义（`PB/proto_out/`，64 个 .proto 文件）

**最关键的战斗协议定义：**
- `battle_data.proto` — **战斗数据核心**：`BATTLEFIELD_STATE` 枚举（33 个状态：INIT→WAIT_JOIN→PRE_FIGHT→ROUND_SELECT→ROUND_FIGHT→SETTLE→RECYCLE）、`BATTLER_STATE`（7 个）、`PET_BIT_TYPE`（60 个宠物状态位：BT_IN_BATTLE/BT_BAN_ACTIVE_SKILL/BT_BAN_STATUS_SKILL 等）、`BattlePerformType`（50 种演出类型：SKILL_CAST/BUFF_CHANGE/DAMAGE/HEAL/ENERGY/DEATH/CHANGE_PET/COMBO_SKILL 等）、`BattlePerformInfo`（完整演出消息，包含所有子类型）
- `battle_buff_data.proto` — buff 运行时数据结构（`BuffRunningData`）
- `com_battle.proto` / `com_battle_enum.proto` — 战斗结果类型（`BATTLE_RESULT_TYPE`）、PK 状态（`PlayerPkState`）、战斗结算信息
- `com_pet.proto` — `PetAttributeInfo`（HP/物攻/特攻/物防/特防/速度各自含 total_race/talent/base_value/effort_exp/effort_lv/effort_add）、`PetData`、进化状态枚举
- `com_pet_skill.proto` — `PetSkillData`（id/type/is_learned/is_equipped/pos/unlock_need_lv/skill_src）、`CastInfo`（技能释放信息）
- `com_pet_team.proto` — 宠物队伍相关
- `com_monster.proto` — 怪物数据
- `c2s_cmd.proto` — 客户端→服务器命令定义
- `zonesvr.proto` / `zonesvr_notify.proto` — 区服协议
- `nrcai.proto` — AI 相关协议

**关键数据结构：**
- `BattleInsidePetInfo` — 战斗中宠物完整状态（pet_id/pos/buffs/battle_attr/skill_round_data/state_bits/energy 等）
- `PetSkillRoundData` — 技能回合数据（state/cost_energy/damage_params/restraint_types/cd_round/enhance_info/skill_buff 等 60+ 字段）
- `BattleStateInfo` — 战场完整状态（round/player_team/enemy_team/evolution_data/pvp_round_limit）
- `SkillCastRecord` — 技能释放记录（caster/target/skill_id/cost_energy/damage_param/restraint_param）
- `DamageRecord` — 伤害记录（caster/target/damage/dam_type/is_critical/is_shield）
- `BattleOpHistory` — 操作历史（skills/change_pets/buffs/damages/role_magics）
- `PvpRankInfo` — PvP 排名信息（r/rank_star/rank_order/rank_name/rank_season_id）

#### 解码工具

- `decode_bin.py` — 将 `.bytes` 二进制配置文件解码为 JSON（需要原始 .bytes 文件）
- `decode_pb.py` — 从编译后的 `.pb` 文件还原 `.proto` 定义文件（`PB/proto_out/` 中的 64 个 .proto 文件即由此生成）
- `PB/proto.json` — protobuf 消息 ID 到消息名称的映射

#### 其他目录

- `BattleFsm/BattleFsmData.json` — 战斗状态机 UI 布局（30+ 状态节点坐标）
- `BattleCamera/` — 57 个战斗摄像机配置 JSON（2V2、技能演出、换宠等场景）
- `Record/` — 32 个真实战斗记录 JSON（BattleEnterNotify/BattleRoundStartNotify/BattlePerformStartNotify 等）
- `Bin/BinLocalize/` — 多语言本地化（dev_CN/en_US/zh_CN/zh_TW 等 7 种语言）
- `Bin/BinConf/` — 91 个配置 schema 文件（描述各 JSON 的字段结构）

#### 数据格式约定

- JSON 统一结构：`{"RocoDataRows": {"ID_AS_STRING": {...}}}`
- 概率/百分比字段：10000 = 100%（如 `success_rate: 10000` = 100% 成功率）
- 属性克制：`type_restraint{N}`，N 为目标属性 ID，1=克制，-1=被克制
- 性格效果 ID：80=物攻，81=物防，82=特攻，83=特防，84=特防，85=速度
- 技能类型：1=主动，2=被动
- 技能效果类型（SKILL_RESULT_TYPE）：1=EFFECT，2=BUFFBASE，3=BUFFGROUP
- 伤害类型（SkillRestraintType）：-3 到 +3，代表被克制三层到克制三层
- 宠物状态位（PET_BIT_TYPE）：位标记，如 BT_IN_BATTLE=11, BT_BAN_ACTIVE_SKILL=12

#### 与现有项目数据的映射

| World-Data 文件 | 项目文件 | 关系 |
|-----------------|---------|------|
| `PETBASE_CONF.json` | `data/game/pet_map.json` | 官方解包 vs wiki 数据，PETBASE 更权威 |
| `SKILL_CONF.json` | `data/game/skill_map.json` | SKILL_CONF 含完整 skill_result 效果链 |
| `TYPE_DICTIONARY.json` | `data/game/type_chart.json` | 同源数据，可互相验证 |
| `BUFFBASE_CONF.json` | `data/game/buffbase_map.json` | 官方 buff 参数定义 |
| `BUFF_CONF.json` | `data/game/buff_map.json` | buff 完整配置 |
| `PET_EVOLUTION_CONF.json` | 无 | 进化链数据，尚未导入 |
| `NATURE_CONF.json` | 无 | 性格效果数据，尚未导入 |
| `battle_data.proto` | `data/game/proto_schema.json` | protobuf 结构权威定义 |
| `PB/proto_out/*.proto` | `protocol/proto_core.py` | 协议解析字段级参考 |

#### 何时参考此仓库

- **验证或补充宠物/技能数据**：PETBASE_CONF 和 SKILL_CONF 是最权威的数据源，比 wiki 数据更准确完整
- **扩展技能效果解析**：`skill_result` 数组包含完整的效果链（effect_id + success_rate + cast_moment），是伤害计算 hook 系统的核心参考
- **理解 buff 叠加规则**：`buff_groupsigns`（同组互斥）、`buff_list_priority`（优先级）、`add_max`（叠加上限）、`connect_buff`（联动）
- **解析新协议字段**：.proto 文件提供完整的 protobuf 字段定义和编号，是 `proto_core.py` 和 `battle.py` 的权威参考
- **添加性格系统**：NATURE_CONF 提供性格对属性的加减效果，计算实际属性时必需
- **添加进化链展示**：PET_EVOLUTION_CONF 提供完整进化链、阶段和等级要求
- **理解战斗状态流程**：BattleFsm 定义 30+ 状态节点，proto 定义完整的状态枚举
- **扩展 PvP 模式支持**：PVP_CONF + PVP_RANK_* 文件定义所有对战模式的规则和配置

### NRC_AI

Local path: `references/NRC_AI/`

洛克王国战斗 AI 模拟器 — 基于蒙特卡洛树搜索（MCTS）的自动对战模拟系统。最核心的价值在于其**效果引擎**（Effect Engine），对 100+ 种战斗效果原语做了完整的数据驱动实现。Key areas:
- **效果引擎**: `src/effect_engine.py`（Handler 注册表，执行效果原语）、`src/effect_models.py`（`E` 枚举：100+ 效果原语类型定义）、`src/effect_data.py`（59 个手工配置技能效果 + 68 个特性效果配置）
- **自动生成效果**: `src/skill_effects_generated.py`（455 个自动生成的技能效果配置）
- **战斗逻辑**: `src/battle.py`（回合流程、印记系统、状态管理）
- **数据模型**: `src/models.py`（Pokemon / Skill / BattleState 数据模型）、`src/effect_models.py`（Timing / SkillTiming 触发时机定义）
- **数据**: `data/nrc.db`（SQLite: 461 精灵 × 495 技能）、`scripts/`（爬虫 / 效果生成器 / 审计工具）
- **文档**: `docs/COVERAGE_MATRIX.md`（特性覆盖矩阵）、`docs/SKILLS_ABILITIES_CONFIG_GUIDE.md`（配置开发手册）

**何时参考此仓库：**
- 实现或扩展 `innate_hooks.py` 中的天赋/特性伤害修改逻辑时，参考 NRC_AI 的 `effect_data.py` 和 `effect_models.py` 了解特定效果原语的参数格式和行为定义
- 需要理解 buff/debuff/印记/状态的精确交互机制时（如层数叠加、触发时机、覆盖规则），参考 `effect_engine.py` 中的 Handler 实现和 `battle.py` 中的印记系统
- 扩展伤害计算管线（`damage_calc.py` 的 hook stages）时，参考 NRC_AI 的效果分类体系确认哪些效果属于威力修改、哪些属于最终伤害修改
- 验证技能效果的正确性时，用 `skill_effects_generated.py` 和 `effect_data.py` 交叉比对
- 需要查找宠物基础数值或技能数据库时，参考 `data/nrc.db` 和 `src/pokemon_db.py` / `src/skill_db.py`

## Language Notes

The codebase uses Chinese for UI strings, comments, and docstrings. Game data files use Chinese field names. Preserve this convention when modifying UI or data-related code.
