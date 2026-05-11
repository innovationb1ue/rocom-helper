# Roco PvP Helper (洛克王国 PvP 辅助工具)

实时战斗分析与辅助决策工具，专为洛克王国 PvP 对战设计。通过被动抓取游戏网络流量（端口 8195），解密自定义 BE21 协议，实时追踪战斗状态，并提供属性克制分析、伤害预测、换宠建议等辅助决策。

> **声明：** 本工具为纯被动读取，仅解析网络流量，**不会向游戏服务器发送任何数据包**。

---

## 功能概览

### 实时战斗追踪

- **被动网络监听** — 基于 Scapy 抓取端口 8195 的游戏流量，提取 AES 会话密钥，自动解密 BE21 协议帧
- **战斗状态机** — 完整追踪 HP、能量、buff/debuff、回合数、宠物切换等战斗状态
- **伤害预测** — 实时计算我方所有技能对敌方宠物的预期伤害，支持连击、属性克制、STAB 等修正
- **先天技能 Hook** — 可扩展的 4 阶段伤害计算管线（pre_power → post_base → pre_final → post_calc），支持连击、属性抵抗、威力修正等

### 战术分析

- **属性克制表** — 18 种属性间的克制/抵抗/免疫关系查询
- **Counter-Pick 推荐** — 基于属性克制关系推荐最佳换宠选择
- **覆盖率分析** — 计算队伍的攻防属性覆盖雷达图
- **威胁评估** — 对敌方宠物进行综合威胁打分
- **队伍构建** — 根据属性覆盖和协同性推荐队伍配置

### 分析 Hook 系统

基于事件驱动的可扩展 Hook 系统，在战斗生命周期关键节点触发：

- **对手行为追踪** — 记录对手技能使用和换宠模式
- **能量监控** — 检测对手能量窗口，预判攻击时机
- **换宠建议** — 基于属性优劣势推荐换宠时机

### 前端界面

6 个功能页面，使用 Ant Design 组件库：

| 页面 | 功能 |
|------|------|
| 仪表盘 | 数据总览和快速入口 |
| 精灵 | 700+ 宠物数据浏览、筛选、种族值查看 |
| 队伍 | 可视化队伍构建与覆盖率分析 |
| 克制表 | 18 种属性交互关系矩阵 |
| 实时战斗 | WebSocket 驱动的实时战斗面板（状态、事件流、伤害预测、建议） |
| 历史 | 战斗回放与历史记录查看 |

---

## 技术架构

```
┌─────────────────────────────────────────────────────┐
│                   React SPA (Vite)                   │
│   Zustand Stores · Ant Design 6 · React Router 7     │
└──────────────────────┬──────────────────────────────┘
                       │ WebSocket + REST API
┌──────────────────────┴──────────────────────────────┐
│                  FastAPI Backend                      │
│  BattleManager (Singleton) · SnifferManager · Routes │
└──────────────────────┬──────────────────────────────┘
                       │
       ┌───────────────┼───────────────┐
       ▼               ▼               ▼
   Analysis          Protocol        Capture
 ┌───────────┐  ┌────────────┐  ┌──────────────┐
 │BattleState│  │ Proto Core │  │  Scapy Sniffer│
 │DamageCalc │  │ Opcodes    │  │  TCP Reassembly│
 │InnatHooks │  │ Battle Ext │  │  BE21 Frame   │
 │Advisor    │  │            │  │  AES Decrypto │
 │Hooks/...  │  │            │  │  Key Capture  │
 └───────────┘  └────────────┘  └──────────────┘
       │               │               │
       ▼               ▼               ▼
 ┌───────────┐  ┌────────────┐  ┌──────────────┐
 │  Game     │  │   Data     │  │  Game Data   │
 │TypeChart  │  │  Loader    │  │  (24MB JSON) │
 │Stats      │  │  Scraper   │  │              │
 │SkillEval  │  │  Updater   │  │              │
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
  ├── battle_advisor.py — 战斗分析协调器
  ├── damage_calc.py — 4 阶段 Hook 管线的伤害计算引擎
  ├── innate_hooks.py — 先天技能伤害 Hook
  ├── event_formatter.py — 协议事件 → UI 格式化
  ├── hook_registry.py — 可扩展分析 Hook 系统 (ABC)
  ├── hooks/ — 默认 Hook 实现
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

- **Python** 3.11+
- **Node.js** 18+
- **Windows**（Scapy 抓包需要 WinPcap/Npcap）
- **洛克王国** 游戏客户端

### 安装

```bash
# 克隆仓库
git clone https://github.com/your-repo/raco-helper.git
cd raco-helper

