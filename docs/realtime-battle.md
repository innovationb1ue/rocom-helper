# 实时战斗功能：原理与用法

## 一、功能定位

实时战斗功能是一个**被动监听式战斗状态显示器**。它通过捕获洛克王国游戏客户端的网络流量，实时解析战斗协议，在 Web 前端展示战斗双方的状态（HP、能量、精灵信息等）并提供基本战术建议。

**它不做的事情：**
- 不控制游戏（不点击、不发送指令、不修改游戏数据）
- 不读取屏幕或内存
- 不调用游戏 API
- 不自动战斗

---

## 二、工作原理

### 整体架构

```
┌─────────────┐    TCP :8195     ┌──────────────────┐
│ 洛克王国客户端 │ ──────────────→ │   网络抓包层       │
│ (游戏进程)    │                 │  (Scapy Sniffer)  │
└─────────────┘                 └────────┬───────────┘
       │                                 │ TCP 流重组
       │                                 │ BE21 帧解析
       │                                 │ AES 解密
       │                                 ↓
       │                        ┌──────────────────┐
       │                        │   协议解析层       │
       │                        │ (Opcode 分发)      │
       │                        └────────┬───────────┘
       │                                 │ 战斗事件
       │                                 ↓
       │                        ┌──────────────────┐
       │                        │   状态追踪层       │
       │                        │ (BattleStateTracker)│
       │                        └────────┬───────────┘
       │                                 │ WebSocket
       │                                 ↓
       │                        ┌──────────────────┐
       └────────────────────────│   Web 前端        │
          用户在游戏中操作         │ (BattleLive 页面)  │
                                 └──────────────────┘
```

### 2.1 网络抓包层

**文件：** `src/capture/sniffer.py`

使用 **Scapy** 的 `AsyncSniffer` 在本机网卡上捕获目标端口为 **8195**（洛克王国默认通信端口）的 TCP 流量。

```python
# BPF 过滤器，只捕获游戏流量
filter = "tcp port 8195"
```

抓到的每个 TCP 包通过源/目的端口判断方向：
- `c2s`（客户端→服务器）：玩家发送的选技能、换宠等指令
- `s2c`（服务器→客户端）：服务器推送的战斗结算、状态更新等

### 2.2 TCP 流重组

**文件：** `src/capture/reassembly.py`

TCP 传输不保证包按序到达，且可能重传。`FlowState` 维护双向的 TCP 流状态：
- 按 `seq` 号排序乱序段
- 去重重传数据
- 将碎片化的 TCP 段重组为连续字节流

### 2.3 BE21 协议帧解析

**文件：** `src/capture/frame.py`

游戏使用自定义的 **BE21 协议** 封装数据。帧格式：

```
┌──────┬──────────┬──────────┬──────────┬──────────┬─────────────┐
│ Magic│ ...      │ CMD (2B) │ SEQ (4B) │ HDR_LEN  │ BODY_LEN    │
│ 3366 │          │ 偏移+6   │ 偏移+9   │ (4B)     │ (4B)        │
├──────┴──────────┴──────────┴──────────┴──────────┴─────────────┤
│ Header Extra (HDR_LEN - 21 bytes)                               │
├─────────────────────────────────────────────────────────────────┤
│ Body (BODY_LEN bytes)                                           │
└─────────────────────────────────────────────────────────────────┘
```

- **Magic**：`0x3366`，用于定位帧头
- **CMD**：命令类型（如 `0x1002`=ACK, `0x4013`=DATA）
- **SEQ**：序列号
- 固定头部 21 字节

解析器从缓冲区中逐个提取完整的 BE21 帧。

### 2.4 AES 密钥提取

**文件：** `src/capture/key_capture.py`、`src/capture/crypto.py`

游戏流量使用 **AES-128-CBC** 加密。密钥来源：

1. 监听 `0x1002`（ACK）帧
2. 从帧的 `header_extra` 字段的第 2~18 字节提取 16 字节密钥
3. 密钥写入 `session_key.txt`，支持手动预设

```python
# 密钥位于 ACK 帧的 header_extra[2:18]
key = packet.header_extra[2:18]
```

对 `0x4013`（DATA）帧进行解密：
```python
iv = body[:16]           # 前 16 字节为 IV
ciphertext = body[16:]   # 其余为密文
plaintext = AES_CBC(key, iv, ciphertext)
```

### 2.5 协议解析层

**文件：** `src/protocol/proto_core.py`、`src/protocol/opcodes.py`、`src/protocol/battle.py`

解密后的数据为 Protobuf 编码的游戏协议。系统通过 **opcode**（操作码）分发到对应的解析函数。

#### 核心 Opcode 映射表

