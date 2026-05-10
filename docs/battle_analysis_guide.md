# 对战包分析指南

本文档说明如何从捕获的二进制包文件中解析、提取、分析一局完整对战数据。供后续 Agent 在进行对战数据分析时参考。

---

## 1. 整体管线概览

```
.bin 文件 (RC01 格式)
  │  tests/packet_reader.py :: read_bin_packet()
  ▼
pkt dict (cmd, seq, direction, decrypted_body_hex, ...)
  │  src/protocol/proto_core.py :: parse_record()
  ▼
record dict (opcode, root, direction, seq, ...)
  │  src/protocol/opcodes.py :: summarize()
  ▼
(kind, summary) — 按 opcode 分派的语义化结果
  │  src/analysis/battle_state.py :: BattleStateTracker
  ▼
battle_state — 实时更新的对战状态快照
```

**核心调用链**：`read_bin_packet` → `parse_record` → `summarize` → `tracker.handle_event`

---

## 2. 二进制包文件格式 (RC01)

文件由 `PacketLogger` 按以下结构写入，文件名格式为 `{direction}_{cmd_hex}_{seq:04d}_{HHMMSS.mmm}.bin`。

| 偏移 | 长度 | 字段 |
|------|------|------|
| 0 | 4 | Magic: `RC01` |
| 4 | 2 (BE) | `cmd` — TGCP 命令号 (0x4013=DATA, 0x1002=ACK) |
| 6 | 4 (BE) | `seq` — 序列号 |
| 10 | 4 | `direction` — `"s2c"` 或 `"c2s"` (null-padded ASCII) |
| 14 | 4 (BE) | `hdr_extra_len` + N 字节 header_extra |
| 18+N | 4 (BE) | `body_len` + N 字节加密 body |
| 22+N+M | 4 (BE) | `decrypted_len` + N 字节**已解密** body |
| ... | 4 (BE) | `meta_len` + N 字节 JSON metadata |

**关键**：对战分析使用 `decrypted_body_hex` 字段（已解密的明文），不需要手动解密。

读取方式：
```python
from tests.packet_reader import read_bin_packet
pkt = read_bin_packet(Path("tests/fixtures/packets/battle_session_1/s2c_0x4013_1599_212333.620.bin"))
# pkt["cmd"] == 0x4013
# pkt["direction"] == "s2c"
# pkt["decrypted_body_hex"] — 明文 hex
```

---

## 3. 协议层解析

### 3.1 parse_record — 从明文 body 提取业务 record

```python
from src.protocol.proto_core import parse_record

record = parse_record(pkt)  # pkt 必须有 cmd=0x4013 和 decrypted_body_hex
```

record 结构核心字段：
- `opcode` (int) — 业务操作码，如 0x1316、0x1324 等
- `opcode_hex` (str) — 如 `"0x1316"`
- `direction` — `"s2c"` / `"c2s"`
- `seq` — 传输序号
- `root` — 递归解析后的 protobuf-like 消息树

### 3.2 root 消息树结构

`root` 是一个递归字典：
```python
{
    "fields": [
        {"field": 1, "wire": 0, "value": 42},           # varint
        {"field": 2, "wire": 2, "raw_hex": "...", "sub": {  # 嵌套消息
            "fields": [...]
        }},
        {"field": 3, "wire": 2, "text": "火龙"},         # UTF-8 字符串
    ],
    "consumed": 45,
    "clean": True
}
```

**常用提取工具函数**（来自 `proto_core.py`）：
- `field_groups(msg)` → `{field_no: [entries]}` 按字段号分组
- `collect_varints(msg, field_no)` → `[int, ...]` 提取 varint 值列表
- `pick_first(values, low=None, high=None)` → 取第一个（可选范围过滤）
- `first_text(msg, field_no)` → 提取第一个文本值
- `first_sub(entries)` → 取第一个有 `sub` 的 entry 的 sub

### 3.3 侧别 (side) 约定

