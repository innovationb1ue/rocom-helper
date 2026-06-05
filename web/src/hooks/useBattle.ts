import { useRef, useCallback, useEffect } from 'react';
import { useBattleStore } from '../stores/battleStore';
import { backendWsUrl } from '../config';
import { handleBattleMessage, type BattleMessage } from '../utils/battleMessages';

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
    const ws = new WebSocket(backendWsUrl('/ws/battle'));
    wsRef.current = ws;

    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onerror = () => setConnected(false);

    ws.onmessage = (ev) => {
      try {
        handleBattleMessage(JSON.parse(ev.data) as BattleMessage, {
          updateState,
          addSuggestion,
          clearExpiredAdvice,
          addFormattedEvent,
          addFormattedEvents,
          setBattleSummary,
          setSkillAnalysis,
          setTraits,
          setOppTraits,
          setOppSkillAnalysis,
          setHookAdvice,
          setTacticalRecommendations,
        });
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
