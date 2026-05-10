import { create } from 'zustand';

export interface EquippedSkill {
  skill_id: number;
  equipped_slot: number;
  pp?: number | null;
  cost_energy?: number | null;
  skill_name?: string | null;
  skill_desc?: string | null;
  skill_energy_cost?: number[] | null;
  skill_damage_type?: number | null;
  skill_element?: number | null;
  skill_target_type?: number | null;
  skill_feature?: number | null;
  skill_cd_round?: number[] | null;
  skill_priority?: number | null;
  skill_dam_type?: number | null;
}

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
  skills?: EquippedSkill[];
  equipped_skills?: EquippedSkill[];
  base_id?: number;
  side?: number;
}

export interface SkillAnalysis {
  skill_id: number;
  skill_name: string;
  equipped_slot: number;
  skill_element: number;
  skill_damage_type: number;
  energy_cost: number;
  skill_desc?: string | null;
  power?: number | null;
  effective_power?: number | null;
  expected_damage?: number | null;
  min_damage?: number | null;
  max_damage?: number | null;
  total_min_damage?: number | null;
  total_max_damage?: number | null;
  effectiveness?: number | null;
  effectiveness_label?: string | null;
  is_stab?: boolean | null;
  can_ko?: boolean | null;
  hit_count?: number;
  confidence?: string | null;
  power_mult?: number | null;
  weather_mult?: number | null;
  damage_breakdown?: Record<string, unknown> | null;
  warnings?: string[];
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

export interface PetTrait {
  name: string;
  description: string;
}

export interface HookAdvice {
  hook_id: string;
  priority: number;
  title: string;
  messages: { type: string; message: string }[];
  data?: Record<string, unknown> | null;
  expires_round?: number | null;
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
  skillAnalysis: SkillAnalysis[];
  traits: PetTrait[];
  oppTraits: PetTrait[];
  hookAdvice: HookAdvice[];
}

interface BattleStore extends BattleState {
  updateState: (state: Partial<BattleState>) => void;
  addSuggestion: (s: { type: string; message: string }) => void;
  setConnected: (c: boolean) => void;
  reset: () => void;
  addFormattedEvent: (event: FormattedBattleEvent) => void;
  addFormattedEvents: (events: FormattedBattleEvent[]) => void;
  setBattleSummary: (summary: BattleSummary) => void;
  setSkillAnalysis: (skills: SkillAnalysis[]) => void;
  setTraits: (traits: PetTrait[]) => void;
  setOppTraits: (traits: PetTrait[]) => void;
  setHookAdvice: (advice: HookAdvice[]) => void;
  clearExpiredAdvice: (currentRound: number) => void;
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
  skillAnalysis: [],
  traits: [],
  oppTraits: [],
  hookAdvice: [],
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
  setSkillAnalysis: (skills) => set({ skillAnalysis: skills }),
  setTraits: (traits) => set({ traits }),
  setOppTraits: (traits) => set({ oppTraits: traits }),
  setHookAdvice: (advice) => set({ hookAdvice: advice }),
  clearExpiredAdvice: (currentRound) => set((st) => ({
    hookAdvice: st.hookAdvice.filter(
      (a) => a.expires_round == null || a.expires_round >= currentRound
    ),
  })),
}));
