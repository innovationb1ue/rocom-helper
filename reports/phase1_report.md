# Phase 1 报告：项目初始化 + 协议解析移植

## 概述

Phase 1 完成了从 RKPP (Roco-Kingdom-Protocol-Parser) 仓库移植网络抓包和协议解析代码到本项目，建立了完整的项目结构和数据管线。

## 项目结构

```
D:\raco-helper\
├── src/
│   ├── capture/           # 网络抓包模块
│   │   ├── frame.py       # BE21 帧解析 (75 行)
│   │   ├── crypto.py      # AES-128-CBC 解密 (85 行)
│   │   ├── reassembly.py  # TCP 流重组 (177 行)
│   │   ├── key_capture.py # 密钥提取 (33 行)
│   │   └── sniffer.py     # 抓包编排器 (193 行)
│   ├── protocol/          # 协议解析模块
│   │   ├── proto_core.py  # Protobuf 原语 + 传输层 (516 行)
│   │   ├── battle.py      # 战斗协议提取 (1042 行)
│   │   └── opcodes.py     # Opcode 分发注册表 (249 行)
│   └── data/
│       └── loader.py      # JSON 数据加载器 (199 行)
├── data/game/             # 静态游戏数据 (12 个 JSON 文件)
├── tests/                 # 测试文件
│   ├── test_frame.py      # BE21 帧解析测试
│   ├── test_crypto.py     # AES 解密测试
│   └── test_loader.py     # 数据加载器测试
└── reports/               # 阶段报告
```

**总代码量**: 2569 行 Python

## 移植模块详情

### 1. src/capture/frame.py — BE21 帧解析

从 `rkpp_network.py` 移植。

| 符号 | 说明 |
|------|------|
| `MAGIC = b"\x33\x66"` | 帧头魔数 |
| `FIXED_HDR_LEN = 21` | 固定头部长度 |
| `Be21Packet` | 帧数据类 (direction, cmd, seq, hdr_len, body_len, header_extra, body) |
| `_validate_be21_header()` | 验证帧头合法性 |
| `parse_be21_from_buffer()` | 从缓冲区解析所有完整帧 |

帧头布局:
```
[0:2]   MAGIC     0x33 0x66
[2:6]   reserved  4 bytes
[6:8]   cmd       2 bytes BE  (范围 0x0001-0x7FFF)
[8:9]   unknown   1 byte
[9:13]  seq       4 bytes BE
[13:17] hdr_len   4 bytes BE  (>= 21)
[17:21] body_len  4 bytes BE
```

### 2. src/capture/crypto.py — AES-128-CBC 解密

从 `rkpp_network.py` 移植。

| 符号 | 说明 |
|------|------|
| `decrypt_4013_body(key, body)` | 解密 0x4013 DATA 帧，返回 (iv, plaintext) |
| `parse_key_text(text)` | 解析 16 字节 ASCII 或 32 字符 hex 密钥 |
| `printable_ascii(blob)` | 检测是否全部可打印 ASCII |
| `load_key_from_file(path)` | 从文件加载密钥 |
| `write_key_file(path, key, flow_id)` | 写密钥到文件 |

### 3. src/capture/reassembly.py — TCP 流重组

从 `rkpp_network.py` 移植。

| 符号 | 说明 |
|------|------|
| `DirectionState` | 单方向 TCP 流状态 (buffer, seq 追踪, 乱序重组) |
| `FlowState` | 双向流状态 (c2s + s2c, AES 密钥, seen_acks) |
| `_BoundedAckSet` | 有界 ACK 去重集合 |

### 4. src/capture/key_capture.py — 密钥提取

新建模块。

| 符号 | 说明 |
|------|------|
| `extract_key_from_ack(packet)` | 从 0x1002 ACK 帧的 header_extra[2:18] 提取 16 字节 AES 密钥 |
| `is_ack_packet(packet)` | 判断是否为 ACK 包 |

### 5. src/capture/sniffer.py — 抓包编排器