| 值 | 含义 |
|----|------|
| 1 | 我方 (player) |
| 2–6 | 我方其他槽位 |
| 401 | 敌方 (opponent) |
| 402–406 | 敌方其他槽位 |

`side_name(side_id)` 返回 `"我方"` 或 `"敌方"`。

---

## 4. 对战操作码一览

### 4.1 核心战斗流程

| Opcode | Kind | 含义 | 提取函数 |
|--------|------|------|----------|
| 0x1316 | `battle_enter` | 对战开始 | `extract_1316_enter()` |
| 0x131A | `round_start` | 回合开始 | `extract_131a_round_start()` |
| 0x130B | `client_skill_select` | 玩家选技能 | `extract_130b_skill_select()` |
| 0x1322 | `server_skill_declare` | 服务端技能声明 | `extract_1322_skill_declare()` |
| 0x1324 | `action_resolve` | 回合执行结果 | `extract_1324_action()` |
| 0x130C | `server_action_ack` | 服务端执行确认 | `extract_130c_result()` |
| 0x1312 | `round_flow` | 回合流程控制 | `extract_1312_round_flow()` |
| 0x1313 | `round_confirm` | 回合确认 | 通用字段提取 |
| 0x1314 | `round_confirm_rsp` | 回合确认响应 | 通用字段提取 |
| 0x132C | `battle_finish` | 对战结束 | `extract_132c_finish()` |

### 4.2 特殊动作与辅助

| Opcode | Kind | 含义 |
|--------|------|------|
| 0x13F4 | `special_refresh` | 技能选项刷新/能量瓶 |
| 0x13FC | `pvp_perform` | PvP 执行指令 (同 0x1324 结构) |
| 0x13F3 | `preplay` | 预演指令 (同 0x1324 结构) |
| 0x13F6 | `ai_skill` | AI 技能推荐 |
| 0x1326 | `auto_cmd` | 自动战斗切换 |
| 0x132A | `role_leave` | 玩家离开 |
| 0x132D | `force_finish` | 强制结束 |
| 0x1334 | `emoji` | 对战表情 |
| 0x133C | `catch_rsp` | 捕获结果 |

### 4.3 非战斗但有用的操作码

| Opcode | 含义 |
|--------|------|
| 0x0102 | `roster_init` — 精灵背包初始化 |
| 0x01A9 | `client_action` — 动作候选 |
| 0x0220 | `snapshot_handle` — 场景快照句柄 |

完整战斗操作码集合（`BATTLE_OPCODES`）：
```python
{0x1316, 0x131A, 0x130B, 0x1322, 0x1324, 0x130C,
 0x1313, 0x1314, 0x132C, 0x13F4, 0x13FC, 0x13F3, 0x1312}
```

---

## 5. 关键数据结构

### 5.1 battle_enter (0x1316) detail

```python
{
    "battle_id": int,           # 对战唯一ID
    "battle_mode": int,         # 对战模式
    "round": 0,                 # 初始回合数
    "max_round": int,           # 最大回合数 (PvP 通常 30)
    "weather_id": int,          # 天气ID
    "wrappers": [               # 所有在场精灵的初始状态
        {
            "name": "火龙",
            "pet_id": 100,
            "level": 50,
            "slot": 1,
            "side": 1,           # 1=我方, 401=敌方
            "types": [1],        # 属性列表
            "max_hp": 300,
            "current_hp": 300,
            "energy": 5,
            "battle_stats": [...], # [max_hp, atk, def, spa, spd, spe]
        },
        ...
    ],
}
```

### 5.2 action_resolve (0x1324) detail

