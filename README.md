# Roco PvP Helper (洛克王国 PvP 辅助工具)

实时战斗分析与辅助决策工具，专为洛克王国 PvP 对战设计。通过被动抓取游戏网络流量（端口 8195），解密自定义 BE21 协议，实时追踪战斗状态，并提供属性克制分析、伤害预测、战术推荐、换宠建议等辅助决策。

> **声明：** 本工具为纯被动读取，仅解析网络流量，**不会向游戏服务器发送任何数据包**。

---

## 已实现功能

### 网络抓包与协议解析

- **被动网络监听** — 基于 Scapy 异步嗅探端口 8195 游戏流量，提取 AES 会话密钥，自动解密 BE21 协议帧
- **TCP 流重组** — 有序数据流重组，处理分片和乱序
- **BE21 帧解析** — 固定帧头 + 加密帧体的二进制协议解析
- **AES-128-CBC 解密** — 从 TCP 握手 ACK 包提取密钥，实时解密载荷
- **Protobuf 解析** — 自定义轻量 Protobuf 解码器，支持 schema-first 和 raw field 双策略解析
- **20+ opcode 分发** — 装饰器注册表驱动的 opcode 分发系统，覆盖所有战斗相关消息

### 实时战斗追踪

- **战斗状态机** — 完整追踪 HP、能量、buff/debuff、回合数、宠物切换、天气效果
- **20+ 事件类型** — 技能释放、伤害、击败、治疗、能量变化、换宠、效果施加、天气变化等
- **双阵营识别** — 多层级 side 识别逻辑，准确区分我方/敌方行为
- **速度追踪** — 从 `battle_enter` 提取双方速度基础值，实时计算含 buff 的有效速度

### 伤害预测

- **确定性伤害计算** — 基于 NRC_AI 公式：`base = (ATK/DEF) * power * 0.9`，叠加克制/STAB/天气/威力修正
- **4 阶段 Hook 管线** — `pre_power → post_base → pre_final → post_calc`，可扩展伤害修改
- **先天技能效果** — 支持连击、属性抵抗、威力修正、HP 阈值增伤、伤害减免等 5 类先天技能 hook
- **多段伤害支持** — 连击技能自动计算命中次数和总伤害
- **KO 判定** — 每个技能标注是否可击杀当前敌方宠物

### 战术推荐引擎

- **期望值动作排序** — 枚举所有可用动作（技能 + 换宠），基于对手行为概率加权打分
- **多维度评分** — 伤害输出 25%、KO 价值 30%、承伤评估 15%、对手 KO 风险 20%、属性克制 5%、能量 3%、数量优势 2%
- **中文推荐理由** — 每个推荐附带可读的战术解释

### 分析 Hook 系统

基于事件驱动的可扩展 Hook 系统，在战斗生命周期 7 个关键节点触发：

| Hook | 触发时机 | 功能 |
|------|---------|------|
| 对手行为追踪 | 战斗开始、行动结算、换宠 | 记录对手技能使用频率，检测技能偏好（>=50%），追踪换宠模式 |
| 能量监控 | 回合开始、行动结算、特殊刷新 | 跟踪双方能量状态，预警能量不足，识别对手攻击窗口 |
| 换宠建议 | 回合开始、换宠 | 属性不利时推荐换宠，从替补席找最佳 counter |

### 策略分析

- **属性克制表** — 21 种属性间完整的克制/抵抗/免疫关系矩阵，支持交互查询
- **Counter-Pick 推荐** — 基于进攻效果、技能覆盖、防御抗性和速度优势的综合评分
- **覆盖率分析** — 攻防属性覆盖雷达图，计算覆盖评分（0-100），识别未覆盖属性和共同弱点
- **威胁评估** — 基于属性克制、技能覆盖和速度对敌方宠物进行综合威胁打分，推荐击杀优先级
- **队伍构建** — 覆盖率评分、共同弱点检测、速度梯队排名、角色分析、队友推荐
- **技能评分** — 综合威力/效率/命中率/PP/属性覆盖/附加效果的 0-100 评分系统
- **种族值计算** — HP + 5 项属性公式、20+ 性格修正、属性评级

