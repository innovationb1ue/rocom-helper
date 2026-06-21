# 架构说明

本文档记录后端核心模块边界和允许的依赖方向。目标是让实时抓包、无头回放和前端展示共用同一套战斗语义与分析管线。

## 分层主线

```text
capture -> protocol -> analysis -> api -> web
              ^           ^
              |           |
          data/game/config
```

- `src/capture/`：只负责网络流量、TCP 重组、BE21 帧、解密和抓包记录，不承担战斗业务判断。`capture/sniffer.py` 保留 Scapy 编排和帧处理主流程；flow 生命周期、preset key 和 status 快照放在 `capture/flow_registry.py`；TCP flow key、包方向、FIN/RST 关闭原因等包级路由规则放在 `capture/packet_flow.py`；ACK 密钥帧去重、key 写入和 key 捕获事件放在 `capture/sniffer_key_events.py`；非 DATA 控制帧转换放在 `capture/sniffer_control_events.py`；DATA 帧解密、parse、summary、日志和 record 分发放在 `capture/sniffer_data_events.py`；缺 key 降级、parse_fail 方向性计数等抓包事件策略放在 `capture/sniffer_events.py`，便于脱离 Scapy 独立测试。
- `src/protocol/`：把 TGCP/Protobuf 记录转换为 opcode 语义 detail。`protocol.proto_core` 和 `protocol.battle` 是兼容门面；底层 wire/schema/tree 工具放在 `protocol/proto/`，战斗 opcode 语义解析放在 `protocol/battle_parts/`。
- `src/analysis/`：消费 opcode detail，维护战斗状态、格式化事件、伤害预测、hook 建议和战术推荐。实时路径与回放路径都从 `BattleProcessor` 进入，处理策略放在 `processor_policy.py`。
- `src/api/`：只做 FastAPI/WebSocket 编排、sniffer 生命周期和 replay service，不直接承载协议语义。
- `web/`：消费 API/WebSocket 消息并展示，不反向编码协议解析规则。

## 依赖规则

- 允许：`capture -> protocol`、`analysis -> protocol/data/game`、`api -> analysis/capture`、`web -> api contract`。
- 禁止：`protocol -> analysis/api`、`data -> analysis/api`、`game -> analysis/api`。
- `src.data.loader` 是兼容门面；新增数据领域逻辑应优先放入 `src/data/*` 内部模块，再由 loader re-export。
- 使用 `py -m scripts.check_architecture` 或 `pytest tests/test_architecture.py -v` 检查 import cycle 和禁止依赖边。

## 实时与回放共享路径

- 实时抓包：`SnifferManager -> BattleManager -> BattleProcessor -> build_battle_messages -> WebSocket`。
- 无头回放：`BattleReplayRunner -> BattleProcessor -> ReplayResult`。
- API fixture 回放：`routes_battle -> replay_service -> BattleManager -> BattleProcessor`。

三条路径都应保持相同的 opcode detail 和状态更新语义。新增战斗行为时，优先在 `BattleProcessor`/`BattleStateTracker`/`event_formatter`/hook 中实现一次，再由实时和回放复用。

## 报告与回放边界

- `src.analysis.replay_runner.BattleReplayRunner` 保留无头回放兼容入口，只负责创建 `BattleProcessor`、迭代 packets 和组装最终 `ReplayResult`。
- `src.analysis.replay_models` 放无头回放公开结果 dataclass；`src.analysis.replay_flow` 只负责单包 detail 归一化、ProcessResult 输出开关、ReplayEventSnapshot 构造、RoundSnapshot 聚合和 stop_round 判定。
- `src.analysis.battle_report` 保留报告 API 兼容门面，负责报告 summary、manifest、zip 打包、归档和 compact analysis 的编排。
- `src.analysis.reporting.analysis` 只负责报告用轻量回放分析和 compact WebSocket-like 消息生成，不持有报告文件系统/zip 逻辑。
- `src.analysis.reporting.catalog` 只负责报告列表、summary、diagnostics 和归档状态标记。
- `src.analysis.reporting.lookup` 只负责 report id 解析和从 packet root 定位具体 battle boundary。
- `src.analysis.reporting.package` 只负责 manifest、`.raco-report` zip 打包、缓存读取和归档写入。
- `src.analysis.reporting.packet_io` 只负责 RC01 `.bin` 包和 metadata 的底层读取、opcode hex 和文件时间戳解析。
- `src.analysis.reporting.window` 只负责从抓包 session 中扫描战斗边界、选择导出窗口文件，以及把窗口内战斗包加载为 replay packet dict。
- `src.analysis.reporting.models` 放报告扫描层共享的异常和边界 dataclass，避免底层模块反向依赖 `battle_report` 门面。

