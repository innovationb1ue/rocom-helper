import { create } from 'zustand';

export type SnifferStatus = 'idle' | 'listening' | 'connected' | 'key_missing' | 'key_captured' | 'disconnected' | 'decrypt_fail' | 'parse_fail';

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
  decryptFailCount: number;
  parseFailCount: number;
}

interface SnifferStore extends SnifferState {
  updateStatus: (status: SnifferStatus, message: string, flowCount: number, keyHex: string | null) => void;
  addRecord: (record: SlimRecord) => void;
  setWsConnected: (c: boolean) => void;
  setDecryptFail: (count: number) => void;
  setParseFail: (count: number) => void;
  reset: () => void;
}

const initialState: SnifferState = {
  status: 'idle',
  message: '未启动',
  flowCount: 0,
  keyHex: null,
  recentRecords: [],
  wsConnected: false,
  decryptFailCount: 0,
  parseFailCount: 0,
};

export const useSnifferStore = create<SnifferStore>((set) => ({
  ...initialState,
  updateStatus: (status, message, flowCount, keyHex) =>
    set({ status, message, flowCount, keyHex }),
  addRecord: (record) =>
    set((s) => ({ recentRecords: [...s.recentRecords.slice(-99), record] })),
  setWsConnected: (c) => set({ wsConnected: c }),
  setDecryptFail: (count) =>
    set({ status: 'decrypt_fail', decryptFailCount: count }),
  setParseFail: (count) =>
    set({ status: 'parse_fail', parseFailCount: count }),
  reset: () => set(initialState),
}));
