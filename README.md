# Roco PvP Helper

洛克王国 PvP 实时战斗分析与辅助决策工具。它被动监听游戏 8195 端口流量，解析 BE21 协议与战斗消息，在 Web 页面中展示双方状态、伤害预测、速度/能量变化和战术建议。

## 免责声明

本项目仅供学习、研究和技术交流使用，用于理解网络协议解析、被动流量分析、实时状态建模、前后端数据展示等工程技术，不得用于任何违反法律法规、游戏用户协议、平台规则或损害他人权益的用途。

请在使用前充分理解并自行承担以下风险：

- **非官方项目**：本项目与洛克王国、腾讯、魔方工作室群及其关联方没有任何隶属、授权、认可或合作关系。项目中提到的游戏名称、角色、技能、数据和相关标识，其权利归原权利人所有。
- **仅被动分析**：本工具设计为只读取和解析本机网络流量，**不会向游戏服务器发送任何数据包**，不会修改客户端、读取或写入游戏内存、注入进程、自动点击、自动操作或代替玩家执行任何游戏行为。
- **禁止违规使用**：不得将本项目用于外挂、作弊、自动化对战、牟利服务、破坏游戏公平性、绕过安全机制、攻击服务器、批量抓取、传播未授权数据或其他任何不当用途。
- **遵守规则与法律**：使用者应自行确认所在地法律法规、游戏服务条款、账号规则和网络安全要求。若游戏运营方或相关权利方认为此类工具不应使用，请立即停止使用并删除相关数据。
- **账号与环境风险**：即使工具本身为被动监听，抓包、协议分析或辅助决策展示仍可能被平台规则视为不被允许的行为。由此导致的账号限制、封禁、数据损失、系统异常或其他后果，均由使用者自行承担。
- **数据来源与准确性**：项目内置数据、协议解析结果、伤害预测和战术建议仅供参考，可能存在版本滞后、解析错误、计算偏差或不完整情况，不构成任何确定性承诺。
- **无担保责任**：本项目按现状提供，不提供任何明示或暗示担保。维护者不对因使用、修改、分发或依赖本项目产生的任何直接或间接损失承担责任。
- **二次分发责任**：如基于本项目进行修改、分发、部署或演示，应保留本免责声明，并确保你的使用场景同样仅限学习研究，不得诱导或帮助他人进行违规行为。

## 核心特性

- **实时战斗状态**：追踪双方阵容、当前上场宠物、HP、能量、buff/debuff、天气、回合与胜负结果。
- **伤害与 KO 预测**：基于属性克制、技能威力、STAB、天气、先天技能等信息预测技能伤害和击杀线。
- **速度与能量判断**：从战斗协议中提取双方速度基础值，结合战斗状态提示出手顺序和能量窗口。
- **战术与换宠建议**：提供属性不利提醒、低血量/低能量提示、counter-pick 和换宠建议。
- **对手行为分析**：记录对手已使用技能、换宠模式和能量变化，辅助判断下一步风险。
- **回放验证**：支持使用预录战斗包进行无头回放或推送到前端重放，无需实际进入游戏。
- **资料与队伍工具**：内置宠物浏览、技能数据、属性克制表、队伍构建和覆盖率分析页面。

## 快速启动

### 环境要求

- **Windows 10/11**：生产运行和抓包以 Windows 为基准。
- **Python 3.9+**：Windows 上使用 `py` 启动。
- **Node.js 18+**：用于运行 Vite 前端。
- **Npcap**：Scapy 抓包依赖，安装时建议勾选 `Install Npcap in WinPcap API-compatible Mode`。
- **洛克王国客户端**：实时抓包分析需要游戏客户端正在运行。

### 安装依赖

```bash
py -m pip install -e .
cd web
npm install
cd ..
```

### 推荐启动方式

Windows 下可以直接运行：

```bash
start.bat
```

脚本会清理已占用的 `18731` 和 `18732` 端口，并分别启动后端和前端窗口。

### 手动启动方式

如果希望手动控制服务，打开两个终端：

```bash
# 终端 1：后端 API 服务，默认端口 18731
py -m src.main
```

```bash
# 终端 2：前端开发服务器，默认端口 18732
cd web
npm run dev
```

启动后访问：

```text
http://localhost:18732
```

### 首次使用流程