## Processor 编排边界

- `src.analysis.battle_processor.BattleProcessor` 保留实时和回放共用的同步处理入口，负责持有 tracker/advisor/hook registry/tactical engine 并委托单事件 flow。
- `src.analysis.processor_event_flow` 只负责单个事件的状态更新、格式化、伤害分析、战术推荐、hook 和 suggestions 编排。
- `src.analysis.processor_policy` 只判断何时 snapshot、何时做伤害分析、何时做 tactical，不持有状态。
- `src.analysis.processor_analysis` 只负责 BattleAdvisor 调用、action_resolve 投影态回退、TacticalEngine 调用和 prediction reliability 写回。
- `src.analysis.processor_hooks` 只负责默认 hook registry 创建和旧 helper 入口委托；opcode 到 `HookTrigger` 的映射、HookContext 构造、hook lifecycle flow、`_hook_signals` 写回和 advice 序列化放在 `processor_hook_flow.py`。
- `src.analysis.processor_outputs` 只负责格式化事件开关、state suggestions 和 `ProcessResult` 组装。
- `src.analysis.hook_registry.HookRegistry` 只负责 hook 注册和兼容方法入口；具体 dispatch、lifecycle notify、signal 收集和 reset 循环放在 `hook_dispatch.py`，便于独立测试异常隔离和触发过滤。
- `src.analysis.hooks.switch_advisor.SwitchAdvisorHook` 只负责 hook 生命周期入口和 `HookAdvice`/`HookSignal` 包装；换宠建议的对位判断、对手换宠识别、counter 选择和消息组装放在 `hooks/switch_advice.py`，便于独立测试。
- `src.analysis.hooks.energy_monitor.EnergyMonitorHook` 只负责能量日志和 hook 输出包装；最低攻击耗能、我方/对手能量提示、优先级和 avoid-skill 信号规则放在 `hooks/energy_advice.py`，便于独立测试。
- `src.analysis.hooks.opponent_tracker.OpponentTrackerHook` 只负责对手行为状态容器、生命周期和 `HookAdvice` 包装；技能归属、技能偏好、换宠日志、低血换宠模式和 data payload 组装放在 `hooks/opponent_behavior.py`，便于独立测试。
- `src.analysis.state_projector` 保留 action_resolve 预测前状态投影入口，只做 state 深拷贝和 entry kind 分发；具体投影逻辑放在 `analysis/projection/`：
  - `core.py`：side 到 active pet 的共享解析。
  - `effects.py`：effect_apply/effect_stage 的 buff 投影和毒层同步。
  - `resources.py`：energy、skill_cast、combo_skill_cast 的能量/技能记录投影。
  - `pets.py`：change_pet 的 active 指针投影和宠物匹配。
  - `field.py`：weather_change 场地投影。
- `src.analysis.battle_advisor.BattleAdvisor` 保留伤害分析兼容入口；advisor 子逻辑放在 `analysis/advisor/`：
  - `skill_analysis.py`：装备技能到 `SkillAnalysis`、伤害预测填充和技能质量评分。
  - `suggestions.py`：KO、效果拔群、被抵抗、能量不足和 counter switch 建议。
  - `traits.py`：物种、协议 innate id 和 innate buff 的特性提取去重。
