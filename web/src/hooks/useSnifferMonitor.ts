import { useRef, useCallback, useEffect } from 'react';
import { useSnifferStore } from '../stores/snifferStore';
import type { SnifferStatus, SlimRecord } from '../stores/snifferStore';
import { backendWsUrl } from '../config';
import api, { fetchSnifferStatus, SNIFFER_START_TIMEOUT_MS } from '../utils/api';

const ACTIVE_STATUSES = new Set<SnifferStatus>(['listening', 'connected', 'key_missing', 'key_captured']);

export function useSnifferMonitor() {
  const wsRef = useRef<WebSocket | null>(null);
  const { updateStatus, addRecord, setWsConnected, setDecryptFail, setParseFail, reset } = useSnifferStore();

  const connectWs = useCallback(() => {
    const existingWs = wsRef.current;
    if (
      existingWs?.readyState === WebSocket.CONNECTING ||
      existingWs?.readyState === WebSocket.OPEN
    ) {
      return;
    }

    const url = backendWsUrl('/api/sniffer/ws/monitor');
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
        } else if (msg.type === 'decrypt_fail') {
          setDecryptFail(msg.count);
        } else if (msg.type === 'parse_fail') {
          setParseFail(msg.count);
        }
      } catch { /* ignore */ }
    };
  }, [updateStatus, addRecord, setWsConnected, setDecryptFail, setParseFail]);

  const applyStatusDetails = useCallback((details?: {
    status?: string;
    message?: string;
    flow_count?: number;
    key_hex?: string | null;
  }) => {
    const status = (details?.status ?? 'idle') as SnifferStatus;
    updateStatus(
      status,
      details?.message ?? '未启动',
      details?.flow_count ?? 0,
      details?.key_hex ?? null,
    );
    if (ACTIVE_STATUSES.has(status)) {
      connectWs();
    }
  }, [connectWs, updateStatus]);

  const refreshStatus = useCallback(async () => {
    try {
      const res = await fetchSnifferStatus();
      applyStatusDetails(res.details);
    } catch (err) {
      console.warn('[sniffer] status refresh failed:', err);
    }
  }, [applyStatusDetails]);

  const startMonitoring = useCallback(async () => {
    console.log('[sniffer] startMonitoring called');
    try {
      // 先连接 WebSocket，确保不丢失状态变更推送
      connectWs();
      updateStatus('listening', '正在启动监听...', 0, null);

      const res = await api.post('/sniffer/start', null, { timeout: SNIFFER_START_TIMEOUT_MS });
      console.log('[sniffer] API response:', res.data);
      applyStatusDetails(res.data?.details);
    } catch (err) {
      console.error('[sniffer] start failed:', err);
      updateStatus('idle', `启动失败: ${err instanceof Error ? err.message : '未知错误'}`, 0, null);
    }
  }, [applyStatusDetails, connectWs, updateStatus]);

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
    void refreshStatus();
  }, [refreshStatus]);

  useEffect(() => {
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  return { startMonitoring, stopMonitoring, connectWs };
}