```python
{
    "packet_state": int,
    "packet_phase": int,
    "packet_index": int,
    "entries": [
        # entry_type=1: 技能施放
        {
            "kind": "skill_cast",
            "skill_id": 7700001,
            "skill_name": "愿力冲击",
            "actor_side": 1,          # 施放方
            "actor_side_name": "我方",
            "target_side": 401,
            "target_side_name": "敌方",
            "energy_delta": -2,
            "energy_after": 3,
        },
        # entry_type=4: 伤害
        {
            "kind": "damage",
            "damage": 120,
            "target_hp_after": 180,
            "damage_target_side": 401,
            "damage_target_side_name": "敌方",
            "skill_id": 7700001,
            "skill_name": "愿力冲击",
            "overflow": 0,           # 溢出伤害
        },
        # entry_type=2: 效果施加
        {
            "kind": "effect_apply",
            "effect_id": 1001,
            "effect_name": "灼烧",
            "actor_side": 1,
            "target_side": 401,
        },
        # entry_type=3: 效果阶段
        {
            "kind": "effect_stage",
            "effect_id": 1001,
            "effect_name": "灼烧",
            "effect_base": 2001,
            "effect_base_name": "灼烧基础",
        },
        # entry_type=7: 击败
        {
            "kind": "defeat",
            "actor_side": 401,       # 被击败方
            "actor_side_name": "敌方",
        },
        # entry_type=10: 效果链接
        {
            "kind": "effect_link",
            "effect_id": 1001,
        },
        # entry_type=30: 连击技能施放
        {
            "kind": "combo_skill_cast",
            "skill_id": 7700001,
            "skill_name": "缠丝劲",
            "actor_side": 1,
            "actor_side_name": "我方",
            "combo_index": 3,         # 当前第几击
            "combo_count": 7,         # 总连击数
            "target_ids": [401],      # 目标列表
        },
    ],
    "primary_skill": {...},         # 主技能 entry
    "energy_event": {...},          # 能量变化 entry
    "damage_event": {...},          # 伤害 entry
    "has_defeat": False,            # 是否有击杀
    "effect_ids": [1001],
    "effect_names": ["灼烧"],
}
```

### 5.3 battle_finish (0x132C) detail

```python
{
    "result_code": 2,               # 结果码
    "result_name": "WIN",           # 可读结果
    "battle_id": int,
    "rounds": 5,                    # 总回合数
    "seconds": 120,                 # 对战时长(秒)
    "pvp_score": int,               # PvP 积分变化
    "total_pvp_score": int,         # PvP 总积分
    "finish_pet_infos": [           # 对战结束时各精灵HP
        {"pet_gid": 100, "remain_hp": 200, "remain_energy": 3, "battle_max_hp": 300},
        {"pet_gid": 200, "remain_hp": 0, "remain_energy": 0, "battle_max_hp": 350},
    ],
}
```

结果码映射 (`BATTLE_RESULT_MAP`)：
| 码 | 结果 |
|----|------|
| 2 | WIN |
| 4 | LOSE |
| 10 | MONSTER_RUNAWAY |
| 12 | RUNAWAY |
| 18 | WIN_DEFEAT |
| 34 | WIN_CATCH |
| 66 | WIN_HP |
| 260 | RUNAWAY_ROLE_MAGIC |

---

## 6. 对战状态追踪 (BattleStateTracker)

`BattleStateTracker` 是一个有状态的状态机，通过 `handle_event(opcode, detail)` 消费事件并维护完整对战状态。

### 6.1 状态结构

```python
state = {
    "battle_id": int | None,
    "battle_mode": int | None,
    "round": int,                   # 当前回合
    "max_round": int,
    "weather_id": int | None,
    "result": "WIN" | "LOSE" | ... | None,
    "my_pets": [pet_info, ...],     # 我方所有精灵
    "opp_pets": [pet_info, ...],    # 敌方所有精灵
    "my_active": pet_info | None,   # 我方当前出战精灵
    "opp_active": pet_info | None,  # 敌方当前出战精灵
    "events": [event_dict, ...],    # 所有处理过的事件日志
}
```

### 6.2 pet_info 结构

```python
{
    "pet_id": int,
    "name": str,
    "types": [int],
    "current_hp": int,
    "max_hp": int,
    "hp_pct": float,               # 0.0 ~ 1.0
    "energy": int,                  # 当前能量
    "buffs": [],
    "combo_bonus": int,             # 连击数修正值（combo_skill_cast 事件更新，换宠时重置）
    "poison_stacks": int,           # 中毒层数（effect_apply 中 POISON_BUFF_IDS 事件更新）
}
```

