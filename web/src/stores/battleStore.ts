import { create } from 'zustand';

export interface BattlePet {
  pet_id: number;
  name: string;
  types: number[];
  current_hp: number;
  max_hp: number;
  hp_pct: number;
  energy: number;
  buffs: unknown[];
}

export interface BattleState {
  battle_id: number | null;
  round: number;
  my_pets: BattlePet[];
  opp_pets: BattlePet[];
  my_active: BattlePet | null;
  opp_active: BattlePet | null;
  result: string | null;
  events: unknown[];
  suggestions: { type: string; message: string }[];
  connected: boolean;
}

interface BattleStore extends BattleState {
  updateState: (state: Partial<BattleState>) => void;
  addSuggestion: (s: { type: string; message: string }) => void;
  setConnected: (c: boolean) => void;
  reset: () => void;
}

const initialState: BattleState = {
  battle_id: null,
  round: 0,
  my_pets: [],
  opp_pets: [],
  my_active: null,
  opp_active: null,
  result: null,
  events: [],
  suggestions: [],
  connected: false,
};

export const useBattleStore = create<BattleStore>((set) => ({
  ...initialState,
  updateState: (partial) => set((s) => ({ ...s, ...partial })),
  addSuggestion: (s) => set((st) => ({ suggestions: [...st.suggestions, s] })),
  setConnected: (c) => set({ connected: c }),
  reset: () => set(initialState),
}));