- `src.analysis.damage_calc.DamageCalculator` 保留单技能/技能列表伤害计算兼容入口；伤害子逻辑放在 `analysis/damage/`：
  - `calculator_phases.py`：`DamageCalculator` 私有计算阶段 mixin，承接 server power rule、pre_power、基础伤害、倍率和 finalize 阶段。
  - `calculator_compat.py`：`DamageCalculator._*` 历史 helper mixin，保持旧测试/调试入口可用，同时让门面不直接持有运行时/属性读取细节。
  - `calculation.py`：单技能伤害计算阶段编排，串联 runtime、server power rule、power hook、combat stats、base formula、multipliers 和 finalize。
  - `formula.py`：NRC 基础伤害公式和防御下限处理。
  - `skill_resolution.py`：技能 damage_type、skill_dam_type 到属性映射、攻击技能判定，以及按 buff 修正进入公式前的固定威力。
  - `batch.py`：技能列表到 `DamageResult` 列表的批量计算和按总伤害排序。
  - `multipliers.py`：属性克制、STAB、天气、`pre_final` hook 和服务端展示/公式倍率的最终伤害倍率解析。
  - `result.py`：`DamageResult` 兼容结果模型、dict 重建、连击数解析和结果解释用 buff 展平。
  - `finalize.py`：post_calc 后的连击/能量/KO 结算、`damage_breakdown` 构造和最终 `DamageResult` 组装。
  - `hook_pipeline.py`：pre_power/post_base/pre_final/post_calc 四阶段 hook 注册、清空和顺序执行。
  - `calculator_config.py`：`DamageCalculator` 运行时配置归一化，包含 server power rule 的嵌套/旧格式兼容。
  - `combat_stats.py`：协议属性、PvP 模板属性、性格修正、buff 能力等级和 stat source/置信度解析。
  - `runtime.py`：状态机同步的 skill runtime 字段、目标 key、能耗和 runtime source 摘要。
  - `server_runtime.py`：服务端同步 damage params/restraint types 匹配，以及 server power rule 到倍率的转换。
- `src.analysis.damage_prediction.DamagePredictionService` 保留统一预测兼容入口；预测子逻辑放在 `analysis/damage/`：
  - `prediction_config.py`：伤害校准、特殊固定伤害规则和 server power rule 的只读配置 store。
  - `prediction_adjustments.py`：特殊规则和回放校准对 `DamageResult` 的调整。
  - `prediction_quality.py`：accuracy flags、对外 confidence 降级和 validation hint 文案规则。
  - `prediction_explain.py`：解释 payload 和 audit key 构造。
  - `prediction_payload.py`：顶层 prediction payload 字典契约组装。
  - `prediction_output.py`：保留旧 helper 入口的兼容门面。
  - `prediction_secondary.py`：毒囊等技能的直接伤害后附带二段效果规则，便于后续新增特殊结算而不扩张输出组装模块。
- `src.analysis.damage_audit` 保留回放伤害审计兼容入口；审计子逻辑放在 `analysis/damage/`：
  - `audit_samples.py`：回放事件到普通伤害/机制伤害审计样本的迭代提取。
  - `audit_models.py` / `audit_ledger.py` / `audit_runtime.py`：审计样本 dataclass、damage ledger 匹配和技能运行时对齐。
  - `audit_summary.py`：普通直接技能伤害样本的单场/多场统计、来源计数、候选策略误差和技能分组。
  - `audit_calibration.py`：审计报告到 damage calibration / special damage rule 配置草案的转换。
  - `audit_mechanism.py`：技能运行时伤害参数机制审计报告组装、候选 totals 和单样本分解校验；保留机制统计/建议兼容入口。
  - `audit_mechanism_stats.py`：机制审计策略误差、分解匹配率和字段存在率统计口径。
  - `audit_mechanism_recommendation.py`：机制审计推荐状态策略，独立判断样本不足、特殊技能保守处理和 damage-param 候选改进。
  - `audit_utils.py`：机制审计和样本对齐共用的小型类型转换/协议枚举工具。

## API 编排边界

