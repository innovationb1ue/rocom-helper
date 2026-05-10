import { useRef, useCallback, useEffect } from 'react';
import { useBattleStore } from '../stores/battleStore';
import type { FormattedBattleEvent, BattleSummary, SkillAnalysis, PetTrait, HookAdvice } from '../stores/battleStore';

export function useBattle() {
  const wsRef = useRef<WebSocket | null>(null);
  const { updateState, addSuggestion, setConnected, reset, addFormattedEvent, addFormattedEvents, setBattleSummary, setSkillAnalysis, setTraits, setOppTraits, setHookAdvice, clearExpiredAdvice } = useBattleStore();

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
        } else if (msg.type === 'hook_advice') {
          setHookAdvice(msg.advice as HookAdvice[]);
        }
      } catch (err) {
        console.error("[useBattle] WebSocket message error:", err);
      }
    };
  }, [updateState, addSuggestion, setConnected, addFormattedEvent, addFormattedEvents, setBattleSummary, setSkillAnalysis, setTraits, setOppTraits, setHookAdvice, clearExpiredAdvice]);

  const sendEvent = useCallback((opcode: number, detail: Record<string, unknown>) => {
    wsRef.current?.send(JSON.stringify({ type: 'event', opcode, detail }));
  }, []);

  const resetBattle = useCallback(() => {
    wsRef.current?.send(JSON.stringify({ type: 'reset' }));
    reset();
  }, [reset]);

  const getState = useCallback(() => {
    wsRef.current?.send(JSON.stringify({ type: 'get_state' }));
  }, []);

  useEffect(() => {
    return () => { wsRef.current?.close(); };
  }, []);

  return { connect, sendEvent, resetBattle, getState };
}
