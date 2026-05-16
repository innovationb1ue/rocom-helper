# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 提供代码库工作指引。

## 项目概述

洛克王国 PvP 辅助工具 — 实时战斗分析与建议工具。被动监听游戏 8195 端口的网络流量，解密自定义 BE21 协议，跟踪实时战斗状态，在 PvP 对战中提供可操作建议（属性克制、威胁评估、阵容搭配）。工具纯粹被动——只读取流量，不会向游戏发送任何数据包。

## 运行环境

- **生产运行环境**：Windows — 工具和游戏都在 Windows 上运行
- **开发环境**：可能在 macOS 上开发，但**所有代码必须以 Windows 为基准**
- **注意事项**：使用 Windows 兼容的 API、路径和命令。Scapy 抓包在 Windows 上需要安装 Npcap。使用 `py`（不是 `python`）作为 Python 启动器。功能完成前必须在 Windows 上测试。

## 技术栈

- **后端**：Python 3.9+, FastAPI, Scapy, PyCryptodome, uvicorn
- **Python 启动器**：Windows 上使用 `py`（不是 `python`）— `python` 不在 PATH 中
- **前端**：React 19, TypeScript, Ant Design 6, Zustand, Vite 8, React Router 7
- **协议**：自定义 BE21 二进制帧格式，AES-128-CBC 加密，类 protobuf 消息载荷

## 命令

### 后端
```bash
py -m src.main                   # 启动 FastAPI 服务 :8000（支持热重载）
pytest                          # 运行所有测试
pytest tests/test_crypto.py     # 运行单个测试文件
pytest -k "test_name"           # 按名称模式匹配运行测试
```

### 后端自闭环回放
```bash
py -m scripts.replay_headless --session battle_session_1       # 文本摘要（事件、预测、hook 建议）
py -m scripts.replay_headless --session battle_session_1 --json  # 完整 JSON 输出（写入 tmp/）
py -m scripts.replay_headless --round 7                        # 在第 7 回合停止
py -m scripts.generate_battle_report --json                    # 生成报告文件（docs/battle_report.txt）
py -m scripts.replay_to_frontend --delay 80 --session battle_session_1  # 推送回放到前端 WebSocket
py -m scripts.replay_to_frontend --delay 80 --session battle_session_1 --round 7  # 回放到第 7 回合
```

### 前端（在 `web/` 目录下）
```bash
npm run dev                     # Vite 开发服务器 :5173
npm run build                   # TypeScript 编译 + Vite 生产构建
npm run lint                    # ESLint 检查
```

## 开发工作流

**每次开发任务完成后必须执行** — 按顺序完成以下步骤：

### 1. 运行完整测试套件
```bash
pytest
```
所有测试必须通过才能继续。先修复失败测试再进行下一步。

### 2. 启动后端和前端
```bash
# 终端 1 — 后端
py -m src.main

# 终端 2 — 前端
cd web && npm run dev
```

### 3. MCP 战斗回放验证（完整的前后端回放验证）

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

### 4. 截图清理

**审查后立即删除截图文件。** 通过 MCP `take_screenshot` 或其他方式截图后，分析完毕即删除。不要在项目目录中遗留 `.png`/`.jpg`/`.jpeg` 截图文件。此规则适用于主 agent 和子 agent。

### 5. 后端自闭环回放验证

当要求进行"后端自闭环验证"时，使用 `BattleReplayRunner` 进行纯后端验证，无需启动服务器或前端。

**步骤：**

1. **运行 headless 回放** — 使用 Bash 运行：
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

## 架构

系统是一个分层管线，在抓包、解析、分析、展示之间有清晰的边界：