### 数据管理

- **BWIKI 数据爬取** — 从游戏 Wiki 自动爬取宠物和技能数据（httpx + BeautifulSoup）
- **增量数据更新** — 字段级 diff 引擎，交互式确认后应用变更，支持 dry-run
- **Wiki 技能导入** — 从 NRC_AI Wiki CSV 导入宠物可学习技能
- **热门技能预设** — 按宠物保存常用技能配置，用于对手技能推断

### 前端界面

7 个功能页面，使用 Ant Design 6 组件库：

| 页面 | 路由 | 功能 |
|------|------|------|
| 仪表盘 | `/` | 数据总览（已加载记录数、数据表统计、属性数量） |
| 精灵浏览 | `/pets` | 700+ 宠物数据搜索、分页浏览、详情抽屉（种族值、技能、属性） |
| 队伍构建 | `/teams` | 6 槽位队伍编辑器，属性覆盖雷达图，counter 推荐，协同分析 |
| 属性克制表 | `/types` | 21×21 交互式属性克制矩阵（颜色编码倍率） |
| 实时战斗 | `/battle` | WebSocket 驱动的实时战斗面板：阵容状态、事件流、伤害预测、战术推荐、Hook 建议、对手技能分析、战斗总结 |
| 技能预设 | `/skill-presets` | 配置宠物常用技能预设，浏览可学习技能，保存/删除预设 |
| 战斗历史 | `/history` | 战斗回放与历史记录（开发中） |

### 战斗回放系统

- **无头回放** — `replay_headless` 纯后端回放，输出逐回合事件/预测/建议
- **前端回放** — `replay_to_frontend` 将录制包推送到前端 WebSocket 实时渲染
- **战斗报告** — `generate_battle_report` 生成格式化文本报告
- **战斗提取** — `extract_battle` 从抓包会话中自动检测战斗边界并提取为测试 fixture
- **指定回合停止** — 支持在任意回合暂停回放，测试中间状态

---

## 技术架构

```
┌──────────────────────────────────────────────────────┐
│                    React SPA (Vite)                    │
│   Zustand Stores · Ant Design 6 · React Router 7      │
└───────────────────────┬──────────────────────────────┘
                        │ WebSocket + REST API
┌───────────────────────┴──────────────────────────────┐
│                   FastAPI Backend                       │
│  BattleManager (Singleton) · SnifferManager · Routes   │
└───────────────────────┬──────────────────────────────┘
                        │
        ┌───────────────┼───────────────┐
        ▼               ▼               ▼
    Analysis          Protocol        Capture
  ┌───────────┐  ┌────────────┐  ┌──────────────┐
  │BattleState│  │ Proto Core │  │  Scapy Sniffer│
  │DamageCalc │  │ Opcodes    │  │  TCP Reassembly│
  │InnatHooks │  │ Battle Ext │  │  BE21 Frame   │
  │Advisor    │  │            │  │  AES Decrypt  │
  │TacticalEng│  │            │  │  Key Capture  │
  │Hooks/...  │  │            │  │               │
  └───────────┘  └────────────┘  └──────────────┘
        │               │               │
        ▼               ▼               ▼
  ┌───────────┐  ┌────────────┐  ┌──────────────┐
  │   Game    │  │    Data    │  │  Game Data   │
  │ TypeChart │  │   Loader   │  │  (24MB JSON) │
  │   Stats   │  │  Scraper   │  │              │
  │ SkillEval │  │  Updater   │  │              │
  └───────────┘  └────────────┘  └──────────────┘
```

### 数据管线