| Opcode | 方向 | 含义 | 解析函数 |
|--------|------|------|---------|
| `0x0102` | s2c | 精灵阵容初始化 | `extract_0102_creatures` |
| `0x1316` | s2c | 战斗开始 | `extract_1316_enter` |
| `0x131A` | s2c | 回合开始 | `extract_131a_round_start` |
| `0x130B` | c2s | 客户端选技能 | `extract_130b_skill_select` |
| `0x1322` | s2c | 服务器技能声明 | `extract_1322_skill_declare` |
| `0x1324` | s2c | 动作结算（伤害/效果/击杀） | `extract_1324_action` |
| `0x13F4` | s2c | 特殊刷新（能量瓶等） | `extract_13f4_refresh` |
| `0x132C` | s2c | 战斗结束 | `extract_132c_finish` |
| `0x1312` | s2c | 回合流程通知 | `extract_1312_round_flow` |
| `0x13FC` | s2c | PVP 结算 | `extract_13fc_pvp_perform` |
| `0x13F3` | s2c | 预演 | `extract_13f3_preplay` |
| `0x130C` | s2c | 服务器动作确认 | `extract_130c_result` |

#### 解析策略

采用 **Schema-first + Raw-field 回退** 的双层策略：
1. 优先使用 Protobuf Schema 解码（如 `ZoneBattleEnterNotify`）
2. Schema 不可用时回退为原始字段号提取（varint 定位）

每个解析函数从 Protobuf 消息中提取结构化数据，如精灵 ID、技能名、伤害值、HP、能量等。

### 2.6 战斗状态追踪

**文件：** `src/analysis/battle_state.py`

`BattleStateTracker` 消费协议事件，维护一个实时战斗状态字典：

```python
state = {
    "battle_id": ...,        # 战斗 ID
    "battle_mode": ...,      # 战斗模式
    "round": 0,              # 当前回合
    "max_round": 0,          # 最大回合
    "weather_id": ...,       # 天气
    "my_pets": [...],        # 我方精灵列表
    "opp_pets": [...],       # 敌方精灵列表
    "my_active": {...},      # 我方上场精灵
    "opp_active": {...},     # 敌方上场精灵
    "events": [...],         # 事件历史
    "result": None,          # 战斗结果 (WIN/LOSE/...)
}
```

每个精灵条目包含：

```python
{
    "pet_id": ...,
    "name": "...",
    "types": [...],           # 属性列表
    "current_hp": ...,
    "max_hp": ...,
    "hp_pct": 0.8,           # HP 百分比 (0.0~1.0)
    "energy": 5,              # 能量 (0~10)
    "buffs": [...],           # 增益/减益状态
    "combo_bonus": 0,         # 连击数修正值（combo_skill_cast 事件更新）
    "poison_stacks": 0,       # 中毒层数（effect_apply 事件更新）
}
```

状态更新流程：
- `0x1316` → 初始化战斗，加载双方精灵阵容
- `0x131A` → 更新回合数和精灵 HP
- `0x1324` → 处理伤害结算、技能消耗、击杀事件
- `0x13F4` → 处理能量瓶等特殊事件
- `0x132C` → 记录战斗结果

#### 战术建议

基于当前状态的简单规则引擎：

| 条件 | 建议 |
|------|------|
| 我方 HP < 25% | "我方精灵HP过低，考虑换宠" |
| 我方 HP > 75% | "我方精灵HP健康" |
| 敌方 HP < 25% | "对手精灵HP极低，可尝试击杀" |
| 能量 < 2 | "能量不足，考虑使用低能耗技能或能量瓶" |
| 负面状态 ≥ 2 | "我方精灵有多个负面状态" |

除上述简单规则建议外，系统还提供两种高级分析：

1. **伤害预测分析**（消息类型 `skill_analysis`）: 对我方精灵的所有装备技能计算伤害预测，含连击总伤害、击杀判断、属性克制信息。由 `BattleAdvisor` 驱动，在 battle_enter、round_start、action_resolve、special_refresh 时触发。

2. **分析 Hook 建议**（消息类型 `hook_advice`）: 基于战斗生命周期的可插拔分析模块，包括对手模式追踪、能量窗口检测、属性换宠建议等。

### 2.6.1 伤害预测分析

**文件：** `src/analysis/battle_advisor.py`、`src/analysis/damage_calc.py`、`src/analysis/innate_hooks.py`

伤害预测系统在战斗进行中对当前精灵的所有装备技能进行伤害计算，提供击杀判断、属性克制等信息。

#### 伤害计算管线 (4 阶段 Hook)

`DamageCalculator` 实现确定性伤害预测：

```
base = (ATK / DEF) * power * 0.9
damage = base * effectiveness * stab * weather * hits * power_mult
```

管线分为 4 个阶段，每个阶段可注册 Hook 函数修改计算参数：

