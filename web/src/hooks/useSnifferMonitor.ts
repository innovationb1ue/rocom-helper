import { useRef, useCallback, useEffect } from 'react';
import { useSnifferStore } from '../stores/snifferStore';
import type { SnifferStatus, SlimRecord } from '../stores/snifferStore';
import api from '../utils/api';

export function useSnifferMonitor() {
  const wsRef = useRef<WebSocket | null>(null);
  const { updateStatus, addRecord, setWsConnected, reset } = useSnifferStore();

  const connectWs = useCallback(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const url = `${protocol}//${window.location.hostname}:8000/api/sniffer/ws/monitor`;
    console.log('[sniffer] connecting WebSocket:', url);
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log('[sniffer] WebSocket connected');
      setWsConnected(true);
    };

    ws.onclose = () => {
      console.log('[sniffer] WebSocket closed');
      setWsConnected(false);
    };

    ws.onerror = (e) => {
      console.error('[sniffer] WebSocket error', e);
      setWsConnected(false);
    };

    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);
        if (msg.type === 'status') {
          updateStatus(msg.status as SnifferStatus, msg.message, msg.flow_count, msg.key_hex);
        } else if (msg.type === 'record') {
          addRecord(msg.record as SlimRecord);
        }
      } catch { /* ignore */ }
    };
  }, [updateStatus, addRecord, setWsConnected]);

  const startMonitoring = useCallback(async () => {
    console.log('[sniffer] startMonitoring called');
    try {
      // 先连接 WebSocket，确保不丢失状态变更推送
      connectWs();

      const res = await api.post('/sniffer/start');
      console.log('[sniffer] API response:', res.data);
      updateStatus(
        res.data?.details?.status ?? 'listening',
        res.data?.details?.message ?? '监听中',
        res.data?.details?.flow_count ?? 0,
        res.data?.details?.key_hex ?? null,
      );
    } catch (err) {
      console.error('[sniffer] start failed:', err);
      updateStatus('idle', `启动失败: ${err instanceof Error ? err.message : '未知错误'}`, 0, null);
    }
  }, [connectWs, updateStatus]);

  const stopMonitoring = useCallback(async () => {
    try {
      await api.post('/sniffer/stop');
    } catch { /* ignore */ }
    reset();
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
  }, [reset]);

  useEffect(() => {
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  return { startMonitoring, stopMonitoring, connectWs };
}
