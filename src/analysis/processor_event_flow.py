"""BattleProcessor 的单事件处理 flow。

这里集中编排一次 opcode detail 进入后要做的事情：状态更新、格式化、
伤害分析、战术推荐、hook 和最终 ProcessResult 组装。
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, List, Optional, Protocol

from src.analysis import processor_analysis, processor_outputs
from src.analysis.formatting.core import FormattedEvent
from src.analysis.models import ProcessResult
from src.analysis.processor_policy import (
    battle_is_active,
    should_compute_damage_analysis,
    should_compute_tactical,
    should_snapshot_state_before,
)


class TrackerLike(Protocol):
    def get_state(self) -> Dict[str, Any]: ...

    def handle_event(self, opcode: int, detail: Dict[str, Any]) -> Dict[str, Any]: ...


AdvisorProvider = Callable[[], processor_analysis.AdvisorLike]
TacticalEngineProvider = Callable[[], processor_analysis.TacticalEngineLike]
HookRunner = Callable[[int, Dict[str, Any], Dict[str, Any]], List[Dict[str, Any]]]
FormattedEventsBuilder = Callable[..., List[FormattedEvent]]
SuggestionsBuilder = Callable[[Dict[str, Any]], List[Dict[str, str]]]


def process_battle_event(
    *,
    tracker: TrackerLike,
    opcode: int,
    detail: Dict[str, Any],
    damage_opcodes: Iterable[int],
    include_analysis: bool,
    include_hooks: bool,
    include_formatting: bool,
    advisor_provider: AdvisorProvider,
    tactical_engine_provider: TacticalEngineProvider,
    hook_runner: HookRunner,
    formatted_events_builder: FormattedEventsBuilder = processor_outputs.build_formatted_events,
    suggestions_builder: SuggestionsBuilder = processor_outputs.build_suggestions,
) -> ProcessResult:
    """处理单个战斗事件，返回状态、格式化事件和分析输出。"""
    needs_state_before = should_snapshot_state_before(
        include_analysis=include_analysis,
        opcode=opcode,
    )
    state_before = tracker.get_state() if needs_state_before else None
    state = tracker.handle_event(opcode, detail)
    round_num = state.get("round", 0)
    active = battle_is_active(state)

    formatted = formatted_events_builder(
        include_formatting=include_formatting,
        opcode=opcode,
        detail=detail,
        state=state,
        round_num=round_num,
    )

    battle_advice_dict: Optional[Dict[str, Any]] = None
    if should_compute_damage_analysis(
        include_analysis=include_analysis,
        active=active,
        opcode=opcode,
        damage_opcodes=damage_opcodes,
    ):
        battle_advice_dict = processor_analysis.compute_damage_analysis_for_event(
            opcode=opcode,
            detail=detail,
            state=state,
            state_before=state_before,
            advisor=advisor_provider(),
        )

    tactical_dict: Optional[Dict[str, Any]] = None
    if should_compute_tactical(
        include_analysis=include_analysis,
        active=active,
        opcode=opcode,
    ):
        tactical_dict = processor_analysis.compute_tactical_with_reliability(
            state,
            engine=tactical_engine_provider(),
            battle_advice=battle_advice_dict,
        )

    hook_advice_dicts: List[Dict[str, Any]] = []
    if include_hooks and active:
        hook_advice_dicts = hook_runner(opcode, detail, state)

    return processor_outputs.build_process_result(
        state=state,
        formatted_events=formatted,
        battle_advice=battle_advice_dict,
        hook_advice=hook_advice_dicts,
        suggestions=suggestions_builder(state),
        tactical=tactical_dict,
    )
