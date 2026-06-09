"""洛克王国伤害计算器 — 基于 NRC_AI 伤害公式的确定性伤害预测。

核心公式 (参考 NRC_AI):
  ability_level = (1 + atk_up + def_down) / max(0.1, 1 + atk_down + def_up)
  ATK = base_atk * ability_level
  base = (ATK / DEF) * power * 0.9
  damage = base * effectiveness * stab * weather_mult * hits * power_mult

4 阶段 hook 管线:
  pre_power → post_base → pre_final → post_calc
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.game.type_chart import TypeChart
from src.analysis.damage import calculation as damage_calculation
from src.analysis.damage import batch as damage_batch
from src.analysis.damage import calculator_config
from src.analysis.damage.calculator_compat import DamageCalculatorCompatMixin
from src.analysis.damage.calculator_phases import DamageCalculationPhasesMixin
from src.analysis.damage.hook_pipeline import DamageHook, DamageHookPipeline, HookStage
from src.analysis.damage.result import DamageResult


class DamageCalculator(DamageCalculationPhasesMixin, DamageCalculatorCompatMixin):
    def __init__(
        self,
        type_chart: Optional[TypeChart] = None,
        *,
        server_power_rules: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.chart = type_chart or TypeChart()
        self._hook_pipeline = DamageHookPipeline()
        # 兼容旧测试和调试入口：外部仍可只读检查 calc._hooks。
        self._hooks = self._hook_pipeline.hooks
        self._server_power_rules: Dict[str, Dict[str, Any]] = {}
        self.set_server_power_rules(server_power_rules or {})

    def set_server_power_rules(self, rules: Dict[str, Any]) -> None:
        """设置按技能启用的服务器威力规则。"""
        self._server_power_rules = calculator_config.normalize_server_power_rules(rules)

    def register_hook(self, stage: HookStage, hook: DamageHook) -> None:
        """注册伤害计算 hook。hook 接收并返回 context dict。"""
        self._hook_pipeline.register(stage, hook)

    def clear_hooks(self) -> None:
        """清除所有已注册的 hooks。"""
        self._hook_pipeline.clear()

    def _run_hooks(self, stage: HookStage, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """依次执行某阶段的所有 hooks，返回最终 context。"""
        return self._hook_pipeline.run(stage, ctx)

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------

    def calculate(
        self,
        attacker: Dict[str, Any],
        defender: Dict[str, Any],
        skill_meta: Dict[str, Any],
        weather: Optional[Dict[str, Any]] = None,
    ) -> Optional[DamageResult]:
        """计算单个技能的伤害预测。返回 None 如果不是攻击技能。"""
        return damage_calculation.calculate_damage(
            self,
            attacker,
            defender,
            skill_meta,
            weather=weather,
        )

    def calculate_all(
        self,
        attacker: Dict[str, Any],
        defender: Dict[str, Any],
        skills: List[Dict[str, Any]],
        weather: Optional[Dict[str, Any]] = None,
    ) -> List[DamageResult]:
        """计算所有攻击技能的伤害预测，按最大伤害降序排列。"""
        return damage_batch.calculate_all_skills(
            self,
            attacker,
            defender,
            skills,
            weather=weather,
        )