- `src.api.battle_manager.BattleManager` 保留为兼容入口和单例门面，只协调 processor、WebSocket hub、sniffer bridge 注册和战斗结束归档调度。
- `src.api.battle_archive` 只负责 battle finish 后的自动报告归档策略、后台任务创建、sniffer session dir 查询和归档异常日志，避免 `BattleManager` 直接持有报告文件系统细节。
- `src.api.ws_hub.JsonWebSocketHub` 只管理 WebSocket 客户端列表、UTF-8 JSON 广播和失效连接清理，不理解战斗消息语义。
- `src.api.battle_sniffer_bridge` 只负责 BattleManager 与 SnifferManager 的 record callback 桥接、sniffer record 过滤、detail 提取和后台处理 task 创建；opcode 分组仍来自 `analysis.constants` 单一真相源。
- `src.api.battle_ws_commands` 只处理 `/ws/battle` 客户端上行控制消息，保持 `event`、`get_state`、`reset`、`request_counter_pick` 的旧响应契约。
- `src.api.battle_ws_endpoint` 只负责 `/ws/battle` 连接生命周期、原始文本 JSON 解码、断开清理和上行消息转发；`routes_battle` 只注册 WebSocket URL。
- `src.api.battle_route_actions` 只负责 battle REST route action 到 manager/replay helper 的委托，让 state/pets/effects/replay 行为可以脱离 FastAPI 独立测试。
- `src.api.battle_report_endpoints` 只负责 battle report REST payload、report id URL 解码、404 转换和 `.raco-report` 下载响应。
- `src.api.battle_replay_endpoint` 只负责 `/api/battle/replay` 的 fixture session 路径解析、缺失 session 兼容错误，以及调用 replay service。
- 这些 helper 使用 duck typing，避免直接依赖 FastAPI 类型，从而可以用 fake WebSocket/processor 独立单测。

## 兼容门面

- `src.protocol.proto_core` 保留 `parse_record()`、`parse_tgcp_control_packet()`、`parse_proto_message()`、`field_groups()`、`decode_proto_by_schema()`、`extract_*()` 等旧导入路径；底层 protobuf/TGCP 子逻辑放在 `protocol/proto/`：
  - `wire.py`：varint、protobuf wire tree 递归解析、TGCP tsf4g padding、c2s opcode normalization 和有符号整数转换。
  - `tree.py`：解析后 message tree 遍历、字段分组、文本/varint/首个值查询。
  - `schema.py`：`proto_schema.json` lazy-load、schema field 映射、scalar/packed decode 和 record schema view 附加。
  - `transport.py`：TGCP DATA/control 记录格式识别、payload root 构建、special heartbeat payload 和 schema view 附加。
  - `constants.py`：协议层 stat/side/SkillDamType/special action 常量，作为 protocol 与 analysis 常量桥接的源头。
  - `lookups.py`：技能、宠物、buff、side 名称查找，以及 actor/target/buff 元数据附加小工具。
  - `creature.py`：PetData/BattleInsidePetInfo 中宠物基础信息、技能、属性、初始 buff 的提取。
  - `state_wrapper.py`：战斗 state wrapper 提取、side path 判断和 wrapper 去重。
