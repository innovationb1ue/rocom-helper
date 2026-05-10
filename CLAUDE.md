# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Roco PvP Helper (洛克王国 PvP 辅助工具) — a real-time battle analysis and suggestion tool for Roco Kingdom PvP. It passively monitors game network traffic on port 8195, decrypts the custom BE21 protocol, tracks live battle state, and provides actionable suggestions (type counters, threat assessment, team composition) during PvP battles. The tool is purely passive — it only reads traffic, never sends packets to the game.

## Tech Stack

- **Backend**: Python 3.11+, FastAPI, Scapy, PyCryptodome, uvicorn
- **Frontend**: React 19, TypeScript, Ant Design 6, Zustand, Vite 8, React Router 7
- **Protocol**: Custom BE21 binary framing with AES-128-CBC encryption, protobuf-like message payloads

## Commands

### Backend
```bash
python -m src.main              # Start FastAPI server on :8000 (with hot reload)
pytest                          # Run all tests
pytest tests/test_crypto.py     # Run a single test file
pytest -k "test_name"           # Run tests matching a name pattern
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
python -m src.main

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
   python -m scripts.replay_to_frontend --delay 80 --session battle_session_1

   # 回放到指定回合（如 R7）停止，用于测试中间状态
   python -m scripts.replay_to_frontend --delay 80 --session battle_session_1 --round 7
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
  ├── battle_state.py ── Real-time battle state machine (HP, energy, buffs, turn tracking)
  ├── battle_advisor.py ── Battle analysis coordinator (skill analysis + damage prediction)
  ├── damage_calc.py ── Damage calculation engine with 4-stage hook pipeline
  ├── innate_hooks.py ── Innate skill damage hooks (combo/stat/type/power modifications)
  ├── event_formatter.py ── Protocol events → UI-ready formatted events
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
  │                  SkillPanel, HookAdvicePanel, BattleSummaryPanel, TeamRoster, CoverageRadar
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

Tests live in `tests/` and mirror the module structure (`test_crypto.py` tests `capture/crypto.py`, etc.). Test fixtures are in `tests/fixtures/`. The test suite covers crypto, protocol parsing, game mechanics (type chart, stats, skill eval), battle state tracking, and API endpoints.

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

洛克王国游戏数据解包与解码工具集 — game data extraction and decoding reference. Key areas:
- **`Bin/BinData/`** and **`Bin/BinDataCompressed/`** — decoded game config JSON (skills, pets, items, etc.), useful for cross-checking our `data/game/` JSON files
- **`Bin/BinConf/`** — schema files (.non format) describing binary config structure
- **`Bin/BinLocalize/`** — localized string data (en_US, etc.)
- **`Bin/decode_bin.py`** — `.bytes` binary config decoder
- **`PB/decode_pb.py`** — `.pb` file to `.proto` reconstructor, useful for understanding protobuf message definitions
- **`BattleCamera/`**, **`BattleFsm/`**, **`BattleRecord/`** — battle-related data (camera, FSM state machine, replay records)

Use this repo to look up game entity IDs, skill/effect definitions, protobuf schemas, and to validate or extend our static game data.

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