1. 以管理员权限启动后端，确保 Npcap 已正确安装。
2. 打开 `http://localhost:18732/battle`。
3. 点击「连接战斗」，建立 WebSocket 连接。
4. 点击「启动监听」，开始捕获游戏端口流量。
5. 在洛克王国客户端中开始 PvP 对战。
6. 前端会实时显示双方状态、事件时间线、伤害预测、战术建议和 Hook 分析。

## 无游戏验证

项目内置了预录制战斗包，可以在没有游戏客户端的情况下验证后端分析和前端展示。

```bash
# 纯后端无头回放：输出每回合事件、预测、建议和最终状态
py -m scripts.replay_headless --session battle_session_1

# 前端回放：需要先启动后端和前端，并在 /battle 页面点击「连接战斗」
py -m scripts.replay_to_frontend --delay 80 --session battle_session_1
```

更多回放参数、指定回合停止和 API 调用方式见 [战斗回放指南](docs/replay_guide.md)。

### `.raco-report` 导入导出

`.raco-report` 是可分享的战斗抓包包，内部保留原始 RC01 `.bin` 文件和少量 manifest 元数据，不包含预生成分析结果。

```bash
# 导入报告为普通抓包目录，并验证能否完整回放
py -m scripts.unpack_battle_report path\to\battle.raco-report --output tmp\report_packets --verify

# 收到用户报告后，一条命令生成文本报告和结构化分析
py -m scripts.analyze_battle_report path\to\battle.raco-report --output tmp\received_reports
```