| 阶段 | 上下文字段 | 用途 |
|------|-----------|------|
| `pre_power` | power, skill_meta, attacker, defender | 修正技能威力 |
| `post_base` | base_damage, atk_val, def_val | 修正基础伤害 |
| `pre_final` | base_damage, effectiveness, stab_mult | 修正属性克制/本系修正 |
| `post_calc` | min_damage, max_damage, hit_count | 修正最终伤害/连击数 |

#### 先天技能 Hook

`innate_hooks.py` 提供四个 Hook 函数，由 `register_innate_hooks()` 注册：

| Hook 函数 | 注册阶段 | effect_type | 效果 |
|-----------|---------|-------------|------|
| `stat_modify_hook` | post_base | stat_modify | HP 低于阈值时百分比提升伤害 |
| `type_resist_modify_hook` | pre_final | type_resist_modify | 提升属性克制倍率下限（如无视抵抗） |
| `combo_modify_hook` | post_calc | combo_modify | 增加连击次数，总伤害 = 单次 × 连击 |
| `power_modify_hook` | post_calc | power_modify | 附加效果如先手吸血 |

支持触发条件：`always`、`per_poison_stack`、`skill_element_used`、`hp_below`、`first_strike`

#### BattleAdvisor

`BattleAdvisor` 是伤害分析入口：
1. 创建 `DamageCalculator` 并注册先天技能 Hook
2. 对我方精灵的所有装备技能计算伤害预测
3. 生成 `BattleAdvice`（含 `skill_analysis`、`suggestions`、`traits`）

#### 分析 Hook 系统

**文件：** `src/analysis/hook_registry.py`、`src/analysis/hooks/`

独立的 ABC Hook 系统，基于战斗生命周期事件触发：

| 触发器 | 时机 |
|--------|------|
| ON_BATTLE_ENTER | 战斗开始 |
| ON_ROUND_START | 回合开始 |
| ON_ACTION_RESOLVE | 动作结算 |
| ON_SPECIAL_REFRESH | 特殊刷新 |
| ON_BATTLE_FINISH | 战斗结束 |
| ON_CHANGE_PET | 换宠 |
| ON_DEFEAT | 击败 |

默认 Hook：`OpponentTrackerHook`、`EnergyMonitorHook`、`SwitchAdvisorHook`

### 2.7 WebSocket 实时推送

**文件：** `src/api/routes_battle.py`

后端通过 FastAPI WebSocket 端点 `/ws/battle` 向前端推送数据。

#### 消息协议

**客户端 → 服务器：**

```json
// 推送游戏事件
{"type": "event", "opcode": 4886, "detail": {...}}

// 查询当前状态
{"type": "get_state"}

// 重置战斗
{"type": "reset"}

// 请求克制推荐
{"type": "request_counter_pick"}
```

**服务器 → 客户端：**

```json
// 连接确认
{"type": "connected", "message": "Battle state tracker ready"}

// 状态更新（每次事件后推送）
{"type": "state_update", "state": {...}}

// 格式化战斗事件
{"type": "battle_event", "event": {...}}
{"type": "battle_events", "events": [{...}, ...]}

// 简单规则建议
{"type": "suggestions", "suggestions": [{"type": "low_hp", "message": "..."}]}

// 伤害预测分析
{"type": "skill_analysis", "skills": [...], "traits": [...], "opp_traits": [...]}

// 分析 Hook 建议
{"type": "hook_advice", "advice": [{"hook_id": "...", "priority": 0, "title": "...", "messages": [...]}]}

// 战斗总结
{"type": "battle_summary", "summary": {...}}

// 克制推荐
{"type": "counter_pick", "opponent": {...}}
```

### 2.8 Web 前端

**文件：** `web/src/pages/BattleLive.tsx`、`web/src/hooks/useBattle.ts`、`web/src/stores/battleStore.ts`

前端使用 React + Zustand + Ant Design：

- **BattleLive 页面**：展示双方精灵 HP 条、能量、回合数、战斗结果、建议列表、事件时间线
- **useBattle Hook**：管理 WebSocket 连接生命周期，封装 `connect`/`sendEvent`/`resetBattle`/`getState`
- **battleStore**：Zustand 状态管理，维护前端战斗状态

---

## 三、使用方法

### 3.1 环境要求

- Python 3.10+
- Windows（Scapy 抓包需要 Npcap/WinPcap）
- Node.js 18+（前端）
- 洛克王国客户端正在运行

### 3.2 安装依赖

```bash
# 后端
pip install scapy pycryptodome fastapi uvicorn

# 前端
cd web
npm install
```

### 3.3 启动后端

```bash
python -m src.main
```

API 服务运行在 `http://localhost:8000`。

### 3.4 启动前端

```bash
cd web
npm run dev
```