- `src.protocol.opcodes` 保留 opcode/inner message 注册清单和 `summarize()` 公开入口；注册表/装饰器放在 `protocol/opcode_registry.py`，opcode/inner 分发与 PB map fallback 放在 `protocol/opcode_dispatch.py`；0x0414 内嵌消息 detail 结构解析放在 `protocol/inner_messages.py`，PB map fallback 仍通过 `data.loader.get_opcode_pb_meta()`。
- `src.protocol.battle` 保留现有 `extract_*` 函数名；内部按 opcode 家族落到 `protocol/battle_parts/`：
  - `action_resolve.py`：0x1324/0x13F3/0x13FC 的 opcode 入口和 extract_kind 标记，保持旧导入路径。
  - `perform_dispatch.py`：BattlePerformInfo 通用 meta、entry type 分发、perform container summary 汇总。
  - `perform_entries_core.py`：技能施放、伤害、治疗、能量等核心数值 perform entry 的字段解析。
  - `perform_entries_effects.py`：effect_apply、buff_trigger、effect_link、effect_trigger 等效果类 perform entry 解析。
  - `perform_entries_pet.py`：defeat、revive、change_pet、change_model、supply_pet 等宠物生命周期 perform entry 解析。
  - `perform_entries_resource.py`：sp_energy_change、sp_energy_trigger 等特殊资源 perform entry 解析。
  - `perform_entries_skill.py`：role_skill、combo_skill、skill_pos_change、special_move 等技能相关 perform entry 解析。
  - `perform_entries_field.py`：idle、skill_state、weather、notify、ai、pvp marker、data_update 等场地/系统 perform entry 解析。
  - `sync.py`：BattlePerformInfo 中 sync-data/data_update 的顶层聚合入口。
  - `sync_common.py`：有符号 varint、fixed32 float、轻量 subitem 等同步字段底层读取器。
  - `sync_items.py`：role/pet/skill/comm/item/task 通用 sync 字段表和列表抽取。
  - `sync_skill.py`：PetSkillRoundData、技能运行时字段和技能同步细节解析。
  - `perform_generic.py`：schema 映射类和未知 perform fallback，负责 raw field dump。
  - `lifecycle.py`：生命周期 opcode 兼容门面，旧导入路径只做 re-export。
  - `lifecycle_core.py`：battle enter、round start、battle finish 的核心生命周期解析和 `BATTLE_RESULT_MAP`。
  - `lifecycle_flow.py`：round flow、round confirm 和 confirm response 的轻量解析。
  - `commands.py`：命令类 opcode 兼容门面，旧导入路径只做 re-export。
  - `command_skills.py`：技能选择、技能声明等技能命令解析。
  - `command_results.py`：0x130C 行动确认结果、wrapper 推断特殊行动解析。
  - `command_refresh.py`：0x13F4 刷新、技能选项和能量瓶信息解析。
  - `auxiliary.py`：辅助 opcode 兼容门面，旧导入路径只做 re-export。
  - `auxiliary_creatures.py`：0x0102 生物列表和玩家/宠物元信息解析。
  - `auxiliary_actions.py`：0x0220 handle、0x01A9 候选动作等辅助动作解析。
  - `auxiliary_simple.py`：简单通知/查询类辅助 opcode 的 schema/raw 解析。
- `src.analysis.battle_state.BattleStateTracker` 保留状态 dict 形状和 `handle_event()` 门面；状态子逻辑放在 `analysis/state/`：
  - `event_dispatch.py`：原始事件历史记录、当前事件上下文设置/清理，以及顶层 opcode 到 handler 的分发。
  - `action_resolve.py`：action_resolve entry 循环编排、perform group/global event 记录、entry handler 分发和 sync_data 应用。
  - `entries_damage.py`：伤害、技能施放、治疗、能量 entry handlers。
  - `entries_pet.py`：换宠 entry handler 和侧边归属判断。
  - `entries_effects.py`：buff/effect/折射相关 entry handlers。
  - `entries_field.py`：天气、模型、通知、AI、道具等 field/global entry handlers。
  - `lifecycle_events.py`：battle_enter、round_start、action_ack、battle_finish、skill_declare 等生命周期 opcode 状态更新。
  - `wrapper_sync.py`：回合开始/action_ack wrapper 到宠物运行时状态的同步、匹配和活跃指针刷新。
  - `weather.py`：天气名称解析和当前天气写回。
  - `hp_ledger.py`：HP 修改、damage ledger 和宠物 HP trace。
  - `field_events.py`：global event、perform group、sync/item sync 历史记录。
  - `skill_runtime.py`：技能运行时同步、实时能耗写回和 leader skill pool 归一化。
  - `pet_runtime.py`：pet sync、pet info sync、wrapper runtime 字段和 data_update 技能同步。
  - `side_resolver.py`：side-slot 归属、active pet 查找和稳定身份匹配。
  - `snapshot.py`：对外状态快照投影、深拷贝和 `effective_speed` 派生字段。
  - `context.py` / `pet_sync.py` / `lifecycle.py`：状态上下文、side-slot 映射和初始状态。
