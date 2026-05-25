import { useRef, useCallback, useEffect } from 'react';
import { useBattleStore } from '../stores/battleStore';
import type { FormattedBattleEvent, BattleSummary, SkillAnalysis, PetTrait, HookAdvice, TacticalRecommendation } from '../stores/battleStore';

export function useBattle() {
  const wsRef = useRef<WebSocket | null>(null);
  const { updateState, addSuggestion, setConnected, reset, addFormattedEvent, addFormattedEvents, setBattleSummary, setSkillAnalysis, setTraits, setOppTraits, setHookAdvice, setOppSkillAnalysis, clearExpiredAdvice, setTacticalRecommendations } = useBattleStore();

  const sendIfOpen = useCallback((payload: unknown) => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      setConnected(false);
      return false;
    }
    ws.send(JSON.stringify(payload));
    return true;
  }, [setConnected]);

  const connect = useCallback(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${protocol}//${window.location.hostname}:8000/ws/battle`);
    wsRef.current = ws;

    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onerror = () => setConnected(false);

    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);
        if (msg.type === 'state_update') {
          updateState(msg.state);
          clearExpiredAdvice(msg.state?.round ?? 0);
        } else if (msg.type === 'suggestions') {
          msg.suggestions.forEach((s: { type: string; message: string }) => addSuggestion(s));
        } else if (msg.type === 'battle_event') {
          addFormattedEvent(msg.event as FormattedBattleEvent);
        } else if (msg.type === 'battle_events') {
          addFormattedEvents(msg.events as FormattedBattleEvent[]);
        } else if (msg.type === 'battle_summary') {
          setBattleSummary(msg.summary as BattleSummary);
        } else if (msg.type === 'skill_analysis') {
          setSkillAnalysis(msg.skills as SkillAnalysis[]);
          if (msg.traits) {
            setTraits(msg.traits as PetTrait[]);
          }
          if (msg.opp_traits) {
            setOppTraits(msg.opp_traits as PetTrait[]);
          }
          if (msg.opp_skill_analysis) {
            setOppSkillAnalysis(msg.opp_skill_analysis as SkillAnalysis[], msg.opp_skill_source || '');
          }
        } else if (msg.type === 'hook_advice') {
          setHookAdvice(msg.advice as HookAdvice[]);
        } else if (msg.type === 'tactical_recommendations') {
          setTacticalRecommendations(msg as TacticalRecommendation);
        }
      } catch (err) {
        console.error("[useBattle] WebSocket message error:", err);
      }
    };
  }, [updateState, addSuggestion, setConnected, addFormattedEvent, addFormattedEvents, setBattleSummary, setSkillAnalysis, setTraits, setOppTraits, setHookAdvice, setOppSkillAnalysis, clearExpiredAdvice, setTacticalRecommendations]);

  const sendEvent = useCallback((opcode: number, detail: Record<string, unknown>) => {
    sendIfOpen({ type: 'event', opcode, detail });
  }, [sendIfOpen]);

  const resetBattle = useCallback(() => {
    sendIfOpen({ type: 'reset' });
    reset();
  }, [reset, sendIfOpen]);

  const getState = useCallback(() => {
    sendIfOpen({ type: 'get_state' });
  }, [sendIfOpen]);

  useEffect(() => {
    return () => { wsRef.current?.close(); };
  }, []);

  return { connect, sendEvent, resetBattle, getState };
}
