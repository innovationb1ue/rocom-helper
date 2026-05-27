# 战斗回放指南

## 概述

回放系统将预录的战斗抓包包通过完整的解析管道重放，推送到前端 WebSocket 客户端实时展示。用于开发调试和验证战斗分析功能。

## 前提条件

- 后端运行: `py -m src.main` (端口 8000)
- 前端运行: `cd web && npm run dev` (端口 5173)
- 浏览器打开 `http://localhost:5173/battle`

## 回放步骤

### 1. 前端准备

在浏览器中打开 `http://localhost:5173/battle`，点击 **"连接战斗"** 按钮。页面应显示绿色的 "已连接" 标签。WebSocket 连接建立后，后端的 `BattleManager` 才会推送数据。

### 2. 触发回放

通过 POST 请求触发回放:

```bash
# 使用默认 session_1，80ms 延迟
curl -X POST "http://localhost:8000/api/battle/replay"

# 指定 session 和延迟
curl -X POST "http://localhost:8000/api/battle/replay?delay_ms=200&session=battle_session_1"

# 快速回放（无延迟）
curl -X POST "http://localhost:8000/api/battle/replay?delay_ms=0"

# 回放到指定回合停止（例如回放到 R7）
curl -X POST "http://localhost:8000/api/battle/replay?stop_round=7"
```

使用 CLI 脚本:

```bash
# 默认回放到战斗结束
py -m scripts.replay_to_frontend --delay 80 --session battle_session_1

# 回放到 R7 停止
py -m scripts.replay_to_frontend --delay 80 --round 7

# 回放到 R10 停止
py -m scripts.replay_to_frontend --delay 80 --round 10

# 指定后端地址
py -m scripts.replay_to_frontend --delay 80 --host localhost --port 8000
```

参数:
- `delay_ms` (int, 默认 80): 每个包之间的延迟毫秒数，0 表示瞬间完成
- `session` (str, 默认 "battle_session_1"): 回放的 session 名称
- `stop_round` (int, 可选): 在指定回合结束后停止回放。例如 `stop_round=7` 表示回放到 R7 结束后停止，不处理 R8 的 round_start。不指定则回放到战斗结束

返回值:
```json
{
  "status": "ok",
  "processed": 176,
  "total_formatted_events": 120,
  "result": "WIN_HP",
  "rounds": 17,
  "stopped_early": false,
  "my_pets": 6,
  "opp_pets": 6
}
```

`stopped_early` 为 `true` 表示因 `stop_round` 参数提前停止。

### 3. 观察前端

回放期间，前端页面会实时更新:
- 双方阵容和 HP/能量条
- 战斗事件日志
- **伤害预测面板**（`DamagePredictionPanel`，在双方阵容下方，显示当前精灵技能的伤害预测，含连击显示）
- 建议卡片
- 战斗结束后显示总结

## 可用的 Session 数据

| Session | 目录 | 包数量 | 回合 | 结果 |
|---------|------|--------|------|------|
| battle_session_1 | `tests/fixtures/packets/battle_session_1/` | ~176 (过滤后) | 17 | WIN_HP |
| battle_session_2 | `tests/fixtures/packets/battle_session_2/` | ~30 (过滤后) | — | — |
| battle_session_3 | `tests/fixtures/packets/battle_session_3/` | — | — | — |
| battle_session_4 | `tests/fixtures/packets/battle_session_4/` | — | — | — |
| battle_session_5 | `tests/fixtures/packets/battle_session_5/` | — | — | — |
| battle_session_6 | `tests/fixtures/packets/battle_session_6/` | — | — | — |

Session 目录结构:
```
tests/fixtures/packets/battle_session_1/
├── _session.json              # session 元数据
├── c2s_0x1001_0001_*.bin      # 客户端→服务端包
├── s2c_0x4013_0002_*.bin      # 服务端→客户端包 (数据包)
└── ...
```

## 数据管道

```
.bin 文件 (RC01 格式)
  │
  ▼  packet_reader.read_bin_packet()
原始数据 (含 decrypted_body_hex)
  │
  ▼  proto_core.parse_record()
结构化 record (opcode, direction, proto tree)
  │
  ▼  opcodes.summarize()
语义化 summary (kind, detail)
  │
  ▼  BattleManager.process_event()
  ├── BattleStateTracker.handle_event()  → 状态更新（含 combo_bonus, poison_stacks）
  ├── format_battle_event()              → 格式化事件 → WebSocket push
  ├── _push_state()                      → state_update → WebSocket push
  ├── BattleAdvisor.analyze()            → skill_analysis → WebSocket push
  │     └── DamageCalculator.calculate() → DamageResult（4 阶段 Hook 管线）
  │           └── innate_hooks            → 先天技能修正（combo/stat/type/power）
  ├── _run_analysis_hooks()              → hook_advice → WebSocket push
  │     └── HookRegistry.dispatch()      → OpponentTracker, EnergyMonitor, SwitchAdvisor
  └── compute_battle_summary()           → battle_summary → WebSocket push (战斗结束时)
```

## WebSocket 消息类型

