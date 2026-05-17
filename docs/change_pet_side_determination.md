# change_pet 事件侧边判断分析

## 背景

`_handle_change_pet_entry` 需要判断换宠发生在哪方（我方/对方）。之前的代码用 `target_side >= 401` 作为判断依据，但在对方是房主的对局中会导致误判，使对方宠物列表膨胀。

## 根因

### BattleChangePet protobuf 定义

来源：`references/Roco-Kingdom-World-Data/PB/proto_out/battle_data.proto`

```protobuf
message BattleChangePet {
  uint32 player_id = 1;          // 换宠的玩家 ID
  uint32 rest_pet_id = 2;        // 被换下的宠物位置编号
  uint32 battle_pet_id = 3;      // 换上的宠物位置编号
  BattlePetInfo battle_pet_info = 4;  // 换上宠物的完整信息
  bool is_cmd = 5;               // 是否玩家主动操作（vs 自动触发）
  ChangePetPerformType perform_type = 6;  // 0=普通, 1=无球
}
```

### 字段语义误解

`_extract_actor_target()` 通用提取函数将 field 1 读为 `actor_side`、field 2 读为 `target_side`。这对 damage/skill_cast 等事件正确（caster_id/target_id），但对 change_pet 不适用：

- `actor_side` 实际是 `player_id`（换宠玩家的 ID），不是位置编号
- `target_side` 实际是 `rest_pet_id`（被换下的宠物位置编号），不是 side 标识

### 位置编号分配规则

`rest_pet_id` 和 `battle_pet_id` 使用 1-6 或 401-406 范围的位置编号。**分配取决于谁是房主**：

| Session | creater_uin | 房主身份 | 房主位置范围 | 对手位置范围 |
|---------|-------------|---------|------------|------------|
| 1 | 336636521 | 我方 | 1-6 | 401-406 |
| 4 | 906454483 | 对方 | 1-6 | 401-406 |
| 5 | 8289533 | 对方 | 1-6 | 401-406 |
| 6 | 336636521 | 我方 | 1-6 | 401-406 |

规律：**房主方始终使用 1-6，对手方始终使用 401-406**。

因此 `side_name()` 硬编码的 `1-6=我方、401+=敌方` 在对方是房主时是反的。

### player_id 的值

`player_id` (field 1) 标识换宠的玩家，但格式不固定：

| Session | 我方 player_id | 对方 player_id |
|---------|---------------|---------------|
| 1 | 336636521 (UIN) | 4 (小数字) |
| 4 | 336636521 (UIN) | 906454483 (UIN) |
| 5 | 336636521 (UIN) | 8289533 (小数字) |
| 6 | 336636521 (UIN) | 1040396965 (UIN) |

`player_id` 等于 `creater_uin`（房主）或对手的某种 ID。格式取决于服务器版本或对手类型，不能作为可靠的 side 判断依据。

## 当前解决方案

`_handle_change_pet_entry` 使用多级判断链：

1. 用 `rest_pet_id` 匹配已知 `opp_pets`/`my_pets`（通过 pet_id）
2. 用 `new_pet_id` 匹配已知宠物列表
3. 用已知 slot 映射
4. 用当前活跃宠物匹配
5. Fallback: `target_side >= 401`

同时维护 `_position_side` 缓存避免重复匹配。

## wrapper side vs change_pet 位置编号

两套独立的编号体系，不能混用：

- **wrapper side**（battle_enter / round_start）：`side=1` 恒为我方，`side=401` 恒为对方。由 protobuf 结构位置决定（`player_team` field 5 vs `enemy_team` field 6），是服务器保证的。
- **change_pet 位置编号**（rest_pet_id / battle_pet_id）：1-6 和 401-406 的分配取决于谁是房主，不固定。

## 自动换宠机制

`is_cmd=0` 表示非玩家主动操作的自动换宠。已观察到的触发场景：
- 能量为 0 时自动切换宠物上场
- 宠物被击败后自动补宠

自动换宠和主动换宠使用相同的 BattleChangePet 消息，仅 `is_cmd` 字段不同。双方的自动换宠都会触发 change_pet 事件。
