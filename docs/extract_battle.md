# 战斗包提取工具

从原始抓包会话中识别战斗边界，提取战斗相关包到测试 fixture。

源码：`scripts/extract_battle.py`

## 概述

工具解决的核心问题：一次抓包会话可能包含多场战斗，以及战斗前后的无关流量。本工具自动检测每场战斗的起止边界，按时间窗口提取相关包到 `tests/fixtures/packets/battle_session_N/`，供回放测试使用。

## 快速开始

```bash
# 1. 列出抓包会话中的所有战斗
py -m scripts.extract_battle --session 2026-05-16_20-12-54_monitor

# 2. 提取第 1 场战斗
py -m scripts.extract_battle --session 2026-05-16_20-12-54_monitor --extract 1

# 3. 提取并验证
py -m scripts.extract_battle --session 2026-05-16_20-12-54_monitor --extract 1 --verify
```

## 命令参考

### `--session <id>` （必需）

指定会话来源，按以下顺序查找：

1. **字面路径** — 如 `logs/packets/my_session`
2. **测试 fixture** — `tests/fixtures/packets/<id>`
3. **抓包日志** — `logs/packets/<id>`

```bash
# 原始抓包会话
py -m scripts.extract_battle --session 2026-05-16_20-12-54_monitor

# 已有的测试 fixture
py -m scripts.extract_battle --session battle_session_3
```

### `--extract <N|all>`

省略此参数则只列出战斗，不提取。

```bash
py -m scripts.extract_battle --session <id> --extract 1     # 提取第 1 场战斗
py -m scripts.extract_battle --session <id> --extract 2     # 提取第 2 场战斗
py -m scripts.extract_battle --session <id> --extract all   # 提取所有战斗
```

### `--verify`

提取后自动验证正确性：对原始包（过滤到时间窗口）和提取包分别运行 `BattleReplayRunner`，比较 `final_state` 和 `battle_summary` 是否完全匹配。

```bash
py -m scripts.extract_battle --session <id> --extract 1 --verify
```

### `--pad-before <秒>` （默认 5.0）

战斗开始前的时间填充，确保 `battle_enter` 之前的上下文包（如密钥交换）也被包含。

```bash
py -m scripts.extract_battle --session <id> --extract 1 --pad-before 10
```

### `--pad-after <秒>` （默认 2.0）

战斗结束后的时间填充。

```bash
py -m scripts.extract_battle --session <id> --extract 1 --pad-after 5
```

### `--output <名称>`

自定义输出目录名（仅在提取单场战斗时有效）。默认自动分配 `battle_session_N`。

```bash
py -m scripts.extract_battle --session <id> --extract 1 --output my_battle
```

## 输出

提取后的目录结构：

```
tests/fixtures/packets/battle_session_N/
├── _session.json                          # 元数据
├── s2c_0x4013_0001_201254.123.bin         # 时间窗口内的所有 .bin 包
├── c2s_0x1001_0002_201255.456.bin
└── ...
```

### `_session.json` 元数据

```json
{
  "session_start": "2026-05-16T20:15:00",
  "session_id": "battle_session_4",
  "source_session": "2026-05-16_20-12-54_monitor",
  "source_path": "logs\\packets\\2026-05-16_20-12-54_monitor",
  "battle_index": 1,
  "enter_file": "s2c_0x4013_0042_201254.123.bin",
  "finish_file": "s2c_0x4013_0198_201345.789.bin",
  "enter_ts": "20:12:54.123",
  "finish_ts": "20:13:45.789",
  "pad_before": 5.0,
  "pad_after": 2.0,
  "file_count": 87
}
```

| 字段 | 含义 |
|------|------|
| `source_session` | 原始抓包会话目录名 |
| `battle_index` | 在原始会话中的第几场战斗 |
| `enter_file` / `finish_file` | 战斗开始/结束的包文件名 |
| `pad_before` / `pad_after` | 提取时使用的时间填充 |
| `file_count` | 提取的包文件数量 |

## 工作原理

### 边界检测

1. 扫描会话目录中所有 `*_0x4013_*.bin` 文件（只有 cmd=0x4013 的包才包含战斗 opcode）
2. 读取每个文件的尾部 JSON 元数据（RC01 格式），提取 `opcode_hex`
3. 匹配 `0x1316`（battle_enter）和 `0x132C`（battle_finish）opcode 对
4. 按时间顺序配对：第 1 个 enter 与第 1 个在其之后的 finish 配对，依此类推
5. 未配对的 enter 标记为 `INCOMPLETE`，使用最后一个包的时间作为结束

### 时间窗口选择

确定战斗边界后，以 `[enter_time - pad_before, finish_time + pad_after]` 作为时间窗口，复制窗口内所有 `.bin` 文件（不限 cmd 类型）到输出目录。

### 验证流程

`--verify` 执行以下对比：

1. 加载原始会话的所有包，按时间窗口过滤
2. 加载提取目录的所有包
3. 检查包数量是否一致
4. 分别运行 `BattleReplayRunner`，对比：
   - `total_packets`
   - `rounds` 数量
   - `final_state` 中的 `round`、`result`、`my_pets`、`opp_pets`
   - `battle_summary` 中的 `result`

全部匹配则通过，任一不一致则报告 `MISMATCH` 并以非零退出码退出。

## 典型工作流

从一次抓包获取可用的测试 fixture：

```bash
# 1. 列出会话中的战斗
py -m scripts.extract_battle --session 2026-05-16_20-12-54_monitor

# 输出示例：
# Session: 2026-05-16_20-12-54_monitor
# Path:    logs/packets/2026-05-16_20-12-54_monitor
# Files:   342 .bin
#
# ── Battle #1 ──
#   Enter:  20:12:54  (...)
#   Finish: 20:13:45  (...)
#   Duration: ~51s
#
#   Extract:  py -m scripts.extract_battle --session ... --extract 1

# 2. 提取并验证
py -m scripts.extract_battle --session 2026-05-16_20-12-54_monitor --extract 1 --verify

# 3. 用提取的 fixture 运行测试
pytest tests/test_battle_replay.py -v

# 4. 回放查看详细输出
py -m scripts.replay_headless --session battle_session_4
```

## 常见问题

**"No battles found in this session"**

会话中没有检测到 `0x1316`（battle_enter）包。可能原因：
- 会话不包含 PvP 战斗
- 包的元数据缺失或损坏
- 包文件名不符合 `*_0x4013_*.bin` 模式

**"INCOMPLETE — no battle_finish"**

检测到 `battle_enter` 但未找到对应的 `battle_finish`。可能是战斗中途断开连接或仍在进行中。提取时仍可使用，但最终状态可能不完整。

**验证失败（包数量不匹配）**

时间窗口计算基于文件名中的时间戳。如果文件命名格式异常，可能导致过滤不准确。尝试调整 `--pad-before` 和 `--pad-after`。
