# Roco-Kingdom-World-Data 参考

详细参考文档已从 CLAUDE.md 提取。

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
| `PETBASE_CONF.json` | `data/game/pet_species.json` | 已导入：1015 个物种完整数据（种族值/属性/特性/进化ID） |
| `SKILL_CONF.json` | `data/game/skill_map.json` | 已导入：含完整 skill_result 效果链 |
| `LEVEL_SKILL_CONF.json` | `data/game/pet_skill_map.json` | 已导入：升级/技能石/血脉技能完整映射 |
| `TYPE_DICTIONARY.json` | `data/game/type_chart.json` | 已导入：含 type_immunity 数据 |
| `BUFFBASE_CONF.json` | `data/game/buffbase_map.json` | 官方 buff 参数定义 |
| `BUFF_CONF.json` | `data/game/buff_map.json` | buff 完整配置 |
| `PET_EVOLUTION_CONF.json` | `data/game/evolution_map.json` | 已导入：309 条进化链 |
| `NATURE_CONF.json` | `data/game/nature_map.json` | 已导入：31 个性格定义 |
| `BATTLE_GLOBAL_CONFIG.json` | `data/game/battle_config.json` | 已导入：528 个战斗全局参数 |
| `WEATHER_CONF.json` | `data/game/weather_map.json` | 已导入：13 种天气类型 |
| `battle_data.proto` | `data/game/proto_schema.json` | protobuf 结构权威定义 |
| `PB/proto_out/*.proto` | `protocol/proto_core.py` | 协议解析字段级参考 |

#### 何时参考此仓库

- **验证或补充宠物/技能数据**：PETBASE_CONF 和 SKILL_CONF 是最权威的数据源，已通过 `scripts/import_bin_data.py` 全量导入
- **扩展技能效果解析**：`skill_result` 数组包含完整的效果链（effect_id + success_rate + cast_moment），是伤害计算 hook 系统的核心参考
- **理解 buff 叠加规则**：`buff_groupsigns`（同组互斥）、`buff_list_priority`（优先级）、`add_max`（叠加上限）、`connect_buff`（联动）
- **解析新协议字段**：.proto 文件提供完整的 protobuf 字段定义和编号，是 `proto_core.py` 和 `battle.py` 的权威参考
- **添加性格系统**：NATURE_CONF 提供性格对属性的加减效果，计算实际属性时必需
- **添加进化链展示**：PET_EVOLUTION_CONF 提供完整进化链、阶段和等级要求
- **理解战斗状态流程**：BattleFsm 定义 30+ 状态节点，proto 定义完整的状态枚举
- **扩展 PvP 模式支持**：PVP_CONF + PVP_RANK_* 文件定义所有对战模式的规则和配置
