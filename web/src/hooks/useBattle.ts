import { useRef, useCallback, useEffect, useState } from 'react';
import { useBattleStore } from '../stores/battleStore';
import { backendWsUrl } from '../config';
import { handleBattleMessage, type BattleMessage } from '../utils/battleMessages';

export function useBattle() {
  const wsRef = useRef<WebSocket | null>(null);
  const [connectionStatus, setConnectionStatus] = useState<'idle' | 'connecting' | 'connected' | 'disconnected'>('idle');
  const { updateState, beginBattleStream, applyBattleFrame, completeBattleStream, addSuggestion, setConnected, reset, addFormattedEvent, addFormattedEvents, setBattleSummary, setSkillAnalysis, setTraits, setOppTraits, setHookAdvice, setOppSkillAnalysis, clearExpiredAdvice, setTacticalRecommendations, canApplyAnalysisContext } = useBattleStore();

  const sendIfOpen = useCallback((payload: unknown) => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      setConnected(false);
      setConnectionStatus('disconnected');
      return false;
    }
    ws.send(JSON.stringify(payload));
    return true;
  }, [setConnected]);

  const connect = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.CONNECTING) return;
    setConnectionStatus('connecting');
    const ws = new WebSocket(backendWsUrl('/ws/battle'));
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      setConnectionStatus('connected');
    };
    ws.onclose = () => {
      setConnected(false);
      setConnectionStatus('disconnected');
    };
    ws.onerror = () => {
      setConnected(false);
      setConnectionStatus('disconnected');
    };

    ws.onmessage = (ev) => {
      try {
        handleBattleMessage(JSON.parse(ev.data) as BattleMessage, {
          updateState,
          beginBattleStream,
          applyBattleFrame,
          completeBattleStream,
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
          canApplyAnalysisContext,
        });
      } catch (err) {
        console.error("[useBattle] WebSocket message error:", err);
      }
    };
  }, [updateState, beginBattleStream, applyBattleFrame, completeBattleStream, addSuggestion, setConnected, addFormattedEvent, addFormattedEvents, setBattleSummary, setSkillAnalysis, setTraits, setOppTraits, setHookAdvice, setOppSkillAnalysis, clearExpiredAdvice, setTacticalRecommendations, canApplyAnalysisContext]);

  const sendEvent = useCallback((opcode: number, detail: Record<string, unknown>) => {
    sendIfOpen({ type: 'event', opcode, detail });
  }, [sendIfOpen]);

  const resetBattle = useCallback(() => {
    sendIfOpen({ type: 'reset' });
    reset();
    setConnectionStatus(wsRef.current?.readyState === WebSocket.OPEN ? 'connected' : 'idle');
  }, [reset, sendIfOpen]);

  const getState = useCallback(() => {
    sendIfOpen({ type: 'get_state' });
  }, [sendIfOpen]);

  useEffect(() => {
    return () => { wsRef.current?.close(); };
  }, []);

  return { connect, sendEvent, resetBattle, getState, connectionStatus };
}