前端运行在 `http://localhost:5173`。

### 3.5 开始使用

1. 打开浏览器访问 `http://localhost:5173`
2. 进入「实时战斗」页面
3. 点击「**连接战斗**」按钮建立 WebSocket 连接
4. 在洛克王国客户端中开始一场战斗
5. 系统自动捕获流量并在前端实时显示战斗状态

> **注意**：抓包需要管理员权限运行后端，且本机需安装 Npcap 驱动。

### 3.6 （可选）预设密钥

如果自动密钥提取失败，可手动创建 `session_key.txt`：

```
key_hex=0123456789abcdef0123456789abcdef
```

或启动时传入：

```python
sniffer = Sniffer(preset_key=b"16-byte-key-here")
```

---

## 四、数据流完整路径

以「战斗中一次技能伤害」为例：

```
1. 游戏服务器发送 TCP 包 (端口 8195)
2. Scapy 捕获 → Sniffer._process_packet()
3. TCP 流重组 → DirectionState.feed()
4. BE21 帧提取 → parse_be21_from_buffer()
5. 识别为 0x4013 DATA 帧
6. AES-128-CBC 解密 → decrypt_4013_body()
7. Protobuf 解析 → parse_record()
8. Opcode 0x1324 分发 → extract_1324_action()
   提取：技能名、伤害值、目标 HP、能量变化
9. BattleStateTracker.handle_event(0x1324, detail)
   更新：精灵 HP、能量
10. WebSocket 推送 state_update → 前端
11. React 重渲染：HP 条下降、事件时间线新增条目
```

---

## 五、文件索引

| 层级 | 文件 | 职责 |
|------|------|------|
| 抓包 | `src/capture/sniffer.py` | Scapy 抓包编排，TCP 流管理 |
| 抓包 | `src/capture/reassembly.py` | TCP 流重组（乱序/重传处理） |
| 抓包 | `src/capture/frame.py` | BE21 协议帧解析 |
| 抓包 | `src/capture/crypto.py` | AES-128-CBC 解密、密钥文件管理 |
| 抓包 | `src/capture/key_capture.py` | 从 ACK 帧提取会话密钥 |
| 协议 | `src/protocol/proto_core.py` | Protobuf 解析原语、精灵/状态提取 |
| 协议 | `src/protocol/opcodes.py` | Opcode 注册表与分发 |
| 协议 | `src/protocol/battle.py` | 战斗协议各 Opcode 的详细解析 |
| 分析 | `src/analysis/battle_state.py` | 实时战斗状态追踪与建议生成 |
| 分析 | `src/analysis/damage_calc.py` | 伤害计算引擎（4 阶段 Hook 管线） |
| 分析 | `src/analysis/innate_hooks.py` | 先天技能伤害 Hook（combo/stat/type/power 修正） |
| 分析 | `src/analysis/battle_advisor.py` | 战斗分析协调器（技能分析 + 伤害预测） |
| 分析 | `src/analysis/hook_registry.py` | 可扩展分析 Hook 系统（ABC 基类，生命周期管理） |
| 分析 | `src/analysis/hooks/opponent_tracker.py` | 对手技能/换宠模式追踪 |
| 分析 | `src/analysis/hooks/energy_monitor.py` | 能量监控与攻击窗口检测 |
| 分析 | `src/analysis/hooks/switch_advisor.py` | 属性克制换宠推荐 |
| 游戏逻辑 | `src/game/type_chart.py` | 18 属性克制矩阵、弱点/抗性查询 |
| 游戏逻辑 | `src/game/stats.py` | 种族值/能力值计算（HP + 5 属性公式） |
| 游戏逻辑 | `src/game/skill_eval.py` | 技能评分引擎 |
| API | `src/api/routes_battle.py` | WebSocket 战斗端点 |
| API | `src/api/app.py` | FastAPI 应用入口 |
| 入口 | `src/main.py` | Uvicorn 启动脚本 |
| 前端 | `web/src/pages/BattleLive.tsx` | 实时战斗页面 |
| 前端 | `web/src/hooks/useBattle.ts` | WebSocket 连接 Hook |
| 前端 | `web/src/stores/battleStore.ts` | 战斗状态管理 |
| 前端 | `web/src/components/BattleTimeline.tsx` | 事件时间线组件 |
| 前端 | `web/src/components/DamagePredictionPanel.tsx` | 伤害预测面板（含连击显示） |
| 前端 | `web/src/components/SkillPanel.tsx` | 技能分析面板 |
| 前端 | `web/src/components/HookAdvicePanel.tsx` | 战术分析建议面板 |
| 数据 | `data/game/type_chart.json` | 属性克制矩阵 |
| 数据 | `data/game/innate_skills.json` | 先天技能定义（S2 天赋、连击修正等） |