### 6.3 事件处理规则

| opcode | 行为 |
|--------|------|
| 0x1316 | 重置状态，初始化双方精灵列表和 active |
| 0x131A | 更新回合号，从 wrappers 同步精灵状态（含换人检测） |
| 0x1324 | 处理 entries：damage 更新HP、skill_cast 更新能量、defeat 归零HP |
| 0x130B | 仅记录（客户端意图） |
| 0x1322 | 仅记录（服务端声明） |
| 0x13F4 | 处理能量瓶等特殊动作 |
| 0x1312 | 更新回合号 |
| 0x132C | 设置胜负结果，更新所有精灵最终HP |

### 6.4 换人检测

当 `round_start` (0x131A) 的 wrappers 中出现新精灵时，tracker 自动将其添加到对应方精灵列表并更新 active。精灵匹配规则：
- 优先按 `pet_id` 匹配
- 对手方通用 ID (20000000) 时，回退到 `slot` 或 `name` 匹配

### 6.5 实时建议

```python
suggestions = tracker.get_suggestions()
# 返回如: [{"type": "low_hp", "message": "我方精灵HP过低，考虑换宠"}, ...]
```

建议类型：`low_hp`、`hp_ok`、`finish_off`、`low_energy`、`debuffed`

---

## 7. 完整回放一局对战的标准流程

使用 `tests/packet_reader.py` 中的工具函数：

```python
from pathlib import Path
from tests.packet_reader import load_battle_packets, replay_battle

# 1. 加载并过滤战斗包
session_dir = Path("tests/fixtures/packets/battle_session_1")
packets = load_battle_packets(session_dir)
# 返回: [{"packet": pkt, "record": record, "opcode": int, "filename": str}, ...]
# 已按时间排序，仅包含 BATTLE_OPCODES 中的包

# 2. 回放整局对战
events, final_state = replay_battle(packets)
# events: 每个包的处理结果列表
#   [{"opcode", "kind", "detail", "state", "filename"}, ...]
# final_state: 对战结束时的完整状态快照

# 3. 提取分析结果
result = final_state["result"]           # "WIN" / "LOSE" / ...
my_pets = final_state["my_pets"]         # 我方精灵列表及最终HP
opp_pets = final_state["opp_pets"]       # 敌方精灵列表及最终HP
opp_names = [p["name"] for p in opp_pets]  # 对手精灵名列表
total_rounds = final_state["round"]      # 总回合数
```

### 7.1 手动逐步回放（更细粒度控制）

```python
from src.analysis.battle_state import BattleStateTracker
from src.protocol.proto_core import extract_inner_message
from src.protocol.opcodes import summarize
from tests.packet_reader import load_battle_packets

packets = load_battle_packets(session_dir)
tracker = BattleStateTracker()

for item in packets:
    record = item["record"]
    opcode = item["opcode"]

    # 对于 0x0414 (inner message)，需要额外提取
    inner = None
    if opcode == 0x0414:
        inner = extract_inner_message(record.get("root", {}))

    kind, summary = summarize(record, inner)
    detail = summary.get("detail", summary) or {}
    state = tracker.handle_event(opcode, detail)

    # 此时 state 是最新快照
    if kind == "action_resolve":
        print(f"回合 {state['round']}: {detail.get('primary_skill', {}).get('skill_name')}")
```

---

## 8. wrappers 提取（精灵状态快照）

`extract_state_wrappers_from_record(record)` 可从任意包含精灵信息的 record 中提取所有在场精灵的状态。常用于 battle_enter 和 round_start。