- `src.analysis.tactical_engine.TacticalEngine` 保留 `recommend(state)` 兼容入口；战术子逻辑放在 `analysis/tactical/`：
  - `tactical_engine.py` 顶层继续 re-export `ActionScore`、`OpponentAction`、`ResolvedOutcome` 和 `TacticalRecommendation` 等旧导入路径使用的模型；这些是兼容契约，不表示 engine 门面持有评分/组装职责。
  - `engine_actions.py` / `engine_opponent.py` / `engine_outcomes.py`：`TacticalEngine` 旧私有方法的 action、opponent、outcome 兼容 mixin，只做委托，不承载算法。
  - `engine_scoring.py` / `engine_presentation.py` / `engine_runtime.py`：`TacticalEngine` 旧私有方法的评分、展示和运行时兼容 mixin，只做委托，不反向依赖 engine 门面。
  - `engine_recommendation_flow.py`：`TacticalEngine.recommend()` 的 public 编排 flow，注入行动枚举、对手预测、评分和 metrics 依赖，便于独立测试早退和组装路径。
  - `action_space.py`：枚举我方可用技能和可换宠物，处理能量、冷却、技能池 fallback。
  - `damage.py`：战术排序使用的伤害预测口径和属性对位倍率，封装 DamagePredictionService 细节。
  - `opponent_model.py`：解析对手技能候选、估计技能/换宠概率、归一化并标注威胁伤害。
  - `runtime.py`：技能运行时字段、冷却、实时能耗和先制层级解析。
  - `outcomes.py`：我方技能/换宠与对手技能/换宠之间的单回合 outcome 推演。
  - `switch_targets.py`：战斗态宠物到分析态宠物的归一化，以及对手换宠目标推断。
  - `threats.py`：根据 ThreatAssessor 的目标顺序挑选战术加权用的最高威胁目标。
  - `recommendations.py`：旧 tactical recommendation 入口兼容门面。
  - `recommendation_confidence.py`：对手技能信息完整度到推荐 confidence 的映射。
  - `action_score_factory.py`：ActionScore 字段构造和候选行动排序。
  - `recommendation_builder.py`：TacticalRecommendation 顶层契约组装，聚合 warnings、primary plan、battle metrics 和 opponent profile。
  - `scoring.py`：纯 outcome 评分权重和公式。
  - `action_outcome_scoring.py`：单个我方行动对所有对手预测行动的 outcome 加权聚合、展示伤害预览和最高威胁 KO 加权。
  - `action_detail_builder.py`：行动评分的前端 detail dict 契约构造，集中处理 category、expected_gain、risk、confidence、metrics、unknowns。
  - `action_scoring.py`：行动评分兼容编排，旧 non-damage/hook signal/metrics/reason 函数保留为兼容委托。
  - `non_damage_scoring.py`：辅助、回复、强化、净化等非伤害技能的 effect tags 评分和 detail 构造。
  - `hook_signal_scoring.py`：分析 hook 输出的 prefer/avoid 信号对行动分数的修饰规则。
  - `action_reason.py`：行动推荐理由文案规则。
  - `action_metrics.py`：单行动和整场 cockpit metrics 构造。
  - `action_details.py`：旧 reason/metrics/battle_metrics 入口兼容门面。
  - `action_presentation.py`：单行动展示分类、收益/风险文案、unknowns 和 confidence。
  - `recommendation_presentation.py`：整条战术推荐的 primary plan、warnings、opponent profile 和对手行动原因。
  - `presentation.py`：旧展示函数兼容门面。
- `src.analysis.event_formatter` 保留 `FormattedEvent`、`format_action_entry()`、`format_battle_event()` 等旧入口；格式化子逻辑放在 `analysis/formatting/`：
  - `core.py`：`FormattedEvent` 契约、side label、宠物名称解析。
  - `lifecycle.py`：battle enter、round start、finish、skill select/declare、action ack、special refresh、round flow。
  - `entry_dispatch.py`：0x1324/0x13FC/0x13F3 action entry 的 kind 分发、未知 entry fallback 和内部 entry suppress。
  - `entries_combat.py`：skill_cast、damage、defeat 等战斗动作格式化。
  - `entries_effects.py`：effect_apply、effect_stage、buff_trigger、effect_link、effect_trigger 等效果格式化。
  - `entries_resources.py`：heal、energy、sp energy、use_item 等资源变化格式化。
  - `entries_pet.py`：change_pet、revive、supply_pet、change_model 等宠物相关格式化。
  - `entries_misc.py`：天气、AI、PVP 演出、技能状态、通知、失败、逃跑等系统/杂项格式化。
  - `merge.py`：连续多段伤害事件合并。