# 安装 Python 依赖
pip install -e .

# 安装前端依赖
cd web
npm install
```

### 启动

```bash
# 终端 1 — 启动后端 API 服务（端口 8000）
py -m src.main

# 终端 2 — 启动前端开发服务器（端口 5173）
cd web && npm run dev
```

打开浏览器访问 `http://localhost:5173`。

### 使用流程

1. 在「实时战斗」页面启动网络监听
2. 连接 WebSocket 接收战斗数据
3. 进入游戏开始 PvP 对战
4. 工具自动捕获流量、解析协议、实时显示战斗状态和建议

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
│   │   ├── battle_advisor.py     # 分析协调器
│   │   ├── damage_calc.py        # 伤害计算引擎
│   │   ├── innate_hooks.py       # 先天技能 Hook
│   │   ├── event_formatter.py    # 事件格式化
│   │   ├── hook_registry.py      # Hook 系统 (ABC)
│   │   ├── hooks/                # 内置 Hook 实现
│   │   ├── coverage.py           # 属性覆盖率
│   │   ├── counter.py            # Counter-pick
│   │   ├── threat.py             # 威胁评估
│   │   └── team_builder.py       # 队伍构建
│   ├── game/                     # 游戏机制
│   │   ├── type_chart.py         # 18 种属性克制矩阵
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
│       ├── loader.py             # 类型化数据访问
│       ├── scraper.py            # Wiki 数据爬取
│       └── updater.py            # 数据更新
├── web/                          # React 前端
│   ├── src/
│   │   ├── pages/                # 页面组件
│   │   │   ├── Dashboard.tsx     # 仪表盘
│   │   │   ├── PetBrowser.tsx    # 宠物浏览
│   │   │   ├── TeamBuilder.tsx   # 队伍构建
│   │   │   ├── TypeChart.tsx     # 属性克制表
│   │   │   ├── BattleLive.tsx    # 实时战斗
│   │   │   └── BattleHistory.tsx # 战斗历史
│   │   ├── components/           # UI 组件
│   │   ├── stores/               # Zustand 状态管理
│   │   ├── hooks/                # React Hooks
│   │   └── utils/                # 工具函数
│   └── package.json
├── data/game/                    # 静态游戏数据 (~24MB JSON)
│   ├── pet_map.json              # 宠物定义 (ID/名字/种族值/属性)
│   ├── skill_map.json            # 技能定义 (威力/属性/能量/目标)
│   ├── pet_skill_map.json        # 宠物-技能映射
│   ├── type_chart.json           # 18 种属性克制矩阵
│   ├── buff_map.json             # Buff/效果定义
│   ├── buffbase_map.json         # 基础 Buff 定义
│   ├── proto_schema.json         # Protobuf 消息 schema
│   ├── opcode_pb_map.json        # Opcode-消息映射
│   ├── innate_skills.json        # 先天技能定义
│   └── ...
├── tests/                        # 测试套件 (530+ 测试 / 45 文件)
├── references/                   # 参考仓库
│   ├── Roco-Kingdom-Protocol-Parser/  # 协议解析参考
│   └── Roco-Kingdom-World-Data/       # 游戏完整解包数据
└── scripts/                      # 辅助脚本 (回放等)
```

---

## API 概览

### REST API

| 端点 | 描述 |
|------|------|
| `GET /api/health` | 健康检查 |
| `GET /api/pets` | 宠物列表查询（支持筛选、搜索、分页） |
| `GET /api/pets/{id}` | 单个宠物详情 |
| `GET /api/teams/analyze` | 队伍属性覆盖率和协同分析 |
| `GET /api/teams/suggest` | 队伍构建推荐 |
| `GET /api/data/{path}` | 静态游戏数据 |
| `POST /api/sniffer/start` | 启动网络监听 |
| `POST /api/sniffer/stop` | 停止网络监听 |
| `GET /api/sniffer/status` | 监听状态查询 |

### WebSocket

| 端点 | 消息类型 |
|------|---------|
| `ws://localhost:8000/ws/battle` | `connected` · `state_update` · `battle_event` · `battle_summary` · `skill_analysis` · `hook_advice` · `suggestions` |