```
Network Traffic (port 8195)
  │
  ▼ capture/sniffer.py — Scapy AsyncSniffer 编排
  │
  ├── capture/key_capture.py — 从 ACK 包提取 AES 会话密钥
  ├── capture/reassembly.py — TCP 流重组为有序数据流
  ├── capture/frame.py — BE21 帧解析（帧头 + 帧体提取）
  ├── capture/crypto.py — AES-128-CBC 解密
  │
  ▼ protocol/
  ├── proto_core.py — Protobuf 解析器、TGCP 传输、宠物/状态提取
  ├── opcodes.py — 装饰器注册的 opcode/inner-message 分发
  ├── battle.py — 战斗数据提取（Schema-first + Raw fallback 双策略）
  │
  ▼ analysis/
  ├── battle_state.py — 实时战斗状态机
  ├── battle_processor.py — 事件处理管线（状态 + 格式化 + 伤害 + hooks + 战术）
  ├── battle_advisor.py — 战斗分析协调器
  ├── damage_calc.py — 4 阶段 Hook 管线的伤害计算引擎
  ├── tactical_engine.py — 期望值加权的战术推荐引擎
  ├── innate_hooks.py — 先天技能伤害 Hook
  ├── event_formatter.py — 协议事件 → UI 格式化
  ├── hook_registry.py — 可扩展分析 Hook 系统 (ABC)
  ├── hooks/ — 默认 Hook 实现（对手追踪、能量监控、换宠建议）
  │
  ▼ api/ → WebSocket → 前端实时更新
```

### 协议解析

游戏使用自定义二进制协议：

- **BE21 帧格式** — 固定帧头标识魔数 + 长度 + 加密帧体
- **AES-128-CBC 加密** — 会话密钥从 TCP 三次握手的 ACK 包中提取
- **TGCP 传输层** — 4 种消息格式封装
- **Protobuf 载荷** — 类 Protobuf 编码的消息体，支持 schema-first 和 raw field 双策略解析

### 战斗生命周期

```
idle → selecting (0x1316 battle_enter)
     → resolving (0x131A round_start)
     → [action events: 0x1324, 0x130C, 0x13F4, ...]
     → [repeat per round]
     → finished (0x132C battle_finish)
```

---

## 快速开始

### 环境要求