前端会收到以下类型的消息:

| type | 说明 | 触发时机 |
|------|------|----------|
| `connected` | 连接确认 | WebSocket 连接时 |
| `state_update` | 战斗状态快照 | 每个事件处理后 |
| `battle_event` | 单个格式化事件 | 有新事件时 |
| `battle_events` | 多个格式化事件 | 有新事件时 |
| `suggestions` | 文本建议 | 状态更新后 |
| `skill_analysis` | 技能分析（含伤害预测） | 进入/回合/动作时 |
| `hook_advice` | 分析 Hook 建议 | 战斗事件触发时 |
| `battle_summary` | 战斗总结 | 战斗结束时 (opcode 0x132C) |

## 伤害预测触发时机

在 `BattleManager.process_event()` 中，以下 opcode 会触发伤害分析:
- `0x1316` (battle_enter) — 战斗开始，精灵数据初始化
- `0x131A` (round_start) — 每回合开始，属性和技能可能变化
- `0x1324` (action_resolve) — 动作结算，HP/能量变化
- `0x13F4` (special_refresh) — 特殊刷新

## 注意事项

1. **必须先连接 WebSocket** 再触发回放，否则数据不会推送到前端
2. 回放会 `reset_tracker()`，清空之前的状态
3. `delay_ms=0` 时所有包瞬间处理完，前端一次性收到所有更新
4. 建议用 `delay_ms=100~200` 观察实时效果
5. 回放可以重复执行，每次都会重置状态

## 无头回放

不需要启动服务器和前端，纯后端回放：

```bash
# 文本摘要输出
py -m scripts.replay_headless --session battle_session_1

# JSON 输出（写入 tmp/ 目录）
py -m scripts.replay_headless --session battle_session_1 --json

# 在指定回合停止
py -m scripts.replay_headless --session battle_session_1 --round 7
```

输出包含：每回合事件摘要、伤害预测、建议、hook 建议、最终状态。

## 战斗报告

生成完整分析报告。默认写入 `docs/battle_report.txt`；加 `--json` 时把结构化结果输出到 stdout：

```bash
py -m scripts.generate_battle_report
py -m scripts.generate_battle_report --json
```

输出包含完整的回合分析、伤害对比和战斗总结。

## `.raco-report` 导入导出

`.raco-report` 是用于问题复现和开发调试的战斗抓包包。它不是分析结果文件，而是一个 zip 格式的原始包归档，包含：

```text
manifest.json                  # 报告元数据：来源 session、战斗边界、导出窗口、文件列表
README.txt                     # 简短说明
packets/_session.json          # 原始 session 元数据（如果存在）
packets/*.bin                  # 原始 RC01 抓包文件
```

当前格式版本为 `format_version = 2`。包内不再包含 `analysis.json`；完整分析应在导入后重新回放生成。

### 导出 `.raco-report`

实时抓包完成一场战斗后，后端会把最近完成的战斗归档到 `logs/battle_reports/<session>/`。也可以通过 API 下载：

```bash
# 列出可导出的战斗报告
curl http://localhost:8000/api/battle/reports

# 下载指定报告；report_id 形如 2026-05-07_21-17-31_monitor:1
curl -o battle.raco-report "http://localhost:8000/api/battle/reports/<urlencoded_report_id>/download"
```

导出窗口使用战斗开始前 `10s`、战斗结束后 `5s` 的缓冲，确保 battle_enter 附近上下文不会被遗漏。包内的 `packets/*.bin` 是从 `logs/packets/<session>/` 原样写入的 RC01 文件，解压后的字节内容应与源文件一致。

### 导入 `.raco-report`

使用 `scripts.unpack_battle_report` 把报告解压成普通抓包目录：

```bash
# 解压到默认目录：与 report 同目录、同名文件夹
py -m scripts.unpack_battle_report path\to\battle.raco-report

# 指定输出目录
py -m scripts.unpack_battle_report path\to\battle.raco-report --output tmp\report_packets

# 解压后立即运行无头完整回放验证
py -m scripts.unpack_battle_report path\to\battle.raco-report --output tmp\report_packets --verify
```

解压后的目录结构类似普通抓包 session：

```text
tmp/report_packets/
├── _session.json
├── _raco_report_manifest.json
├── c2s_0x4013_0551_212323.955.bin
├── s2c_0x4013_1543_212323.988.bin
└── ...
```

其中 `_raco_report_manifest.json` 是从报告里的 `manifest.json` 复制出来的导出元数据。`.bin` 文件位于目录根部，因此现有 `load_battle_packets()`、`BattleReplayRunner` 和调试脚本可以直接读取。

### 验证导入结果

推荐导入时直接加 `--verify`：

```bash
py -m scripts.unpack_battle_report path\to\battle.raco-report --output tmp\report_packets --verify
```

成功时输出类似：

```text
Replay verification: PASS
  packets=176 rounds=17 final_round=17 result=WIN_HP my_pets=6 opp_pets=6
```

如果需要进一步调试，可以把解压目录复制或移动到 `tests/fixtures/packets/<name>/`，再用现有无头回放或测试夹具读取。