### 回放 API

| 端点 | 描述 |
|------|------|
| `POST /api/battle/replay/{session}` | 回放指定战斗会话 |
| `GET /api/battle/replay/sessions` | 列出可用回放会话 |

---

## 测试

```bash
# 运行全部测试
pytest

# 运行指定测试文件
pytest tests/test_crypto.py

# 按名称筛选
pytest -k "test_damage_calc"

# 运行并显示详细输出
pytest -v
```

测试套件包含 **530+ 测试**，覆盖协议解析、游戏机制、战斗状态、伤害计算、分析 Hook、策略推荐、API 端点等全部模块。所有测试使用真实数据，不使用 mock。

---

## 技术栈

### 后端

| 组件 | 技术 |
|------|------|
| Web 框架 | FastAPI |
| ASGI 服务器 | Uvicorn |
| 网络抓包 | Scapy |
| 加密解密 | PyCryptodome (AES-128-CBC) |
| HTTP 客户端 | HTTPX |
| 数据爬取 | BeautifulSoup4 |

### 前端

| 组件 | 技术 |
|------|------|
| 框架 | React 19 |
| 类型系统 | TypeScript |
| UI 组件库 | Ant Design 6 |
| 状态管理 | Zustand 5 |
| 路由 | React Router 7 |
| 构建工具 | Vite 8 |

---

## 核心设计理念

### 双提取策略

`battle.py` 中所有主要提取器使用双策略：

1. **Schema-first** — 通过 `proto_schema.json` 定义解码，提供类型安全的结构化访问
2. **Raw fallback** — 当 schema 不可用时，手动解析 protobuf 字段

两条路径产出相同的输出结构，`_schema_quality()` 辅助函数标记解析质量。

### 双 Hook 系统

项目有两套独立的 Hook 系统，服务于不同目的：

**1. 伤害计算 Hook** (`damage_calc.py`) — 4 阶段管线，修改伤害计算：

```
pre_power → post_base → pre_final → post_calc
```

先天技能 Hook (`innate_hooks.py`) 注册在 `post_base`（属性修改）、`pre_final`（属性抵抗）、`post_calc`（连击/威力修正）阶段。

**2. 分析 Hook** (`hook_registry.py`) — ABC 驱动的事件 Hook，在战斗生命周期节点触发：

```
ON_BATTLE_ENTER → ON_ROUND_START → ON_ACTION_RESOLVE → ON_SPECIAL_REFRESH → ON_BATTLE_FINISH
```

### WebSocket 推送架构

`BattleManager` 作为全局单例，通过 Sniffer Bridge 将网络层捕获的 TGCP DATA 包解码后，经过完整的分析管线（状态追踪 → 事件格式化 → 战术分析 → WebSocket 推送），实现端到端实时更新。

---

## 数据来源

游戏数据来自多个来源，按权威性排序：

1. **官方解包数据** (`references/Roco-Kingdom-World-Data/`) — 游戏本地配置文件，最权威
2. **Wiki 爬取** (`src/data/scraper.py`) — 游戏 Wiki 数据，作为补充
3. **内置数据** (`data/game/`) — 预处理的 JSON 数据文件

### 核心数据文件

| 文件 | 大小 | 描述 |
|------|------|------|
| `pet_map.json` | 706K | 700+ 宠物定义（ID、名字、种族值、属性） |
| `skill_map.json` | 1.2M | 技能定义（威力、属性、能量消耗、目标类型） |
| `pet_skill_map.json` | — | 宠物-技能映射关系 |
| `type_chart.json` | 2.8K | 18 种属性克制矩阵 |
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