- **操作系统** — Windows 10/11（抓包功能需要 Windows）
- **Python** 3.11+
- **Node.js** 18+
- **Npcap** — [下载地址](https://npcap.com/)（Scapy 抓包依赖，安装时勾选 "Install Npcap in WinPcap API-compatible Mode"）
- **洛克王国** 游戏客户端

### 安装步骤

```bash
# 1. 克隆仓库
git clone https://github.com/your-repo/raco-helper.git
cd raco-helper

# 2. 安装 Python 依赖
pip install -e .

# 3. 安装前端依赖
cd web
npm install
cd ..
```

### 启动项目

需要两个终端分别启动后端和前端：

**终端 1 — 启动后端 API 服务（端口 8000）**

```bash
py -m src.main
```

后端启动后会显示：
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
```

**终端 2 — 启动前端开发服务器（端口 5173）**

```bash
cd web
npm run dev
```

前端启动后会显示：
```
VITE v8.x.x  ready in xxx ms

➜  Local:   http://localhost:5173/
```

打开浏览器访问 **http://localhost:5173** 即可使用。

### 使用流程

1. 打开前端页面，进入「实时战斗」页面
2. 点击「启动监听」开始捕获网络流量
3. 点击「连接战斗」建立 WebSocket 连接
4. 在游戏中开始 PvP 对战
5. 工具自动捕获流量、解析协议、实时显示：
   - 双方阵容 HP/能量状态
   - 战斗事件时间线
   - 每个技能的伤害预测和 KO 判定
   - 战术推荐（最优技能选择、换宠建议）
   - 对手行为分析和能量窗口预警

### 回放测试

使用预录制的战斗数据测试，无需实际游戏：

```bash
# 无头回放（纯后端，终端输出）
py -m scripts.replay_headless --session battle_session_1

# 前端回放（需要先启动前后端服务）
py -m scripts.replay_to_frontend --delay 80 --session battle_session_1
```

---

## API 概览

### REST API

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/health` | GET | 健康检查 |
| `/api/pets` | GET | 宠物列表（分页、搜索、属性筛选） |
| `/api/pets/{id}` | GET | 宠物详情（含技能数据） |
| `/api/skills` | GET | 技能列表（分页、属性筛选） |
| `/api/skills/{id}` | GET | 技能详情 |
| `/api/types` | GET | 所有属性列表 |
| `/api/types/{id}/matchups` | GET | 属性克制关系（弱点/抗性/免疫） |
| `/api/teams/analyze` | POST | 队伍分析（覆盖率、角色、速度梯队、建议） |
| `/api/teams/counter` | POST | 查找最佳 counter 选择 |
| `/api/teams/suggest` | POST | 队友推荐 |
| `/api/teams/coverage` | POST | 攻防属性覆盖报告 |
| `/api/battle/state` | GET | 当前战斗状态快照 |
| `/api/battle/pets` | GET | 双方活跃宠物 |
| `/api/battle/effects` | GET | 当前 buff/debuff 和天气 |
| `/api/battle/replay` | POST | 回放战斗包到 WebSocket 客户端 |
| `/api/data/status` | GET | 已加载数据表统计 |
| `/api/data/refresh` | POST | 热重载数据文件 |
| `/api/sniffer/start` | POST | 启动网络监听 |
| `/api/sniffer/stop` | POST | 停止网络监听 |
| `/api/sniffer/status` | GET | 监听状态查询 |
| `/api/config/popular-skills` | GET | 所有热门技能预设 |
| `/api/config/popular-skills/{base_id}` | GET/PUT/DELETE | 宠物技能预设 CRUD |
| `/api/config/pets-with-skills` | GET | 宠物及可学习技能列表 |
| `/api/config/pets-with-skills/{base_id}/skills` | GET | 指定宠物可学习技能 |

### WebSocket

| 端点 | 推送消息类型 |
|------|-------------|
| `ws://localhost:8000/ws/battle` | `connected` · `state_update` · `battle_event(s)` · `battle_summary` · `skill_analysis` · `hook_advice` · `tactical_recommendations` · `suggestions` |
| `ws://localhost:8000/ws/monitor` | `status` · `record` · `key_captured` · `flow_closed` |

---

## 项目结构

```
raco-helper/
├── src/                          # Python 后端
│   ├── main.py                   # 应用入口 (uvicorn)
│   ├── capture/                  # 网络抓包层
│   │   ├── sniffer.py            # Scapy 异步嗅探器
│   │   ├── key_capture.py        # AES 密钥提取
│   │   ├── reassembly.py         # TCP 流重组
│   │   ├── frame.py              # BE21 帧解析
│   │   ├── crypto.py             # AES-128-CBC 解密
│   │   └── packet_logger.py      # 数据包日志
│   ├── protocol/                 # 协议解析层
│   │   ├── proto_core.py         # Protobuf 解析器
│   │   ├── opcodes.py            # Opcode 注册与分发
│   │   └── battle.py             # 战斗数据提取
│   ├── analysis/                 # 战斗分析层
│   │   ├── battle_state.py       # 战斗状态机
│   │   ├── battle_processor.py   # 事件处理管线
│   │   ├── battle_advisor.py     # 分析协调器
│   │   ├── damage_calc.py        # 伤害计算引擎
│   │   ├── tactical_engine.py    # 战术推荐引擎
│   │   ├── innate_hooks.py       # 先天技能 Hook
│   │   ├── event_formatter.py    # 事件格式化
│   │   ├── hook_registry.py      # Hook 系统 (ABC)
│   │   ├── hooks/                # 内置 Hook 实现
│   │   ├── coverage.py           # 属性覆盖率
│   │   ├── counter.py            # Counter-pick
│   │   ├── threat.py             # 威胁评估
│   │   ├── team_builder.py       # 队伍构建
│   │   └── replay_runner.py      # 无头回放器
│   ├── game/                     # 游戏机制
│   │   ├── type_chart.py         # 21 种属性克制矩阵
│   │   ├── stats.py              # 种族值/实数值计算
│   │   └── skill_eval.py         # 技能评分引擎
│   ├── api/                      # FastAPI 路由层
│   │   ├── app.py                # 应用工厂
│   │   ├── battle_manager.py     # 全局战斗管理器
│   │   ├── sniffer_manager.py    # 嗅探器管理
│   │   ├── routes_battle.py      # 战斗 WebSocket + REST
│   │   ├── routes_sniffer.py     # 抓包控制 API
│   │   ├── routes_teams.py       # 队伍分析 API
│   │   ├── routes_pets.py        # 宠物查询 API
│   │   └── routes_data.py        # 静态数据 API
│   └── data/                     # 数据加载
│       ├── loader.py             # 类型化数据访问（13 个 JSON 表）
│       ├── scraper.py            # BWIKI 数据爬取
│       └── updater.py            # 数据更新
├── web/                          # React 前端
│   ├── src/
│   │   ├── pages/                # 7 个页面组件
│   │   ├── components/           # UI 组件
│   │   │   ├── PetCard.tsx       # 宠物卡片
│   │   │   ├── TeamSlot.tsx      # 队伍槽位
│   │   │   ├── CoverageRadar.tsx # 覆盖率雷达图
│   │   │   ├── TypeBadge.tsx     # 属性徽章
│   │   │   ├── BattleTimeline.tsx    # 战斗时间线
│   │   │   ├── BattleEventLog.tsx    # 战斗事件日志
│   │   │   ├── BattleSummaryPanel.tsx # 战斗总结
│   │   │   ├── DamagePredictionPanel.tsx # 伤害预测面板
│   │   │   ├── SkillPanel.tsx        # 技能分析面板
│   │   │   ├── OpponentSkillPanel.tsx # 对手技能分析
│   │   │   ├── HookAdvicePanel.tsx    # Hook 建议面板
│   │   │   ├── TacticalPanel.tsx     # 战术推荐面板
│   │   │   └── TeamRoster.tsx        # 阵容状态
│   │   ├── stores/               # Zustand 状态管理
│   │   ├── hooks/                # React Hooks
│   │   └── utils/                # 工具函数
│   └── package.json
├── data/                         # 数据目录
│   ├── game/                     # 静态游戏数据 (~24MB JSON)
│   │   ├── pet_map.json          # 宠物定义
│   │   ├── skill_map.json        # 技能定义
│   │   ├── pet_skill_map.json    # 宠物-技能映射
│   │   ├── type_chart.json       # 属性克制矩阵
│   │   ├── proto_schema.json     # Protobuf 消息 schema
│   │   ├── opcode_pb_map.json    # Opcode-消息映射
│   │   ├── buff_map.json         # Buff 定义
│   │   ├── innate_skills.json    # 先天技能定义
│   │   └── ...
│   └── config/                   # 用户配置
│       └── popular_skills.json   # 热门技能预设
├── tests/                        # 测试套件 (717 测试 / 31 文件)
├── scripts/                      # 辅助脚本
│   ├── replay_headless.py        # 无头回放
│   ├── replay_to_frontend.py     # 前端回放
│   ├── extract_battle.py         # 战斗提取
│   ├── generate_battle_report.py # 战斗报告
│   ├── update_data.py            # 数据更新
│   ├── import_wiki_skills.py     # Wiki 技能导入
│   └── ...
├── references/                   # 参考仓库
│   ├── Roco-Kingdom-Protocol-Parser/  # 协议解析参考
│   ├── Roco-Kingdom-World-Data/       # 游戏完整解包数据
│   └── NRC_AI/                        # 战斗 AI 模拟器
└── docs/                         # 文档
```

---

## 测试

```bash
# 运行全部测试（自动并行）
pytest

# 运行指定测试文件
pytest tests/test_crypto.py

# 按名称筛选
pytest -k "test_damage_calc"

# 详细输出
pytest -v
```

测试套件包含 **717 个测试**，覆盖 31 个测试文件，涵盖：
- 协议解析（opcode、帧解析、加密、技能/属性提取）
- 游戏机制（属性克制表、种族值、技能评分）
- 战斗状态（状态机、事件格式化、回放）
- 伤害计算（伤害引擎、先天技能 hook、集成测试）
- 分析 Hook（注册表、对手追踪、能量监控、换宠建议）
- 策略分析（counter、覆盖率、队伍构建、威胁评估）
- API 端点（REST、WebSocket、回放）
- 数据加载

所有测试使用真实数据，不使用 mock。

---

## 技术栈

### 后端

| 组件 | 技术 |
|------|------|
| Web 框架 | FastAPI |
| ASGI 服务器 | Uvicorn（支持热重载） |
| 网络抓包 | Scapy |
| 加密解密 | PyCryptodome (AES-128-CBC) |
| HTTP 客户端 | HTTPX |
| 数据爬取 | BeautifulSoup4 |
| 测试 | pytest + pytest-xdist（并行） |

### 前端

| 组件 | 技术 |
|------|------|
| 框架 | React 19 |
| 类型系统 | TypeScript |
| UI 组件库 | Ant Design 6 |
| 状态管理 | Zustand 5 |
| 路由 | React Router 7 |
| 构建工具 | Vite 8 |
| HTTP 客户端 | Axios |

---

## 核心设计理念

### 双提取策略

`battle.py` 中所有主要提取器使用双策略：

1. **Schema-first** — 通过 `proto_schema.json` 定义解码，提供类型安全的结构化访问
2. **Raw fallback** — 当 schema 不可用时，手动解析 protobuf 字段

两条路径产出相同的输出结构，`_schema_quality()` 辅助函数标记解析质量。

### 双 Hook 系统

**1. 伤害计算 Hook** (`damage_calc.py`) — 4 阶段管线，修改伤害计算：

```
pre_power → post_base → pre_final → post_calc
```

先天技能 Hook (`innate_hooks.py`) 注册在 `post_base`（属性修改）、`pre_final`（属性抵抗）、`post_calc`（连击/威力修正）阶段。

**2. 分析 Hook** (`hook_registry.py`) — ABC 驱动的事件 Hook，在战斗生命周期节点触发：

```
ON_BATTLE_ENTER → ON_ROUND_START → ON_ACTION_RESOLVE → ON_SPECIAL_REFRESH → ON_BATTLE_FINISH → ON_CHANGE_PET → ON_DEFEAT
```

### WebSocket 推送架构

`BattleManager` 作为全局单例，通过 Sniffer Bridge 将网络层捕获的 TGCP DATA 包解码后，经过完整的分析管线（状态追踪 → 事件格式化 → 伤害预测 → 战术推荐 → Hook 分析 → WebSocket 推送），实现端到端实时更新。

### 对手技能推断（3 级回退）

对手装备技能不可直接获取，使用 3 级回退策略：
1. **协议数据** — 从战斗包中提取的已使用技能
2. **累积已用技能** — 对战中逐步累积的 `used_skills`
3. **热门预设** — 从 `popular_skills.json` 获取社区常用配置

---

## 数据来源

游戏数据来自多个来源，按权威性排序：

1. **官方解包数据** (`references/Roco-Kingdom-World-Data/`) — 游戏本地配置文件，最权威
2. **Wiki 爬取** (`src/data/scraper.py`) — 游戏 BWIKI 数据，作为补充
3. **内置数据** (`data/game/`) — 预处理的 JSON 数据文件

### 核心数据文件

| 文件 | 大小 | 描述 |
|------|------|------|
| `pet_map.json` | 706K | 700+ 宠物定义（ID、名字、种族值、属性） |
| `skill_map.json` | 1.2M | 技能定义（威力、属性、能量消耗、目标类型） |
| `pet_skill_map.json` | — | 宠物-技能映射关系 |
| `type_chart.json` | 2.8K | 21 种属性克制矩阵 |
| `proto_schema.json` | 3.1M | Protobuf 消息 schema 定义 |
| `opcode_pb_map.json` | 315K | Opcode 到 Protobuf 消息的映射 |
| `buff_map.json` | 891K | Buff/效果定义 |
| `innate_skills.json` | 4.5K | 先天技能定义（用于伤害 Hook） |

---

## 参考项目

| 项目 | 描述 |
|------|------|
| [Roco-Kingdom-Protocol-Parser](https://github.com/LeiHaoQiao/Roco-Kingdom-Protocol-Parser) | 洛克王国战斗协议解析器，协议解析的主要参考 |
| [Roco-Kingdom-World-Data](https://github.com/LeiHaoQiao/Roco-Kingdom-World-Data) | 游戏完整解包数据，676 个 JSON 配置 + 64 个 protobuf 定义 |
| [NRC_AI](https://github.com/ngrc6/nrc_ai) | 洛克王国战斗 AI 模拟器，100+ 效果原语的效果引擎参考 |

---

## License

本项目仅供学习和研究使用。