```
网络流量（端口 8195）
  │
  ▼
capture/sniffer.py ── Scapy AsyncSniffer，编排整个管线
  │
  ├── capture/key_capture.py ── 从 ACK 包提取 AES 会话密钥
  ├── capture/reassembly.py ── TCP 流重组为有序流
  ├── capture/frame.py ── BE21 帧解析（头部 + 载荷提取）
  ├── capture/crypto.py ── AES-128-CBC 解密加密载荷
  │
  ▼
protocol/
  ├── proto_core.py ── Protobuf 解析器、TGCP 传输（4 种格式）、宠物/状态提取、游戏常量
  ├── opcodes.py ── 基于装饰器的 opcode/内部消息注册与分发
  ├── battle.py ── 战斗专用提取（双路径：schema 优先 + 原始字段回退）
  │
  ▼
analysis/
  ├── constants.py ── 共享 opcode 常量、OPCODE_LABELS、SDT_TO_TYPE 重导出（单一数据源）
  ├── pet_info.py ── PetInfo 构建工厂（from_wrapper/from_change_pet → to_dict），统一宠物字典构建，包含 base_speed（来自 battle_stats[5]）
  ├── battle_state.py ── 实时战斗状态机（HP、能量、buff、回合追踪）
  ├── battle_processor.py ── 纯同步事件处理器（状态 + 格式化 + 伤害 + hooks），BattleManager 和 ReplayRunner 共用
  ├── battle_advisor.py ── 战斗分析协调器（技能分析 + 伤害预测 + 状态建议）
  ├── damage_calc.py ── 伤害计算引擎，4 阶段 hook 管线
  ├── innate_hooks.py ── 天赋技能伤害 hooks（连击/属性/类型/威力修改）
  ├── event_formatter.py ── 协议事件 → UI 格式化事件
  ├── replay_runner.py ── 无头回放器（无 FastAPI/WebSocket），生成 ReplayResult 和逐事件快照
  ├── hook_registry.py ── 可扩展分析 hook 系统（基于 ABC，生命周期感知）
  ├── hooks/
  │   ├── __init__.py ── 默认 hook 工厂
  │   ├── opponent_tracker.py ── 对手技能/换宠模式追踪
  │   ├── energy_monitor.py ── 能量监控与攻击窗口检测
  │   └── switch_advisor.py ── 基于属性克制的换宠建议
  ├── coverage.py ── 攻击/防御属性覆盖计算
  ├── counter.py ── 基于属性克制的 counter-pick 逻辑
  ├── threat.py ── 对手宠物威胁评估
  ├── team_builder.py ── 阵容搭配建议
  │
  ▼
game/
  ├── type_chart.py ── TypeChart 类：18 属性克制矩阵、弱点/抗性查询、覆盖评分
  ├── stats.py ── 种族值计算器（HP + 5 项属性公式）、性格修正、属性评级
  ├── skill_eval.py ── 技能评分引擎（威力、效率、命中率、PP、属性覆盖、效果）
  │
  ▼
api/ (FastAPI)
  ├── app.py ── 应用工厂（create_app）、CORS、路由挂载
  ├── battle_manager.py ── 全局单例：抓包桥接、WS 推送、hook 分发
  ├── sniffer_manager.py ── 抓包会话管理
  ├── routes_battle.py ── WebSocket（/ws/battle）+ REST + 回放端点
  ├── routes_sniffer.py ── 抓包控制 API
  ├── routes_teams.py ── 阵容分析端点
  ├── routes_pets.py ── 宠物数据查询
  ├── routes_data.py ── 静态游戏数据服务
  │
  ▼
web/ (React SPA)
  ├── stores/ ── Zustand 状态管理（battleStore, snifferStore, petsStore）
  ├── hooks/ ── useBattle（WebSocket）、usePets（REST）、useSnifferMonitor
  ├── pages/ ── Dashboard, PetBrowser, TeamBuilder, TypeChart, BattleLive, BattleHistory
  ├── components/ ── PetCard, TeamSlot, TypeBadge, BattleTimeline, BattleEventLog,
  │                  DamagePredictionPanel, SkillPanel, HookAdvicePanel,
  │                  BattleSummaryPanel, TeamRoster, CoverageRadar
```

### 数据文件

静态游戏数据存放在 `data/game/` 目录，为 JSON 文件（约 24MB）。关键文件：

**核心数据库：**
- `pet_map.json` (706K) — 宠物定义（ID、名称、种族值、属性）
- `skill_map.json` (1.2M) — 技能定义（威力、属性、能量消耗、目标类型）
- `pet_skill_map.json` — 宠物与技能映射（每个宠物可学习的技能）
- `type_chart.json` (2.8K) — 18 属性克制矩阵
- `attr_map.json` (12K) — 属性/类型名称查找

