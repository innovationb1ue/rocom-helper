"""战术推荐引擎 — 基于期望值加权的行动排序系统。

对每个可选操作（4 技能 + 换宠）计算期望得分，考虑：
  - 对手行动的概率预测
  - 速度先后手与击杀否定
  - 伤害 / 存活 / 属性对位 / 能量效率
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from src.analysis.damage_calc import DamageCalculator
from src.analysis.damage_prediction import DamagePredictionService
from src.analysis.innate_hooks import register_innate_hooks
from src.analysis.constants import SDT_TO_TYPE
from src.analysis.skill_classifier import classify_skill_effect
from src.analysis.models import ActionScore, OpponentAction, ResolvedOutcome, TacticalRecommendation
from src.analysis.tactical import presentation
from src.analysis.counter import CounterPicker
from src.analysis.pet_identity import same_battle_pet
from src.analysis.skill_resolver import resolve_opponent_skills, skills_from_pool
from src.analysis.threat import ThreatAssessor
from src.data.loader import get_skill_meta
from src.game.type_chart import TypeChart

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Evaluation weights
# ---------------------------------------------------------------------------

W_DAMAGE_DEALT = 0.25
W_KO = 0.30
W_DAMAGE_TAKEN = 0.15
W_OPP_KO = 0.20
W_TYPE_MATCHUP = 0.05
W_ENERGY = 0.03
W_COUNT_ADV = 0.02


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


# ---------------------------------------------------------------------------
# TacticalEngine
# ---------------------------------------------------------------------------

class TacticalEngine:
    """战术推荐引擎 — 为每个可选操作计算期望得分并排序。"""

    def __init__(self, type_chart: Optional[TypeChart] = None) -> None:
        self.chart = type_chart or TypeChart()
        self._damage_calc = DamageCalculator(self.chart)
        register_innate_hooks(self._damage_calc)
        self._prediction_service = DamagePredictionService(self.chart, damage_calc=self._damage_calc)
        self._threat = ThreatAssessor(self.chart)
        self._counter = CounterPicker(self.chart)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def recommend(self, state: Dict[str, Any]) -> Optional[TacticalRecommendation]:
        """根据当前战斗状态生成推荐行动排序。"""
        my_active = state.get("my_active")
        opp_active = state.get("opp_active")
        my_pets = state.get("my_pets", [])
        opp_pets = state.get("opp_pets", [])
        if not my_active or not opp_active:
            return None

        our_actions = self._enumerate_our_actions(my_active, my_pets)
        if not our_actions:
            return None

        opp_skill_source = self._opp_skill_source(opp_active)
        opp_predicted = self._predict_opp_actions(opp_active, opp_pets, state)
        if not opp_predicted:
            return None

        top_threat_name = None
        if opp_pets:
            norm_my_active = self._normalize_pet_for_analysis(my_active)
            target_order = self._threat.suggest_target_order(opp_pets, norm_my_active)
            if target_order:
                top_threat_name = target_order[0]["name"]

        scored: List[ActionScore] = []
        for our_action in our_actions:
            score, reason, detail = self._score_action(
                our_action, my_active, opp_active, my_pets, opp_pets,
                opp_predicted, state, top_threat_name,
            )
            scored.append(ActionScore(
                action_type=our_action["action_type"],
                skill_id=our_action.get("skill_id"),
                skill_name=our_action.get("skill_name"),
                switch_to_name=our_action.get("switch_to_name"),
                score=round(score, 4),
                reason=reason,
                category=detail.get("category", "balanced"),
                expected_gain=detail.get("expected_gain", ""),
                risk=detail.get("risk", ""),
                confidence=detail.get("confidence", "medium"),
                damage_dealt=detail.get("damage_dealt"),
                damage_taken=detail.get("damage_taken"),
                can_ko=detail.get("can_ko", False),
                energy_cost=our_action.get("energy_cost", 0),
                metrics=detail.get("metrics", {}),
                unknowns=detail.get("unknowns", []),
            ))

        scored.sort(key=lambda a: a.score, reverse=True)

        confidence = self._assess_confidence(opp_active)
        warnings = self._build_warnings(scored, opp_predicted, confidence, opp_skill_source)

        return TacticalRecommendation(
            actions=scored,
            opp_predicted=opp_predicted,
            round_number=state.get("round", 0),
            confidence=confidence,
            primary_plan=self._primary_plan(scored),
            warnings=warnings,
            metrics=self._battle_metrics(my_active, opp_active, my_pets, opp_pets),
            opponent_profile=self._opponent_profile(opp_active, opp_predicted, opp_skill_source),
        )

    # ------------------------------------------------------------------
    # Action enumeration
    # ------------------------------------------------------------------

    def _enumerate_our_actions(
        self, my_active: Dict[str, Any], my_pets: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """枚举所有可选操作：可用技能 + 可换宠物。"""
        actions: List[Dict[str, Any]] = []
        our_energy = my_active.get("energy", 10)

        # 技能
        equipped = (
            my_active.get("equipped_skills")
            or my_active.get("skills")
            or my_active.get("used_skills")
            or []
        )
        if not equipped:
            equipped = self._skills_from_pool(my_active)

        for eq in equipped:
            skill_id = eq.get("skill_id")
            if skill_id is None:
                continue
            meta = get_skill_meta(skill_id)
            if meta is None:
                continue

            runtime = self._skill_runtime(my_active, skill_id)
            cd_round = self._skill_cd_round(eq, runtime)
            if cd_round > 0:
                continue

            energy_cost = self._resolve_action_energy_cost(eq, runtime, meta)
            if energy_cost > our_energy:
                continue

            skill_name = eq.get("skill_name") or meta.get("name", "?")
            damage_type = eq.get("skill_damage_type") or meta.get("damage_type", 0)
            element = eq.get("skill_element") or 0
            if element == 0 and meta:
                dt = meta.get("skill_dam_type")
                if dt is not None:
                    element = SDT_TO_TYPE.get(dt, 0)

            actions.append({
                "action_type": "skill",
                "skill_id": skill_id,
                "skill_name": skill_name,
                "energy_cost": energy_cost,
                "damage_type": damage_type,
                "skill_element": element,
                "meta": meta,
                "is_damage_skill": damage_type in (2, 3) and (meta.get("dam_para", [0]) or [0])[0] > 0,
                "priority_layer": self._skill_priority_layer(eq, runtime, meta),
                "cd_round": cd_round,
            })

        # 换宠
        for pet in my_pets:
            if pet.get("current_hp", 1) <= 0:
                continue
            if same_battle_pet(pet, my_active):
                continue
            actions.append({
                "action_type": "switch",
                "switch_to_name": pet.get("name", "?"),
                "switch_to_pet": pet,
                "energy_cost": 0,
            })

        return actions

    @staticmethod
    def _skills_from_pool(pet: Dict[str, Any]) -> List[Dict[str, Any]]:
        return skills_from_pool(pet)

    # ------------------------------------------------------------------
    # Opponent prediction
    # ------------------------------------------------------------------

    def _predict_opp_actions(
        self, opp_active: Dict[str, Any], opp_pets: List[Dict[str, Any]],
        state: Dict[str, Any],
    ) -> List[OpponentAction]:
        """预测对手可能的行动及概率。"""
        actions: List[OpponentAction] = []
        opp_energy = opp_active.get("energy", 10)

        # 解析对手技能
        opp_skills, opp_source = resolve_opponent_skills(opp_active)

        # 技能概率
        skill_probs = self._compute_skill_probabilities(opp_skills, opp_energy, opp_active)
        for skill_id, prob, skill_name in skill_probs:
            meta = get_skill_meta(skill_id) or {}
            runtime = self._skill_runtime(opp_active, skill_id)
            skill = next((s for s in opp_skills if s.get("skill_id") == skill_id), {})
            actions.append(OpponentAction(
                action_type="skill",
                skill_id=skill_id,
                skill_name=skill_name,
                probability=prob,
                source=opp_source,
                reason=self._opp_action_reason(skill_id, prob, opp_active),
                priority_layer=self._skill_priority_layer(skill, runtime, meta),
            ))

        # 换宠概率
        switch_prob = self._estimate_switch_probability(opp_active, state)
        if switch_prob > 0:
            living_bench = [
                p for p in opp_pets
                if p.get("current_hp", 1) > 0 and not same_battle_pet(p, opp_active)
            ]
            if living_bench:
                per_pet = switch_prob / len(living_bench)
                for pet in living_bench:
                    actions.append(OpponentAction(
                        action_type="switch",
                        switch_to_name=pet.get("name", "?"),
                        probability=per_pet,
                        source="state",
                        reason="低血量或对位不利时的换宠候选",
                    ))

        # 归一化
        total = sum(a.probability for a in actions)
        if total <= 0:
            if actions:
                n = len(actions)
                for a in actions:
                    a.probability = 1.0 / n
            else:
                return []
        else:
            for a in actions:
                a.probability /= total

        self._annotate_opp_threat(actions, opp_active, state)

        return actions

    @staticmethod
    def _resolve_opp_skills(opp_active: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Resolve opponent skill candidates without owning the fallback policy."""
        skills, _source = resolve_opponent_skills(opp_active)
        return skills

    def _compute_skill_probabilities(
        self, opp_skills: List[Dict[str, Any]], opp_energy: int,
        opp_active: Dict[str, Any],
    ) -> List[Tuple[int, float, str]]:
        """根据使用频率和技能威力分配概率。"""
        if not opp_skills:
            return []

        used_skills: Dict[int, int] = {}
        for us in (opp_active.get("used_skills") or []):
            sid = us.get("skill_id")
            if sid is not None:
                used_skills[sid] = used_skills.get(sid, 0) + 1

        entries: List[Tuple[int, float, str]] = []
        total_weight = 0.0

        for skill in opp_skills:
            skill_id = skill.get("skill_id")
            if skill_id is None:
                continue
            meta = get_skill_meta(skill_id)
            if meta is None:
                continue

            runtime = self._skill_runtime(opp_active, skill_id)
            cd_round = self._skill_cd_round(skill, runtime)
            if cd_round > 0:
                continue

            energy_cost = self._resolve_action_energy_cost(skill, runtime, meta)
            if energy_cost > opp_energy:
                continue

            name = skill.get("skill_name") or meta.get("name", "?")

            # 权重：已使用过的技能按频率，未使用过的按威力
            freq = used_skills.get(skill_id, 0)
            if freq > 0:
                weight = float(freq)
            else:
                power = (meta.get("dam_para", [0]) or [0])[0]
                weight = max(1.0, power / 20.0)

            entries.append((skill_id, weight, name))
            total_weight += weight

        if total_weight <= 0 or not entries:
            return []

        return [(sid, w / total_weight, name) for sid, w, name in entries]

    def _estimate_switch_probability(
        self, opp_active: Dict[str, Any], state: Dict[str, Any],
    ) -> float:
        """估算对手换宠概率。"""
        prob = 0.10  # 基础概率

        hp_pct = opp_active.get("hp_pct", 1.0)
        if hp_pct < 0.25:
            prob = 0.25

        # 我方属性克制对手 → 对手更可能换
        my_active = state.get("my_active")
        if my_active:
            my_types = my_active.get("types", [])
            opp_types = opp_active.get("types", [])
            if my_types and opp_types:
                best_mult = 0.0
                for at in my_types:
                    m = self.chart.get_multiplier(at, opp_types)
                    if m > best_mult:
                        best_mult = m
                if best_mult >= 2.0:
                    prob = max(prob, 0.35)

        return min(prob, 0.40)

    # ------------------------------------------------------------------
    # Outcome resolution
    # ------------------------------------------------------------------

    def _resolve_outcome(
        self, our_action: Dict[str, Any], opp_action: OpponentAction,
        my_active: Dict[str, Any], opp_active: Dict[str, Any],
        my_pets: List[Dict[str, Any]], opp_pets: List[Dict[str, Any]],
        state: Dict[str, Any],
    ) -> ResolvedOutcome:
        weather = state.get("weather")

        # --- 我们换宠 ---
        if our_action["action_type"] == "switch":
            return self._resolve_switch_outcome(
                our_action, opp_action, my_active, opp_active, state, weather,
            )

        # --- 对手换宠 ---
        if opp_action.action_type == "switch":
            return self._resolve_opp_switch_outcome(
                our_action, opp_action, my_active, opp_active, opp_pets, state, weather,
            )

        # --- 双方都用技能 ---
        return self._resolve_skill_vs_skill(
            our_action, opp_action, my_active, opp_active, state, weather,
        )

    def _resolve_skill_vs_skill(
        self, our_action: Dict[str, Any], opp_action: OpponentAction,
        my_active: Dict[str, Any], opp_active: Dict[str, Any],
        state: Dict[str, Any], weather: Optional[Dict[str, Any]],
    ) -> ResolvedOutcome:
        our_speed = my_active.get("effective_speed") or my_active.get("base_speed", 0)
        opp_speed = opp_active.get("effective_speed") or opp_active.get("base_speed", 0)
        our_priority = int(our_action.get("priority_layer") or 0)
        opp_priority = int(opp_action.priority_layer or 0)
        if our_priority != opp_priority:
            we_act_first = our_priority > opp_priority
        else:
            we_act_first = our_speed >= opp_speed

        our_meta = our_action.get("meta")
        our_damage = self._calc_damage(my_active, opp_active, our_meta, weather)

        opp_meta = get_skill_meta(opp_action.skill_id) if opp_action.skill_id else None
        opp_damage = self._calc_damage(opp_active, my_active, opp_meta, weather)

        our_hp = my_active.get("current_hp", 0)
        opp_hp = opp_active.get("current_hp", 0)

        we_ko = False
        opp_kos_us = False

        if we_act_first:
            opp_hp -= our_damage
            we_ko = opp_hp <= 0
            if not we_ko:
                our_hp -= opp_damage
                opp_kos_us = our_hp <= 0
        else:
            our_hp -= opp_damage
            opp_kos_us = our_hp <= 0
            if not opp_kos_us:
                opp_hp -= our_damage
                we_ko = opp_hp <= 0

        energy_after = my_active.get("energy", 10) - our_action.get("energy_cost", 0)

        return ResolvedOutcome(
            our_damage_dealt=our_damage,
            opp_damage_dealt=opp_damage if not we_ko else 0,
            we_ko=we_ko,
            opp_kos_us=opp_kos_us,
            we_act_first=we_act_first,
            our_remaining_hp=max(0, our_hp),
            opp_remaining_hp=max(0, opp_hp),
            type_matchup_after=self._type_matchup_score(my_active, opp_active),
            energy_after=max(0, energy_after),
            pet_count_delta=(1 if we_ko else 0) - (1 if opp_kos_us else 0),
        )

    def _resolve_switch_outcome(
        self, our_action: Dict[str, Any], opp_action: OpponentAction,
        my_active: Dict[str, Any], opp_active: Dict[str, Any],
        state: Dict[str, Any], weather: Optional[Dict[str, Any]],
    ) -> ResolvedOutcome:
        """我方换宠：先手换出，对手技能打在新宠物上。"""
        incoming = our_action.get("switch_to_pet", {})

        opp_meta = get_skill_meta(opp_action.skill_id) if opp_action.skill_id else None
        opp_damage = self._calc_damage(opp_active, incoming, opp_meta, weather)

        our_remaining = incoming.get("current_hp", 0) - opp_damage

        return ResolvedOutcome(
            our_damage_dealt=0,
            opp_damage_dealt=opp_damage,
            we_ko=False,
            opp_kos_us=our_remaining <= 0,
            we_act_first=True,
            our_remaining_hp=max(0, our_remaining),
            opp_remaining_hp=opp_active.get("current_hp", 0),
            type_matchup_after=self._type_matchup_score(incoming, opp_active),
            energy_after=incoming.get("energy", 10),
            pet_count_delta=-1 if our_remaining <= 0 else 0,
            incoming_energy=incoming.get("energy", 10),
            incoming_has_buffs=bool(incoming.get("buffs")),
        )

    def _resolve_opp_switch_outcome(
        self, our_action: Dict[str, Any], opp_action: OpponentAction,
        my_active: Dict[str, Any], opp_active: Dict[str, Any],
        opp_pets: List[Dict[str, Any]], state: Dict[str, Any],
        weather: Optional[Dict[str, Any]],
    ) -> ResolvedOutcome:
        """对手换宠：用对手最可能换上的宠物（按属性优势选）。"""
        target = self._most_likely_switch_target(opp_action, opp_pets, my_active)
        if target is None:
            target = opp_active

        our_meta = our_action.get("meta")
        our_damage = self._calc_damage(my_active, target, our_meta, weather)

        target_hp = target.get("current_hp", 0) - our_damage
        we_ko = target_hp <= 0

        energy_after = my_active.get("energy", 10) - our_action.get("energy_cost", 0)

        return ResolvedOutcome(
            our_damage_dealt=our_damage,
            opp_damage_dealt=0,
            we_ko=we_ko,
            opp_kos_us=False,
            we_act_first=True,
            our_remaining_hp=my_active.get("current_hp", 0),
            opp_remaining_hp=max(0, target_hp),
            type_matchup_after=self._type_matchup_score(my_active, target),
            energy_after=max(0, energy_after),
            pet_count_delta=1 if we_ko else 0,
        )

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def _score_action(
        self, our_action: Dict[str, Any], my_active: Dict[str, Any],
        opp_active: Dict[str, Any], my_pets: List[Dict[str, Any]],
        opp_pets: List[Dict[str, Any]], opp_predicted: List[OpponentAction],
        state: Dict[str, Any], top_threat_name: Optional[str] = None,
    ) -> Tuple[float, str, Dict[str, Any]]:
        """对单个操作计算期望得分。"""
        # 非伤害技能走简化路径
        if our_action["action_type"] == "skill" and not our_action.get("is_damage_skill", False):
            return self._score_non_damage_skill(our_action, my_active, opp_active)

        total_score = 0.0
        best_damage_dealt = 0
        worst_damage_taken = 0
        can_ko = False
        display_damage_dealt: Optional[int] = None
        display_can_ko = False

        if our_action["action_type"] == "skill" and our_action.get("is_damage_skill", False):
            display_damage_dealt = self._calc_damage(
                my_active, opp_active, our_action.get("meta"), state.get("weather")
            )
            if display_damage_dealt > 0:
                display_can_ko = display_damage_dealt >= opp_active.get("current_hp", 0)

        for opp_act in opp_predicted:
            outcome = self._resolve_outcome(
                our_action, opp_act, my_active, opp_active,
                my_pets, opp_pets, state,
            )
            outcome_score = self._evaluate_outcome(outcome, my_active, opp_active)
            total_score += opp_act.probability * outcome_score

            if outcome.our_damage_dealt > best_damage_dealt:
                best_damage_dealt = outcome.our_damage_dealt
            if outcome.opp_damage_dealt > worst_damage_taken:
                worst_damage_taken = outcome.opp_damage_dealt
            if outcome.we_ko:
                can_ko = True

        # 威胁加成：能击杀最高威胁对手时提升评分
        if top_threat_name and opp_active.get("name") == top_threat_name and can_ko:
            total_score *= 1.15

        # Hook 信号修饰
        hook_signals = state.get("_hook_signals", [])
        for signal in hook_signals:
            if signal.get("signal_type") == "prefer_switch" and our_action["action_type"] == "switch":
                total_score *= 1.2
            elif signal.get("signal_type") == "avoid_skill" and our_action["action_type"] == "skill":
                energy_cost = our_action.get("energy_cost", 0)
                if energy_cost >= 3:
                    total_score *= 0.5
                elif energy_cost >= 1:
                    total_score *= 0.8

        reason = self._generate_reason(
            our_action,
            display_damage_dealt or best_damage_dealt,
            worst_damage_taken,
            display_can_ko or can_ko,
        )
        metrics = self._action_metrics(
            our_action=our_action,
            my_active=my_active,
            opp_active=opp_active,
            damage_dealt=display_damage_dealt or best_damage_dealt,
            damage_taken=worst_damage_taken,
            can_ko=display_can_ko or can_ko,
        )
        unknowns = self._action_unknowns(our_action, opp_active, state)
        detail = {
            "damage_dealt": display_damage_dealt if display_damage_dealt and display_damage_dealt > 0 else None,
            "damage_taken": worst_damage_taken if worst_damage_taken > 0 else None,
            "can_ko": display_can_ko or can_ko,
            "category": self._action_category(our_action, total_score, display_can_ko or can_ko, worst_damage_taken, my_active),
            "expected_gain": self._expected_gain(our_action, display_damage_dealt or best_damage_dealt, display_can_ko or can_ko, metrics),
            "risk": self._risk_summary(our_action, worst_damage_taken, my_active, unknowns),
            "confidence": self._action_confidence(unknowns, opp_active),
            "metrics": metrics,
            "unknowns": unknowns,
        }
        return total_score, reason, detail

    def _evaluate_outcome(
        self, outcome: ResolvedOutcome,
        my_active: Dict[str, Any], opp_active: Dict[str, Any],
    ) -> float:
        """将推演结果转为分数。"""
        our_max_hp = max(1, my_active.get("max_hp", 1))
        opp_max_hp = max(1, opp_active.get("max_hp", 1))

        score = (
            W_DAMAGE_DEALT * _clamp01(outcome.our_damage_dealt / opp_max_hp)
            + W_KO * (1.0 if outcome.we_ko else 0.0)
            - W_DAMAGE_TAKEN * _clamp01(outcome.opp_damage_dealt / our_max_hp)
            - W_OPP_KO * (1.0 if outcome.opp_kos_us else 0.0)
            + W_TYPE_MATCHUP * _clamp01(outcome.type_matchup_after / 4.0)
            + W_ENERGY * _clamp01(outcome.energy_after / 10.0)
            + W_COUNT_ADV * outcome.pet_count_delta * 0.15
        )

        # 换宠动量奖励：入场宠物有能量和 buff 时更有利
        if outcome.incoming_energy > 0:
            score += 0.02 * _clamp01(outcome.incoming_energy / 10.0)
        if outcome.incoming_has_buffs:
            score += 0.03

        return score

    def _score_non_damage_skill(
        self, our_action: Dict[str, Any],
        my_active: Dict[str, Any], opp_active: Dict[str, Any],
    ) -> Tuple[float, str, Dict[str, Any]]:
        """非伤害技能的结构化评分。"""
        base = 0.15
        meta = our_action.get("meta", {})
        tags = classify_skill_effect(meta)

        hp_pct = my_active.get("hp_pct", 1.0)
        our_speed = my_active.get("effective_speed") or my_active.get("base_speed", 0)
        opp_speed = opp_active.get("effective_speed") or opp_active.get("base_speed", 0)
        we_outspeed = our_speed >= opp_speed

        if "stat_up" in tags:
            if "spd_up" in tags or "speed" in tags:
                base += 0.08
            elif we_outspeed:
                base += 0.06
            else:
                base += 0.04

        if "stat_down" in tags:
            base += 0.05

        if "heal" in tags:
            if hp_pct < 0.3:
                base += 0.12
            elif hp_pct < 0.5:
                base += 0.08
            else:
                base += 0.03

        if "shield" in tags:
            if hp_pct < 0.5:
                base += 0.07
            else:
                base += 0.04

        if "damage_reduce" in tags:
            base += 0.05

        if "cleanse" in tags:
            buffs = my_active.get("buffs", [])
            negative_buffs = [b for b in buffs if b.get("stage", 0) < 0]
            if negative_buffs:
                base += 0.06

        if "hazard" in tags:
            base += 0.04

        energy_cost = our_action.get("energy_cost", 0)
        base -= 0.015 * energy_cost
        base = max(0.05, base)

        reason = our_action.get("skill_name", "辅助技能")
        if tags:
            reason += f" ({','.join(tags[:3])})"
        unknowns = self._action_unknowns(our_action, opp_active, {})
        detail = {
            "damage_dealt": None,
            "damage_taken": None,
            "can_ko": False,
            "category": "conservative" if "heal" in tags or "shield" in tags else "setup",
            "expected_gain": "强化/回复类收益，适合拉长回合",
            "risk": "直接输出较低，若对手爆发可能亏节奏",
            "confidence": self._action_confidence(unknowns, opp_active),
            "metrics": {
                "energy_after": max(0, my_active.get("energy", 10) - our_action.get("energy_cost", 0)),
                "effect_tags": tags,
            },
            "unknowns": unknowns,
        }
        return base, reason, detail

    # ------------------------------------------------------------------
    # Reason generation
    # ------------------------------------------------------------------

    @staticmethod
    def _generate_reason(
        our_action: Dict[str, Any], damage_dealt: int, damage_taken: int, can_ko: bool,
    ) -> str:
        """生成中文推荐理由。"""
        if our_action["action_type"] == "switch":
            name = our_action.get("switch_to_name", "?")
            reasons = []
            if can_ko is False and damage_taken > 0:
                reasons.append(f"吃 {damage_taken} 伤害")
            reasons.append("改善对位")
            return f"换上 {name}，{'，'.join(reasons)}"

        skill_name = our_action.get("skill_name", "?")
        reasons = []

        if can_ko:
            reasons.append("先手击杀")
        if damage_dealt > 0:
            opp_max_hp_approx = 300  # 未知时用粗估值
            if damage_dealt > opp_max_hp_approx * 0.5:
                reasons.append("高伤害")
            else:
                reasons.append(f"{damage_dealt} 伤害")

        energy_cost = our_action.get("energy_cost", 0)
        if energy_cost >= 5:
            reasons.append(f"耗能 {energy_cost}")

        if damage_taken > 0:
            reasons.append(f"承受 {damage_taken}")

        return f"{skill_name}：{'，'.join(reasons)}" if reasons else skill_name

    # ------------------------------------------------------------------
    # Decision cockpit helpers
    # ------------------------------------------------------------------

    def _action_metrics(
        self,
        *,
        our_action: Dict[str, Any],
        my_active: Dict[str, Any],
        opp_active: Dict[str, Any],
        damage_dealt: int,
        damage_taken: int,
        can_ko: bool,
    ) -> Dict[str, Any]:
        my_speed = my_active.get("effective_speed") or my_active.get("base_speed", 0)
        opp_speed = opp_active.get("effective_speed") or opp_active.get("base_speed", 0)
        priority_layer = int(our_action.get("priority_layer") or 0)
        if priority_layer > 0:
            speed_order = f"先手技能 +{priority_layer}"
        elif priority_layer < 0:
            speed_order = f"后发技能 {priority_layer}"
        else:
            speed_order = "速度更快" if my_speed >= opp_speed else "速度较慢"
        energy_after = max(0, my_active.get("energy", 10) - our_action.get("energy_cost", 0))
        my_hp = my_active.get("current_hp", 0)
        opp_hp = opp_active.get("current_hp", 0)
        return {
            "speed_order": speed_order,
            "my_speed": my_speed,
            "opp_speed": opp_speed,
            "priority_layer": priority_layer,
            "energy_after": energy_after,
            "kill_line": max(0, opp_hp - max(0, damage_dealt)),
            "survival_line": max(0, my_hp - max(0, damage_taken)),
            "damage_pct": round(damage_dealt / max(1, opp_active.get("max_hp", 1)), 3) if damage_dealt else 0,
            "incoming_pct": round(damage_taken / max(1, my_active.get("max_hp", 1)), 3) if damage_taken else 0,
            "can_ko": can_ko,
            "switch_penalty": our_action["action_type"] == "switch" and damage_taken > 0,
            "type_matchup": self._type_matchup_score(
                our_action.get("switch_to_pet", my_active), opp_active
            ),
        }

    @staticmethod
    def _action_category(
        our_action: Dict[str, Any],
        score: float,
        can_ko: bool,
        damage_taken: int,
        my_active: Dict[str, Any],
    ) -> str:
        return presentation.action_category(our_action, score, can_ko, damage_taken, my_active)

    @staticmethod
    def _expected_gain(
        our_action: Dict[str, Any],
        damage_dealt: int,
        can_ko: bool,
        metrics: Dict[str, Any],
    ) -> str:
        return presentation.expected_gain(our_action, damage_dealt, can_ko, metrics)

    @staticmethod
    def _risk_summary(
        our_action: Dict[str, Any],
        damage_taken: int,
        my_active: Dict[str, Any],
        unknowns: List[str],
    ) -> str:
        return presentation.risk_summary(our_action, damage_taken, my_active, unknowns)

    @staticmethod
    def _action_unknowns(
        our_action: Dict[str, Any],
        opp_active: Dict[str, Any],
        state: Dict[str, Any],
    ) -> List[str]:
        return presentation.action_unknowns(our_action, opp_active, state)

    @staticmethod
    def _action_confidence(unknowns: List[str], opp_active: Dict[str, Any]) -> str:
        return presentation.action_confidence(unknowns, opp_active, TacticalEngine._assess_confidence)

    @staticmethod
    def _primary_plan(actions: List[ActionScore]) -> str:
        return presentation.primary_plan(actions)

    @staticmethod
    def _build_warnings(
        actions: List[ActionScore],
        opp_predicted: List[OpponentAction],
        confidence: str,
        opp_skill_source: str,
    ) -> List[str]:
        return presentation.build_warnings(actions, opp_predicted, confidence, opp_skill_source)

    def _battle_metrics(
        self,
        my_active: Dict[str, Any],
        opp_active: Dict[str, Any],
        my_pets: List[Dict[str, Any]],
        opp_pets: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        living_my = [p for p in my_pets if p.get("current_hp", 1) > 0]
        living_opp = [p for p in opp_pets if p.get("current_hp", 1) > 0]
        my_speed = my_active.get("effective_speed") or my_active.get("base_speed", 0)
        opp_speed = opp_active.get("effective_speed") or opp_active.get("base_speed", 0)
        return {
            "speed_line": {
                "my": my_speed,
                "opp": opp_speed,
                "order": "我方先手" if my_speed >= opp_speed else "对手先手",
            },
            "energy_window": {
                "my": my_active.get("energy", 0),
                "opp": opp_active.get("energy", 0),
            },
            "pet_count": {
                "my_alive": len(living_my),
                "opp_alive": len(living_opp),
                "delta": len(living_my) - len(living_opp),
            },
            "type_matchup": self._type_matchup_score(my_active, opp_active),
        }

    @staticmethod
    def _opponent_profile(
        opp_active: Dict[str, Any],
        opp_predicted: List[OpponentAction],
        opp_skill_source: str,
    ) -> Dict[str, Any]:
        return presentation.opponent_profile(opp_active, opp_predicted, opp_skill_source)

    @staticmethod
    def _opp_skill_source(opp_active: Dict[str, Any]) -> str:
        _skills, source = resolve_opponent_skills(opp_active)
        return source

    @staticmethod
    def _opp_action_reason(skill_id: int, probability: float, opp_active: Dict[str, Any]) -> str:
        return presentation.opp_action_reason(skill_id, probability, opp_active)

    def _annotate_opp_threat(
        self,
        actions: List[OpponentAction],
        opp_active: Dict[str, Any],
        state: Dict[str, Any],
    ) -> None:
        my_active = state.get("my_active")
        if not my_active:
            return
        weather = state.get("weather")
        my_hp = my_active.get("current_hp", 0)
        for action in actions:
            if action.action_type != "skill" or action.skill_id is None:
                continue
            meta = get_skill_meta(action.skill_id)
            damage = self._calc_damage(opp_active, my_active, meta, weather)
            action.threat_damage = damage if damage > 0 else None
            action.can_ko = damage >= my_hp if damage > 0 else False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _calc_damage(
        self, attacker: Dict[str, Any], defender: Dict[str, Any],
        skill_meta: Optional[Dict[str, Any]], weather: Optional[Dict[str, Any]],
    ) -> int:
        """用 DamageCalculator 计算伤害，返回与技能分析面板一致的期望伤害口径。"""
        if skill_meta is None:
            return 0
        damage_type = skill_meta.get("damage_type", 0)
        if damage_type not in (2, 3):
            return 0
        pred = self._prediction_service.predict(attacker, defender, skill_meta, weather=weather)
        if pred is None:
            return 0
        return pred["prediction"]["total"]

    @staticmethod
    def _skill_runtime(pet: Dict[str, Any], skill_id: Any) -> Dict[str, Any]:
        if skill_id is None:
            return {}
        runtime = pet.get("skill_runtime") or {}
        item = runtime.get(str(skill_id)) or runtime.get(skill_id) or {}
        return item if isinstance(item, dict) else {}

    @staticmethod
    def _skill_cd_round(skill: Dict[str, Any], runtime: Dict[str, Any]) -> int:
        for source in (runtime, skill):
            value = source.get("cd_round")
            if isinstance(value, list):
                value = next((item for item in value if item is not None), None)
            if value is not None:
                try:
                    return max(0, int(value))
                except (TypeError, ValueError):
                    return 0
        return 0

    @staticmethod
    def _resolve_action_energy_cost(
        skill: Dict[str, Any],
        runtime: Dict[str, Any],
        meta: Dict[str, Any],
    ) -> int:
        for source, key in (
            (runtime, "cost_energy_result"),
            (skill, "runtime_cost_energy"),
            (runtime, "cost_energy"),
            (runtime, "raw_cost_energy"),
            (skill, "cost_energy"),
        ):
            value = source.get(key)
            if value is not None:
                return int(value)
        costs = meta.get("energy_cost", [0]) if meta else [0]
        return int(costs[0]) if costs else 0

    @staticmethod
    def _skill_priority_layer(
        skill: Dict[str, Any],
        runtime: Dict[str, Any],
        meta: Dict[str, Any],
    ) -> int:
        skill_buff = runtime.get("skill_buff") if isinstance(runtime.get("skill_buff"), dict) else {}
        runtime_priority = skill_buff.get("priority")
        if runtime_priority not in (None, 0):
            try:
                return int(runtime_priority)
            except (TypeError, ValueError):
                pass

        for value in (skill.get("skill_priority"), meta.get("skill_priority") if meta else None):
            if value is not None:
                try:
                    return int(value) - 5
                except (TypeError, ValueError):
                    break

        desc = str((meta or {}).get("desc") or skill.get("skill_desc") or skill.get("desc") or "")
        match = re.search(r"先手\s*([+-])\s*(\d+)", desc)
        if match:
            layer = int(match.group(2))
            return layer if match.group(1) == "+" else -layer
        if "先手" in desc or "优先" in desc:
            return 1
        if skill.get("priority_display"):
            return 1
        return 0

    def _type_matchup_score(
        self, our_pet: Dict[str, Any], opp_pet: Dict[str, Any],
    ) -> float:
        """计算我方对敌方的最佳属性克制倍率。"""
        our_types = our_pet.get("types", [])
        opp_types = opp_pet.get("types", [])
        if not our_types or not opp_types:
            return 1.0
        best = 0.0
        for at in our_types:
            m = self.chart.get_multiplier(at, opp_types)
            if m > best:
                best = m
        return best

    @staticmethod
    def _normalize_pet_for_analysis(pet: Dict[str, Any]) -> Dict[str, Any]:
        """将战斗状态宠物转换为 ThreatAssessor / CounterPicker 期望的格式。"""
        normalized = dict(pet)

        stats = pet.get("stats", [])
        if isinstance(stats, list):
            stats_dict: Dict[str, Any] = {}
            for s in stats:
                name = s.get("name")
                val = s.get("total") or s.get("calc") or 0
                if name:
                    stats_dict[name] = val
            normalized["stats"] = stats_dict
        elif isinstance(stats, dict):
            normalized["stats"] = stats

        if "base_speed" in pet and "SPE" not in normalized.get("stats", {}):
            normalized.setdefault("stats", {})["SPE"] = pet["base_speed"]

        skills = pet.get("equipped_skills") or pet.get("skills") or []
        normalized_skills: List[Dict[str, Any]] = []
        for s in skills:
            ns = dict(s)
            if "skill_element" in s and "type_id" not in s:
                ns["type_id"] = s["skill_element"]
            if "skill_name" in s and "name" not in s:
                ns["name"] = s["skill_name"]
            normalized_skills.append(ns)
        normalized["skills"] = normalized_skills

        return normalized

    def _most_likely_switch_target(
        self,
        opp_action: OpponentAction, opp_pets: List[Dict[str, Any]],
        my_active: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """猜测对手最可能换上的宠物（按名称匹配或按反制优势）。"""
        target_name = opp_action.switch_to_name
        for pet in opp_pets:
            if pet.get("name") == target_name and pet.get("current_hp", 1) > 0:
                return pet

        living_bench = [
            p for p in opp_pets
            if p.get("current_hp", 1) > 0
        ]
        if not living_bench:
            return None

        # 对手换宠时通常换上克制我方的宠物
        norm_my_active = self._normalize_pet_for_analysis(my_active)
        norm_bench = [self._normalize_pet_for_analysis(p) for p in living_bench]
        counters = self._counter.find_counters([norm_my_active], norm_bench, top_n=1)
        if counters:
            counter = counters[0]
            for p in living_bench:
                if same_battle_pet(p, counter):
                    return p

        return living_bench[0]

    @staticmethod
    def _assess_confidence(opp_active: Dict[str, Any]) -> str:
        """评估推荐的置信度。"""
        equipped = opp_active.get("equipped_skills") or opp_active.get("skills") or []
        if equipped:
            return "high"
        used = opp_active.get("used_skills") or []
        if len(used) >= 3:
            return "high"
        if used:
            return "medium"
        return "low"