```python
from src.protocol.proto_core import extract_state_wrappers_from_record

wrappers = extract_state_wrappers_from_record(enter_record)
# 返回去重后的 wrapper 列表:
# [
#   {"name": "火龙", "pet_id": 100, "side": 1, "level": 50,
#    "types": [1], "max_hp": 300, "current_hp": 300, "energy": 5,
#    "battle_stats": [300, atk, def, spa, spd, spe], "slot": 1},
#   {"name": "水龟", "pet_id": 200, "side": 401, ...},
# ]
```

side 判定逻辑（`_side_from_path`）：
- 路径含 `.6[N].5[N]` → side=1（我方）
- 路径含 `.6[N].6[N]` → side=401（敌方）
- 路径含 `.8[N].` → side=401（敌方，round_start 格式）

---

## 8.1 伤害计算管线

伤害计算由 `DamageCalculator` (`src/analysis/damage_calc.py`) 驱动，输出 `DamageResult` 数据结构。

```python
from src.analysis.damage_calc import DamageCalculator
from src.analysis.innate_hooks import register_innate_hooks

calc = DamageCalculator()
register_innate_hooks(calc)  # 注册先天技能 Hook（必须显式调用）

result = calc.calculate(
    attacker={"types": [1], "current_hp": 200, "max_hp": 300, ...},
    defender={"types": [2], "max_hp": 250, "current_hp": 250, ...},
    skill_meta=get_skill_meta(7700001),
)
# result: DamageResult 或 None（非攻击技能）
# result.hit_count — 连击数
# result.total_min_damage / total_max_damage — 连击总伤害
# result.can_ko — 是否能击杀
```

`DamageResult` 关键字段:
- `min_damage` / `max_damage`: 单次命中伤害
- `hit_count`: 连击次数（默认 1）
- `total_min_damage` / `total_max_damage`: 总伤害 = 单次 × 连击
- `can_ko`: 总伤害是否 >= 目标当前 HP
- `effectiveness` / `effectiveness_label`: 属性克制倍率
- `confidence`: "high" (抓包数据) 或 "medium" (wiki 估算)

4 阶段 Hook 管线:

| 阶段 | 上下文字段 | 用途 |
|------|-----------|------|
| `pre_power` | power, skill_meta, attacker, defender | 修正技能威力 |
| `post_base` | base_damage, atk_val, def_val | 修正基础伤害 |
| `pre_final` | base_damage, effectiveness, stab_mult | 修正属性克制/本系修正 |
| `post_calc` | min_damage, max_damage, hit_count | 修正最终伤害/连击数 |

先天技能 Hook (`src/analysis/innate_hooks.py`):

| Hook 函数 | 注册阶段 | effect_type | 效果 |
|-----------|---------|-------------|------|
| `stat_modify_hook` | post_base | stat_modify | HP 低于阈值时百分比提升伤害 |
| `type_resist_modify_hook` | pre_final | type_resist_modify | 提升属性克制倍率下限 |
| `combo_modify_hook` | post_calc | combo_modify | 增加连击次数 |
| `power_modify_hook` | post_calc | power_modify | 附加效果如先手吸血 |

---

## 9. 游戏数据查询

通过 `src/data/loader.py` 可查询静态游戏数据：

```python
from src.data.loader import get_pet_name, get_skill_name, get_skill_meta, get_attr_name
from src.data.loader import get_pet_meta, get_pet_skill_meta, get_buff_meta, get_buffbase_meta
from src.data.loader import get_innate_skill, get_innate_skills_for_pet

get_pet_name(100)                  # → "火龙"
get_skill_name(7700001)            # → "愿力冲击"
get_skill_meta(7700001)            # → {"desc": ..., "energy_cost": 2, "damage_type": ..., ...}
get_attr_name(1)                   # → "火"（属性名）
get_pet_meta(100)                  # → {"base_id": ..., "pet_info_id": ...}
get_pet_skill_meta(base_id)        # → {"level_skills": [...]}（技能池）
get_buff_meta(buff_id)             # → {"name": "灼烧"}
get_buffbase_meta(base_id)         # → {"name": "灼烧基础"}
get_innate_skill(buff_id)          # → {"name": "无视抵抗", "effect_type": "type_resist_modify", ...}
get_innate_skills_for_pet(base_id) # → [{"name": "...", "effect_type": "combo_modify", ...}]
```