**协议与 schema：**
- `proto_schema.json` (3.1M) — Protobuf 消息 schema 定义
- `opcode_pb_map.json` (315K) — opcode 到 protobuf 消息的映射
- `pb_message_index.json` (1.8M) — Protobuf 消息名称索引

**战斗数据：**
- `innate_skills.json` (4.5K) — 天赋技能定义，用于伤害 hook 系统
- `buff_map.json` (891K) — Buff/效果定义（ID、名称、描述）
- `buffbase_map.json` (1.1M) — 基础 buff 定义

**怪物与 wiki 数据：**
- `monster_map.json` (7.3M) — 游戏内怪物 ID 映射
- `wiki_pets.json` (217K) — Wiki 来源的宠物数据（备用种族值）
- `wiki_skills.json` (90K) — Wiki 来源的技能数据
- `special_move_map.json` (86K) — 特殊招式定义

`src/data/loader.py` 模块提供类型化数据访问；`src/data/scraper.py` 和 `src/data/updater.py` 负责从游戏 wiki 爬取数据。

### 关键设计模式

- **后端入口**：`src/main.py` 通过 `src/api.app:app` 运行 uvicorn（工厂模式 `create_app()`）
- **路由注册**：所有路由在 `app.py` 中以 `/api` 前缀挂载（战斗 WebSocket 除外）
- **CORS**：允许的源为 `localhost:5173` 和 `127.0.0.1:5173`（Vite 开发服务器）
- **状态管理**：前端使用 Zustand stores；战斗状态通过 WebSocket，宠物/阵容数据通过 REST
- **API 客户端**：`web/src/utils/api.ts` 集中管理 Axios 调用
- **BattleManager 单例**：`get_battle_manager()` 提供全局访问，桥接抓包器到 WebSocket 客户端和分析管线
- **Opcode 分发**：`opcodes.py` 使用装饰器注册表（`_OPCODE_REGISTRY` 用于主 opcode，`_INNER_REGISTRY` 用于 opcode 0x0414 的内部消息分发）。`summarize()` 函数对未知 opcode 回退到 `opcode_pb_map.json` 元数据。
- **Opcode 常量**：`src/analysis/constants.py` 集中管理所有 opcode 常量（`OPCODE_BATTLE_ENTER`、`OPCODE_ACTION_RESOLVE` 等）、opcode 集合（`LIFECYCLE_OPCODES`、`DAMAGE_OPCODES`、`IN_BATTLE_OPCODES`）、`OPCODE_LABELS`，并重导出 `SDT_TO_TYPE`。所有分析和 API 模块从此文件导入，不使用十六进制字面量。

### 关键架构概念

**双 Hook 系统：**

项目有两套独立的 hook 系统，服务于不同目的：

1. **伤害计算 Hooks**（`damage_calc.py`）— `DamageCalculator` 内的 4 阶段管线，修改伤害计算：
   - `pre_power` — 在计算前修改技能威力
   - `post_base` — 在核心公式后修改基础伤害
   - `pre_final` — 在最终乘法前修改克制/STAB
   - `post_calc` — 修改最终伤害值和命中次数
   - 天赋技能 hooks（`innate_hooks.py`）使用此系统：`stat_modify_hook`（post_base）、`type_resist_modify_hook`（pre_final）、`combo_modify_hook` 和 `power_modify_hook`（post_calc）。

2. **分析 Hook 系统**（`hook_registry.py`）— 基于 ABC 的事件驱动 hook 系统，由战斗生命周期事件触发：
   - 触发器：`ON_BATTLE_ENTER`, `ON_ROUND_START`, `ON_ACTION_RESOLVE`, `ON_SPECIAL_REFRESH`, `ON_BATTLE_FINISH`, `ON_CHANGE_PET`, `ON_DEFEAT`
   - Hooks 实现 `AnalysisHook` ABC 并返回 `HookAdvice` dataclass
   - 默认 hooks：`OpponentTrackerHook`, `EnergyMonitorHook`, `SwitchAdvisorHook`

