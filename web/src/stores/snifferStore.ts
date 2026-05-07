import { create } from 'zustand';

export type SnifferStatus = 'idle' | 'listening' | 'connected' | 'key_captured' | 'disconnected';

export interface SlimRecord {
  record_type?: string;
  opcode?: number;
  opcode_hex?: string;
  cmd?: number;
  cmd_hex?: string;
  tgcp_command_name?: string;
  _summary_kind?: string;
  direction?: string;
  captured_at?: string;
}

interface SnifferState {
  status: SnifferStatus;
  message: string;
  flowCount: number;
  keyHex: string | null;
  recentRecords: SlimRecord[];
  wsConnected: boolean;
}

interface SnifferStore extends SnifferState {
  updateStatus: (status: SnifferStatus, message: string, flowCount: number, keyHex: string | null) => void;
  addRecord: (record: SlimRecord) => void;
  setWsConnected: (c: boolean) => void;
  reset: () => void;
}

const initialState: SnifferState = {
  status: 'idle',
  message: '未启动',
  flowCount: 0,
  keyHex: null,
  recentRecords: [],
  wsConnected: false,
};

export const useSnifferStore = create<SnifferStore>((set) => ({
  ...initialState,
  updateStatus: (status, message, flowCount, keyHex) =>
    set({ status, message, flowCount, keyHex }),
  addRecord: (record) =>
    set((s) => ({ recentRecords: [...s.recentRecords.slice(-99), record] })),
  setWsConnected: (c) => set({ wsConnected: c }),
  reset: () => set(initialState),
}));
