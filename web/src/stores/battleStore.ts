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
  level?: number;
  slot?: number;
  skills?: unknown[];
  equipped_skills?: unknown[];
}

export interface FormattedBattleEvent {
  kind: string;
  round: number;
  summary: string;
  detail: Record<string, unknown>;
  icon: string;
  color: string;
}

export interface BattleSummary {
  result: string | null;
  rounds: number;
  my_pets_final: { name: string; hp: number; max_hp: number; status: string }[];
  opp_pets_final: { name: string; hp: number; max_hp: number; status: string }[];
  event_stats: Record<string, number>;
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
  formattedEvents: FormattedBattleEvent[];
  battleSummary: BattleSummary | null;
}

interface BattleStore extends BattleState {
  updateState: (state: Partial<BattleState>) => void;
  addSuggestion: (s: { type: string; message: string }) => void;
  setConnected: (c: boolean) => void;
  reset: () => void;
  addFormattedEvent: (event: FormattedBattleEvent) => void;
  addFormattedEvents: (events: FormattedBattleEvent[]) => void;
  setBattleSummary: (summary: BattleSummary) => void;
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
  formattedEvents: [],
  battleSummary: null,
};

export const useBattleStore = create<BattleStore>((set) => ({
  ...initialState,
  updateState: (partial) => set((s) => ({ ...s, ...partial })),
  addSuggestion: (s) => set((st) => {
    if (st.suggestions.some(x => x.type === s.type && x.message === s.message)) return st;
    return { suggestions: [...st.suggestions, s] };
  }),
  setConnected: (c) => set({ connected: c }),
  reset: () => set(initialState),
  addFormattedEvent: (event) =>
    set((st) => ({ formattedEvents: [...st.formattedEvents, event] })),
  addFormattedEvents: (events) =>
    set((st) => ({ formattedEvents: [...st.formattedEvents, ...events] })),
  setBattleSummary: (summary) => set({ battleSummary: summary }),
}));