**注意**：`register_innate_hooks()` 由 `BattleAdvisor` 自动调用，因此通过 `BattleManager` 触发的伤害分析已激活天赋 hooks。但如果直接实例化 `DamageCalculator`（如测试或独立脚本），必须显式调用 `register_innate_hooks()` 才能应用天赋技能效果。

**PvP 数据可用性：**

协议对双方提供不对称数据。理解哪些数据可用、哪些不可用，对行动建议至关重要：

- **速度**：双方都可用，通过 `battle_stats[5]` 从第一个包（`battle_enter` 0x1316）获取。存储在 `pet["base_speed"]` 中 — 战斗中不可变。`pet["effective_speed"]` 在 `get_state()` 中按需计算，基于 `base_speed` + 活跃速度 buff（通过 `loader.py` 中的 `get_speed_buff_modifiers`）。
- **装备技能**：仅自己方宠物可用（`inside_info_f8` 来源）。对手的 `equipped_skills` 始终为 `[]`。
- **对手已学技能**：通过 `used_skills` 在对手使用技能时逐步累积。对手完整技能池可从 `pet_skill_map.json` 按 `base_id` 查询。
- **属性（物攻/物防/特攻/特防）**：协议发送 `battle_stats[1:5]` 但对手通常为 `0` — 仅 HP（`[0]`）和速度（`[5]`）有值。`extract_creature` 的 `stats` 字段对手也为空。

**双提取策略（battle.py）：**

`battle.py` 中所有主要提取器使用双路径方法：
1. **Schema 优先**：通过 `proto_schema.json` 定义解码，结构化、类型安全
2. **原始回退**：当 schema 数据不可用时手动解析 protobuf 字段

两条路径产生相同的输出格式。`_schema_quality()` 辅助函数为每个结果标记 `parse_quality`。

**战斗生命周期：**

```
idle → selecting（0x1316 battle_enter）→ resolving（0x131A round_start）
  → [行动事件：0x1324, 0x130C, 0x13F4, ...]
  → [每回合重复]
  → finished（0x132C battle_finish）
```

**WebSocket 消息类型：**

`/ws/battle` 端点向已连接客户端推送以下消息类型：
- `connected` — 初始连接确认
- `state_update` — 每次事件后的完整战斗状态快照。每个宠物字典包含 `base_speed`（来自 `battle_stats[5]` 的精确值，在 battle_enter 时设置后不再修改 — 速度 buff 应从此基础值计算）
- `battle_event` / `battle_events` — 格式化的战斗事件，用于时间线展示
- `battle_summary` — 战斗结束摘要（在 0x132C 时计算）
- `skill_analysis` — 所有装备技能的伤害预测（可选包含 `traits`）
- `hook_advice` — 分析 hook 建议（能量、换宠、对手模式）
- `suggestions` — 基于规则的简单建议（低 HP、低能量等）

**抓包桥接：**

`BattleManager` 通过 `_ensure_bridge()` 向 `SnifferManager` 注册回调。当抓包器捕获 TGCP DATA 包时，桥接器解码 opcode 并通过完整管线分发（tracker → formatter → analysis → WebSocket 推送）。仅处理 `_LIFECYCLE_OPCODES`（0x1316, 0x131A, 0x132C, 0x0102）和 `_IN_BATTLE_OPCODES`。

## 测试

测试位于 `tests/` 目录，与模块结构对应。套件包含 **640+ 个测试**，覆盖约 30 个测试文件。主要测试领域：

- **协议解析**：`test_opcodes.py`, `test_frame.py`, `test_crypto.py`, `test_skill_extraction.py`, `test_type_extraction.py`
- **游戏机制**：`test_type_chart.py`（50 个测试）, `test_stats.py`（21 个测试）, `test_skill_eval.py`（8 个测试）
- **战斗状态**：`test_battle_state.py`, `test_event_formatter.py`, `test_battle_replay.py`
- **伤害计算**：`test_damage_calc.py`, `test_innate_hooks.py`（24 个测试）, `test_innate_integration.py`（17 个端到端测试）
- **分析 hooks**：`test_hook_registry.py`, `test_hook_opponent_tracker.py`, `test_hook_energy_monitor.py`, `test_hook_switch_advisor.py`
- **策略**：`test_counter.py`, `test_coverage.py`, `test_team_builder.py`, `test_threat.py`
- **API**：`test_api.py`, `test_replay_api.py`, `test_battle_advisor.py`, `test_battle_advisor_integration.py`
- **数据**：`test_loader.py`