导出通过战斗报告 API 或前端历史页面完成；导入、导出和包结构详见 [战斗回放指南](docs/replay_guide.md#raco-report-导入导出)。

## 功能概览

### 实时战斗

- 被动监听游戏网络流量，自动完成 TCP 流重组、BE21 帧解析、AES-128-CBC 解密和 opcode 分发。
- 维护完整战斗状态机，覆盖战斗开始、回合开始、行动结算、换宠、特殊刷新和战斗结束。
- 将协议事件格式化为前端可读事件，例如技能释放、伤害、治疗、击败、能量变化、buff 变化和天气变化。

### 战斗分析

- 对我方装备技能生成伤害预测、属性克制标签、连击总伤害和 KO 判定。
- 使用可扩展的伤害 Hook 处理先天技能、威力修正、属性抵抗、连击和减伤效果。
- 通过分析 Hook 提供对手行为追踪、能量监控、攻击窗口识别和换宠建议。

### 策略工具

- 属性克制矩阵查询，支持弱点、抗性、免疫和倍率查看。
- Counter-pick 推荐，综合进攻效果、防御抗性、技能覆盖和速度优势。
- 队伍构建分析，展示覆盖率、共同弱点、速度梯队和队友推荐。
- 宠物与技能浏览，基于 `data/game/` 的静态游戏数据。

### 回放与报告

- `scripts.replay_headless`：纯后端回放，用于快速验证战斗分析。
- `scripts.replay_to_frontend`：将预录包推送到前端 WebSocket，模拟实时战斗。
- `scripts.extract_battle`：从抓包 session 中提取战斗 fixture，详见 [战斗包提取文档](docs/extract_battle.md)。
- `scripts.generate_battle_report`：生成格式化战斗报告。
- `scripts.unpack_battle_report`：导入 `.raco-report`，还原为可完整回放的抓包目录。
- `scripts.analyze_battle_report`：导入用户发来的 `.raco-report`，生成 `battle_report.txt` 和 `analysis.json`。

## 技术架构

```text
洛克王国客户端 TCP :8195
        |
        v
capture/
  Scapy 抓包 -> TCP 重组 -> BE21 帧解析 -> AES 解密
        |
        v
protocol/
  TGCP/Protobuf 解析 -> opcode 分发 -> 战斗语义提取
        |
        v
analysis/
  状态追踪 -> 事件格式化 -> 伤害预测 -> 战术建议 -> Hook 分析
        |
        v
api/
  FastAPI REST + WebSocket
        |
        v
web/
  React + Ant Design + Zustand 实时展示
```

详细原理见 [架构说明](docs/architecture.md)、[实时战斗功能：原理与用法](docs/realtime-battle.md) 和 [战斗分析指南](docs/battle_analysis_guide.md)。

### 主要目录

| 路径 | 说明 |
|------|------|
| `src/capture/` | 抓包、TCP 重组、BE21 帧解析、AES 解密和密钥提取 |
| `src/protocol/` | Protobuf/TGCP 解析、opcode 分发、战斗字段提取；`battle.py` 保留兼容门面 |
| `src/analysis/` | 战斗状态机、伤害预测、事件格式化、Hook 分析、战术推荐和回放 runner |
| `src/api/` | FastAPI 应用、REST 路由、WebSocket、抓包管理和回放 service |
| `src/game/` | 属性克制、种族值计算、技能评分等游戏机制 |
| `web/` | React 19 + TypeScript + Ant Design 6 前端 |
| `data/game/` | 宠物、技能、属性、buff、协议 schema 等静态数据 |
| `scripts/` | 回放、战斗提取、报告生成和数据导入脚本 |
| `docs/` | 更详细的使用、协议、回放和分析文档 |

## API 概览

### REST

| 端点 | 说明 |
|------|------|
| `GET /api/health` | 健康检查 |
| `GET /api/battle/state` | 当前战斗状态快照 |
| `GET /api/battle/pets` | 双方战斗宠物列表与 active 宠物 |
| `GET /api/battle/effects` | 当前天气、阶段和双方 buff 摘要 |
| `POST /api/battle/replay` | 将预录战斗包回放到 WebSocket 客户端 |
| `GET /api/battle/reports` | 列出可下载的 `.raco-report` |
| `GET /api/battle/reports/{report_id}` | 获取单个报告元数据 |
| `GET /api/battle/reports/{report_id}/download` | 下载 `.raco-report` 原始抓包包 |
| `POST /api/sniffer/start` / `POST /api/sniffer/stop` | 启动或停止网络监听 |
| `GET /api/sniffer/status` | 查询监听状态 |
| `GET /api/config/popular-skills` | 热门技能预设 |
| `GET /api/config/pets-with-skills` | 可按技能查询的宠物索引 |

### WebSocket

| 端点 | 说明 |
|------|------|
| `/ws/battle` | 实时战斗状态、事件、技能分析、Hook 建议和结算摘要 |
| `/api/sniffer/ws/monitor` | 抓包监听状态推送 |
## 常用命令

```bash
# 后端
py -m src.main

# 前端
cd web
npm run dev

# 前端构建
cd web
npm run build

# 运行全部测试
pytest

# 运行单个测试文件
pytest tests/test_crypto.py

# 按名称筛选测试
pytest -k "test_damage_calc"

# 无头回放
py -m scripts.replay_headless --session battle_session_1

# 前端回放
py -m scripts.replay_to_frontend --delay 80 --session battle_session_1
```

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.9+、FastAPI、Uvicorn、Scapy、PyCryptodome |
| 前端 | React 19、TypeScript、Ant Design 6、Zustand、Vite 8、React Router 7 |
| 协议 | BE21 二进制帧、AES-128-CBC、TGCP、类 Protobuf 载荷 |
| 测试 | pytest、pytest-xdist、真实抓包 fixture |

## 数据来源

静态数据位于 `data/game/`，由游戏 BinData 解包数据导入并预处理，主要包括：

| 文件 | 说明 |
|------|------|
| `pet_map.json` | 宠物定义、名称、种族值、属性 |
| `skill_map.json` | 技能定义、威力、属性、能量消耗、目标类型 |
| `pet_skill_map.json` | 宠物与可学习技能映射 |
| `type_chart.json` | 属性克制矩阵 |
| `proto_schema.json` | Protobuf 消息 schema |
| `opcode_pb_map.json` | opcode 到 protobuf 消息映射 |
| `buff_map.json` / `buffbase_map.json` | Buff 与效果定义 |
| `innate_skills.json` | 先天技能定义，用于伤害 Hook |

参考数据和协议项目已放在 `references/`：

| 项目 | 用途 |
|------|------|
| [Roco-Kingdom-Protocol-Parser](https://github.com/LeiHaoQiao/Roco-Kingdom-Protocol-Parser) | 战斗协议解析参考 |
| [Roco-Kingdom-World-Data](https://github.com/LeiHaoQiao/Roco-Kingdom-World-Data) | 游戏完整解包数据参考 |
| [NRC_AI](https://github.com/ngrc6/nrc_ai) | 战斗 AI 与效果引擎参考 |

## 测试与验证

```bash
pytest
```

测试覆盖协议解析、抓包帧处理、游戏机制、战斗状态、伤害计算、分析 Hook、策略分析、API 和回放流程。所有核心测试使用真实数据与预录抓包 fixture。

对于只修改文档的任务，不需要运行完整测试；建议至少检查 Markdown 链接和命令是否仍然有效。

## License

本项目仅供学习和研究使用。使用、修改或分发前请务必阅读并遵守上方免责声明。