### 游戏逻辑模块 (src/game/)

| 模块 | 说明 |
|------|------|
| `src/game/type_chart.py` | `TypeChart` 类 — 加载 type_chart.json，提供倍率查询、弱点分析、覆盖度计算 |
| `src/game/stats.py` | 种族值/能力值计算 — `calc_hp()`, `calc_stat()`, `calc_all_stats()`, 性格修正 |
| `src/game/skill_eval.py` | 技能评分 — `score_skill()` (0-100 分), `rank_skills()` 排序 |

```python
from src.game.type_chart import TypeChart
from src.game.stats import calc_all_stats
from src.game.skill_eval import score_skill, rank_skills

chart = TypeChart()
chart.get_multiplier(1, [2])          # → 2.0 (火→草)
chart.get_effectiveness_label(2.0)     # → "效果拔群"

calc_all_stats([100,80,70,90,85,95], level=50, nature="固执")
score_skill({"power": 90, "energy_cost": 3, "accuracy": 100})
```

---

## 10. 常见分析任务示例

### 10.1 统计对手精灵阵容

```python
_, state = replay_battle(load_battle_packets(session_dir))
opp_team = [{"name": p["name"], "types": p["types"], "max_hp": p["max_hp"]} for p in state["opp_pets"]]
```

### 10.2 按回合统计伤害

```python
events, _ = replay_battle(packets)
for e in events:
    if e["opcode"] == 0x1324:
        for entry in e["detail"].get("entries", []):
            if entry.get("kind") == "damage":
                print(f"回合{e['state']['round']}: {entry.get('damage')} 伤害 → {entry.get('damage_target_side_name')}")
```

### 10.3 提取对战中的技能使用序列

```python
for e in events:
    if e["kind"] == "action_resolve":
        skill = e["detail"].get("primary_skill")
        if skill:
            print(f"{skill['actor_side_name']} 使用 {skill['skill_name']}")
```

### 10.4 判断胜负及积分

```python
_, state = replay_battle(packets)
print(f"结果: {state['result']}")

# 从 finish 事件获取积分
finish_events = [e for e in events if e["opcode"] == 0x132C]
if finish_events:
    d = finish_events[0]["detail"]
    print(f"PvP 积分: {d.get('pvp_score')}, 总分: {d.get('total_pvp_score')}")
```

---

## 11. 注意事项

1. **包的方向**：`s2c` = 服务端下发的结果数据（HP变化、伤害、效果），`c2s` = 客户端发送的操作意图（选技能）。分析对战结果主要看 `s2c` 包。

2. **opcode 0x0414**：这是一个包装 opcode，实际业务含义在 `inner message` 中。需要用 `extract_inner_message()` 解包后再 `summarize`。

3. **技能ID约定**：游戏中技能 ID 有两种格式——原始 ID（如 77000）和 ×100 格式（如 7700000）。`normalize_skill_id()` 自动处理转换。

4. **精灵匹配**：PvP 对手的 pet_id 可能是通用值 20000000，需要通过 slot 或 name 做二次匹配。

5. **tsf4g padding**：payload 末尾可能有 `tsf4g` 标记的填充字节，`strip_tsf4g_padding()` 自动处理。

6. **Schema vs Raw 回退**：部分 opcode 提取函数支持"schema-first"——如果 record 有 `_decoded` 字段（proto schema 预解析），优先使用 schema 结果，否则回退到原始字段遍历。`parse_quality` 字段标识使用了哪种路径。

7. **能量系统**：初始能量为 5，上限为 10。能量瓶 (`energy_bottle`) 可回复能量。

8. **特殊动作**：除技能外还有三种特殊操作——愿力强化 (`action_name="愿力强化"`)、能量瓶 (`action_name="能量瓶"`)、换人 (`action_name="换人"`)。