测试 fixture 位于 `tests/fixtures/`（包含 `packets/battle_session_1/` 和 `packets/battle_session_2/` 用于回放测试）。所有测试使用真实数据，不使用 mock。

### 无头测试数据结构

`BattleReplayRunner` 通过三个 dataclass 产生结构化输出。理解这些对编写分析测试至关重要：

**`ReplayResult`**（顶层，来自 `src/analysis/replay_runner.py`）：
```python
@dataclass
class ReplayResult:
    total_packets: int                           # 已处理事件数
    events: List[ReplayEventSnapshot]            # 逐事件的扁平快照
    rounds: List[RoundSnapshot]                  # 逐回合聚合
    final_state: Dict[str, Any]                  # 最终 BattleStateTracker 状态
    battle_summary: Dict[str, Any]               # 来自 compute_battle_summary()
    stopped_early: bool                          # 是否因 stop_round 提前停止
```

**`RoundSnapshot`**（逐回合聚合）：
- `round_num`, `state_at_start`, `state_at_end`
- `damage_predictions` — 每个技能的伤害预测字典列表
- `formatted_events` — 聚合的 UI 就绪事件字典（kind/summary/icon/color）
- `suggestions` — 聚合的建议字典（type/message）

**`ReplayEventSnapshot`**（逐事件，最细粒度）：
- `opcode`, `kind`, `round_num`
- `state_before`, `state_after` — 事件前后的战斗状态
- `battle_advice` — 包含 `skill_analysis`（伤害预测）和 `opp_traits` 的字典
- `hook_advice` — 字典列表（hook_id/title/priority/messages）
- `suggestions` — 字典列表（type/message）

**`ProcessResult`**（来自 `BattleProcessor.process_event()`）：
- `state` — 更新后的战斗状态字典
- `formatted_events` — FormattedEvent 列表
- `battle_advice` — 技能分析字典（或 None）
- `hook_advice` — hook 建议字典列表
- `suggestions` — 建议字典列表

**`battle_advice` 字典结构**（当存在时）：
- `skill_analysis` — 每个技能的字典列表：`skill_name`, `expected_damage`, `can_ko`, `effectiveness`, `effectiveness_label`, `energy_cost`, `hit_count`, `damage_breakdown`, `warnings`
- `opp_traits` — 检测到的对手天赋特性列表

**`hook_advice` 字典结构**（每条记录）：
- `hook_id` — 如 `"opponent_tracker"`, `"energy_monitor"`, `"switch_advisor"`
- `priority` — 0=紧急, 1=重要, 2=信息
- `title` — 可读标题
- `messages` — 包含 `message` 键的字典列表

### 分析测试模式

**模式 1：完整回放集成测试**（用真实包测试整个管线）：
```python
from tests.packet_reader import load_battle_packets
from src.analysis.replay_runner import BattleReplayRunner

packets = load_battle_packets("tests/fixtures/packets/battle_session_1")
runner = BattleReplayRunner()
result = runner.run(packets)

# 验证最终状态
assert result.final_state["round"] == 17
assert result.final_state["result"] == "WIN_HP"
# 验证逐回合预测
for rs in result.rounds:
    if rs.damage_predictions:
        for pred in rs.damage_predictions:
            assert "expected_damage" in pred
            assert "can_ko" in pred
```

**模式 2：单事件处理器测试**（用构造的事件测试 BattleProcessor）：
```python
from src.analysis.battle_processor import BattleProcessor

processor = BattleProcessor()
pr = processor.process_event(0x1316, battle_enter_detail)
assert len(pr.state["my_pets"]) == 6
assert pr.formatted_events  # 应产生至少一个事件
```