- `src.api.sniffer_manager.SnifferManager` 保留抓包生命周期兼容入口和依赖持有；WebSocket 连接/广播委托给通用 `api/ws_hub.py`，事件队列、广播 task 和监控 task 生命周期放在 `api/sniffer_runtime.py`，manager start/status evaluation 编排放在 `api/sniffer_manager_flow.py`，manager 状态字段、flow_count 锁和状态变更事件构建放在 `api/sniffer_manager_state.py`，record callback 注册与线程安全分发放在 `api/sniffer_record_callbacks.py`，key 加载、PacketLogger 会话、Sniffer 构造、线程启动 timeout 和启动后 settle 放在 `api/sniffer_startup.py`，启动失败/停止清理、packet session dir 读取和 flow monitor tick 规则放在 `api/sniffer_lifecycle.py`，sniffer 原始事件到状态/消息的转换下沉到 `api/sniffer_events.py`，启动后 status 快照纯评估下沉到 `api/sniffer_state.py`，消息构建与持久化细节拆到 `api/sniffer_messages.py`（status payload、record 精简）、`api/sniffer_ws_monitor.py`（monitor WebSocket 连接生命周期、初始状态和控制消息）、`api/sniffer_route_actions.py`（start/stop/status REST payload 和 HTTP 错误映射）和 `api/sniffer_key_store.py`（会话 key 文件写入），避免 manager/route 同时承担传输契约、异步 task、启动资源、事件状态机和文件格式细节。
- `src.api.routes_battle` 保留 `/ws/battle` 和 battle REST URL；WebSocket 原始 JSON 解码下沉到 `api/battle_ws_endpoint.py`，REST action 到 manager 的委托下沉到 `api/battle_route_actions.py`，state/pets/effects 响应投影下沉到 `api/battle_route_state.py`，report payload/download 下沉到 `api/battle_report_endpoints.py`，fixture replay 路径与服务调用下沉到 `api/battle_replay_endpoint.py`，route 本身只做 FastAPI 路径挂载和 manager 获取。
- `src.api.routes_config` 保留热门技能与可学技能配置 URL；CRUD payload、HTTP 404 和持久化调用下沉到 `api/config_route_actions.py`，默认名称解析、宠物技能池扫描和可学技能响应组装下沉到 `api/config_service.py`，route 只做请求体模型和路径挂载。
- `src.data.loader` 保留旧导入路径；`src.data.catalog` 也只保留历史导入路径，底层按职责拆到 `data/catalog_files.py`（数据目录、JSON 路径、安全读取）、`data/catalog_bundle.py`（基础 bundle/name-map 缓存）和 `data/catalog_lookup.py`（ID 规范化、元数据/名称查询）。
- `src.data.loader` 中的领域查询继续下沉：`data/pet_skills.py` 负责宠物技能池和 level_skill_conf_id fallback，`data/wiki_compat.py` 负责旧 wiki 风格名称查询的 BinData 兼容实现，`data/innate.py` 负责先天技能、宠物 innate trait 和对应缓存。
- `src.data.buff_modifiers` 保留 buff 相关旧导入路径；底层按职责拆到 `data/buff_tables.py`（表构建/cache）、`data/buff_effects.py`（buff id/derived child 遍历）、`data/buff_skill_modifiers.py`（技能威力/连击修正）、`data/buff_stat_modifiers.py`（属性修正递归计算）、`data/buff_resource_modifiers.py`（速度和伤害减免）和 `data/buff_presentation.py`（摘要与 buff 字典富化）。
- `src.data.species` 保留物种/性格/进化链/战斗配置/天气的旧导入路径；具体数据访问拆到 `data/pet_species.py`、`data/nature.py`、`data/evolution.py`、`data/battle_config.py`、`data/weather.py`，每个模块只管理自己的缓存和查询规则。

## WebSocket 消息契约

`/ws/battle` 继续推送以下兼容消息：

- `connected`
- `state_update`
- `battle_event` / `battle_events`
- `battle_summary`
- `skill_analysis`
- `hook_advice`
- `suggestions`
- `tactical_recommendations`

新增字段应保持可选和向后兼容；不要替换现有字段含义。前端类型说明位于 `web/src/types/battle.ts`。