新建模块，整合 Scapy AsyncSniffer。

| 符号 | 说明 |
|------|------|
| `Sniffer` | 顶层抓包类 (start/stop, 流管理, 解密+解析+分发) |

处理流程:
```
TCP payload → DirectionState.feed() → Be21Packet
  → 0x1002? → 密钥提取
  → 0x4013? → AES 解密 → parse_record() → summarize() → on_record 回调
  → 其他?   → parse_tgcp_control_packet() → on_record 回调
```

### 6. src/protocol/proto_core.py — Protobuf 原语 + 传输层

从 `rkpp_proto_core.py` 移植。

| 符号 | 说明 |
|------|------|
| `read_varint()` | 读取 varint |
| `parse_proto_message()` | 递归解析 Protobuf 消息 |
| `walk_messages()`, `field_groups()`, `collect_varints()` | 消息遍历辅助 |
| `first_text()`, `first_sub()`, `pick_first()` | 字段提取 |
| `extract_creature()`, `extract_state_wrapper()` | 精灵/状态提取 |
| `parse_record()`, `parse_tgcp_control_packet()` | 传输层解析 |
| `_extract_actor_target()`, `_attach_buff_meta()` | 战斗辅助 |
| `extract_inner_message()` | 0x0414 内嵌消息提取 |

三种传输层布局:
- `v14`: magic 0x3963, 传统格式
- `live_s2c`: magic 0x55AA, 服务端到客户端
- `live_c2s`: magic 0x3963, 客户端到服务端

### 7. src/protocol/battle.py — 战斗协议提取

从 `rkpp_proto_battle.py` 移植。

17 个提取函数 + 3 个共用内部函数:

| 函数 | Opcode | 说明 |
|------|--------|------|
| `extract_0102_creatures()` | 0x0102 | 精灵列表（含属性/技能/种族值） |
| `extract_0102_metadata()` | 0x0102 | 玩家信息 |
| `extract_0220_handle()` | 0x0220 | 快照句柄 |
| `extract_01a9_action()` | 0x01A9 | 客户端操作 |
| `extract_130b_skill_select()` | 0x130B | 客户端选技能 |
| `extract_130c_result()` | 0x130C | 服务器确认 |
| `extract_1322_skill_declare()` | 0x1322 | 服务器声明技能 |
| `extract_1324_action()` | 0x1324 | 动作结算（技能/伤害/效果/击败） |
| `extract_13f4_refresh()` | 0x13F4 | 特殊刷新（能量瓶/愿力强化） |
| `extract_1316_enter()` | 0x1316 | 进入战斗（schema-first + raw fallback） |
| `extract_131a_round_start()` | 0x131A | 回合开始 |
| `extract_132c_finish()` | 0x132C | 战斗结束（含结果映射 + PvP 分数） |
| `extract_13fc_pvp_perform()` | 0x13FC | PvP 表演 |
| `extract_13f3_preplay()` | 0x13F3 | 预演 |
| `extract_1312_round_flow()` | 0x1312 | 回合流 |

1324 动作结算支持的 entry 类型:
- type 1: skill_cast (技能释放 + 能量变化)
- type 2: effect_apply (效果施加)
- type 3: effect_stage (效果阶段)
- type 4: damage (伤害 + 目标 HP)
- type 7: defeat (击败)
- type 10: effect_link (效果链接)

### 8. src/protocol/opcodes.py — Opcode 分发注册表

从 `rkpp_analyzer.py` 移植。

14 个 opcode 处理器 + 4 个 inner message 处理器:

| Opcode | Kind | Handler |
|--------|------|---------|
| 0x0102 | roster_init | extract_0102_metadata + extract_0102_creatures |
| 0x01A9 | client_action | extract_01a9_action |
| 0x0220 | snapshot_handle | extract_0220_handle |
| 0x130B | client_skill_select | extract_130b_skill_select |
| 0x130C | server_action_ack | extract_130c_result |
| 0x1312 | round_flow | extract_1312_round_flow |
| 0x1316 | battle_enter | extract_1316_enter |
| 0x131A | round_start | extract_131a_round_start |
| 0x1322 | server_skill_declare | extract_1322_skill_declare |
| 0x1324 | action_resolve | extract_1324_action |
| 0x132C | battle_finish | extract_132c_finish |
| 0x13F3 | preplay | extract_13f3_preplay |
| 0x13F4 | special_refresh | extract_13f4_refresh |
| 0x13FC | pvp_perform | extract_13fc_pvp_perform |

| Inner ID | Kind | Parser |
|----------|------|--------|
| 390 | inner390_pair | 对战配对 |
| 200 | inner200_commit | 提交确认 |
| 51 | inner51_event | 事件 |
| 1 | inner1_effect | 效果 |

公共接口 `summarize(record, inner)` 根据 opcode 查表分发。

### 9. src/data/loader.py — JSON 数据加载器

从 `Data.py` 移植并重构。

线程安全缓存，支持 12 个 JSON 数据文件:

| 文件 | 条目数 | 说明 |
|------|--------|------|
| attr_map.json | 86 | 属性定义 |
| skill_map.json | 1,378 | 技能元数据 |
| pet_map.json | 6,575 | 精灵数据 |
| pet_skill_map.json | 881 | 精灵→技能映射 |
| buff_map.json | 1,925 | Buff 定义 |
| buffbase_map.json | 1,879 | Buff 基础定义 |
| monster_map.json | 11,176 | 怪物/NPC |
| special_move_map.json | 1,443 | 特殊移动 |
| opcode_pb_map.json | 1,497 | Opcode→protobuf 映射 |
| pb_message_index.json | 9,883 | Protobuf 消息索引 |
| proto_schema.json | - | Protobuf 消息定义 |

公共 API:
- `get_bundle()`, `get_maps()` — 加载全部数据
- `get_attr_name(id)`, `get_skill_name(id)`, `get_pet_name(id)` — 名称查找
- `get_attr_meta(id)`, `get_skill_meta(id)`, `get_pet_meta(id)` — 完整元数据
- `invalidate_cache()` — 清空缓存重载

## RKPP 代码适配差异

| 差异点 | RKPP 原版 | 本项目 |
|--------|-----------|--------|
| Python 版本 | >=3.11 | >=3.9 (使用 `from __future__ import annotations`) |
| 数据加载 | `Data.py` 模块级变量 | `loader.py` 线程安全缓存 + RLock |
| 导入方式 | `import rkpp_proto` | `from src.protocol.proto_core import ...` |
| 密钥提取 | 内嵌在 `_handle_be21()` | 独立 `key_capture.py` 模块 |
| 抓包编排 | `RkppAnalyzer` 类 (含 CSV/PCAP 输出) | `Sniffer` 类 (纯回调模式) |
| Schema 解码 | `rkpp_analysis.py` | 暂未移植 (Phase 2) |
| 格式化器 | `_FMT_REGISTRY` | 暂未移植 (Phase 2) |

## 测试结果

```
54 passed in 6.10s
```

| 测试文件 | 测试数 | 通过 | 说明 |
|----------|--------|------|------|
| test_frame.py | 16 | 16 | BE21 帧解析：MAGIC 校验、帧解析、cmd 范围、截断、偏移 |
| test_crypto.py | 15 | 15 | AES 解密：加解密往返、密钥解析、错误处理、文件 I/O |
| test_loader.py | 23 | 23 | 数据加载：bundle 加载、属性/技能/精灵查询、缓存失效 |

所有测试使用真实数据，不使用 mock。

## 下一步 (Phase 2)

1. 构建完整属性克制矩阵 `data/game/type_chart.json`
2. 实现属性克制计算器 `src/game/type_chart.py`
3. 实现种族值/能力值计算 `src/game/stats.py`
4. 实现 Wiki 爬虫 `src/data/scraper.py`
5. 阶段 2 测试和报告