**模式 3：状态追踪器单元测试**（逐步测试状态转换）：
```python
from src.analysis.battle_state import BattleStateTracker

tracker = BattleStateTracker()
tracker.handle_event(0x1316, battle_enter_detail)
state = tracker.get_state()
assert state["phase"] == "selecting"
assert state["my_active"] is not None
```

**模式 4：指定回合停止测试**（测试中间战斗状态）：
```python
runner = BattleReplayRunner()
result = runner.run(packets, stop_round=5)
assert result.stopped_early is True
# 检查第 5 回合状态
round5 = result.rounds[-1]
assert round5.round_num == 5
```

**模式 5：标志选择性测试**（禁用高开销计算）：
```python
runner = BattleReplayRunner(include_analysis=False, include_hooks=False)
result = runner.run(packets)  # 仅状态追踪，无伤害/hook 计算
assert result.final_state is not None
assert all(rs.battle_advice is None for rs in result.rounds)
```

### 无头回放 CLI 输出指南

`replay_headless` 文本输出结构（每回合一个区块）：
```
=== Round N ===
  My: {name} HP {cur}/{max} Energy {n}  |  Opp: {name} HP {cur}/{max}
  [kind] summary text                    ← 格式化事件
  SUGGEST: [type] message                ← 建议
  {skill_name}  dmg: {n} range: [{min}-{max}] eff: {label} [KO]  ← 伤害预测
  HOOK: [hook_id] title                  ← hook 建议
    - message text
```

JSON 输出（`--json`，写入 `tmp/`）：结构化的 `ReplayResult` 序列化，包含上述所有字段。

## 协议字段参考

**编码时查阅字段含义的首选资源：**

- `docs/proto_reference.md` — 战斗协议字段参考手册（枚举值、消息字段映射、游戏配置语义）
- `data/game/proto_field_reference.json` — 结构化 JSON 版本（34 个枚举 + 386 个消息定义 + 游戏配置字段语义 + ID 交叉引用链）

**何时查阅：**
- 解析新协议字段时 — 先查 proto_reference.md 找到字段编号对应的名称和类型
- 理解 buff/skill/effect 参数含义时 — 查阅"游戏配置字段语义"章节
- 确认枚举值含义时 — 查阅"枚举值速查"章节（如 BattlePerformType、SkillRestraintType）
- 追踪 ID 引用链时 — skill_result.effect_id → EFFECT_CONF/BUFF_CONF，buff_base_ids → BUFFBASE_CONF

**数据来源：** 从 `references/Roco-Kingdom-World-Data/` 的 .proto 定义和游戏配置 JSON 中自动提取。

## 参考仓库

以下外部仓库是协议解析和游戏数据的有用参考：

所有参考仓库已克隆到本地 `references/` 目录下。

### Roco-Kingdom-Protocol-Parser (RKPP)

本地路径：`references/Roco-Kingdom-Protocol-Parser/`

洛克王国战斗协议解析器 — 战斗协议解析的主要参考。关键重叠领域：
- **协议解析**：`rkpp_proto_core.py`（proto-tree 解析）、`rkpp_proto_battle.py`（战斗语义）— 对应我们的 `protocol/proto_core.py` 和 `protocol/battle.py`
- **网络层**：`rkpp_network.py`（TCP 重组、BE21 帧解析、AES-CBC 解密、密钥提取）— 对应我们的 `capture/` 模块
- **战斗分析**：`rkpp_analysis.py`（schema 驱动的字段解码）、`rkpp_reporter.py`（战斗摘要）— 对应我们的 `analysis/battle_state.py`
- **数据**：`Data.py` / `Data/` — 运行时数据访问和离线索引数据
- **服务器文档**：`Server.md` — 服务器协议文档

使用此仓库交叉验证 opcode 含义、protobuf 字段结构、战斗状态转换，以及我们实现中尚未覆盖的协议细节。

### Roco-Kingdom-World-Data

本地路径：`references/Roco-Kingdom-World-Data/`

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

## 语言约定

代码库中的 UI 文本、注释和文档字符串使用中文。游戏数据文件使用中文字段名。修改 UI 或数据相关代码时请保持此约定。
