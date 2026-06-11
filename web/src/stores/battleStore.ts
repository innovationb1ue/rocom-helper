import { create } from 'zustand';
import type { AnalysisContext, BattlePet, BattleState, FormattedBattleEvent, BattleSummary, SkillAnalysis, PetTrait, HookAdvice, TacticalRecommendation } from '../types/battle';

export type { EquippedSkill, BattlePet, SkillAnalysis, FormattedBattleEvent, BattleSummary, PetTrait, HookAdvice, ActionScore, OpponentAction, TacticalRecommendation, BattleState } from '../types/battle';

const MAX_FORMATTED_EVENTS = 500;
const MAX_SUGGESTIONS = 20;

function takeLast<T>(items: T[], max: number): T[] {
  if (items.length <= max) return items;
  return items.slice(-max);
}

interface BattleStore extends BattleState {
  updateState: (state: Partial<BattleState>) => void;
  addSuggestion: (s: { type: string; message: string }) => void;
  setConnected: (c: boolean) => void;
  reset: () => void;
  canApplyAnalysisContext: (context?: AnalysisContext) => boolean;
  addFormattedEvent: (event: FormattedBattleEvent) => void;
  addFormattedEvents: (events: FormattedBattleEvent[]) => void;
  setBattleSummary: (summary: BattleSummary) => void;
  setSkillAnalysis: (skills: SkillAnalysis[]) => void;
  setTraits: (traits: PetTrait[]) => void;
  setOppTraits: (traits: PetTrait[]) => void;
  setHookAdvice: (advice: HookAdvice[]) => void;
  setOppSkillAnalysis: (skills: SkillAnalysis[], source: string) => void;
  clearExpiredAdvice: (currentRound: number) => void;
  setTacticalRecommendations: (rec: TacticalRecommendation | null) => void;
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
  oppSkillAnalysis: [],
  oppSkillSource: '',
  tacticalRecommendations: null,
};

export const useBattleStore = create<BattleStore>((set, get) => ({
  ...initialState,
  updateState: (partial) => set((s) => ({
    ...s,
    ...partial,
    tacticalRecommendations: partial.result ? null : s.tacticalRecommendations,
  })),
  addSuggestion: (s) => set((st) => {
    if (st.suggestions.some(x => x.type === s.type && x.message === s.message)) return st;
    return { suggestions: takeLast([...st.suggestions, s], MAX_SUGGESTIONS) };
  }),
  setConnected: (c) => set({ connected: c }),
  reset: () => set(initialState),
  canApplyAnalysisContext: (context) => contextMatches(get(), context),
  addFormattedEvent: (event) =>
    set((st) => ({ formattedEvents: takeLast([...st.formattedEvents, event], MAX_FORMATTED_EVENTS) })),
  addFormattedEvents: (events) =>
    set((st) => ({ formattedEvents: takeLast([...st.formattedEvents, ...events], MAX_FORMATTED_EVENTS) })),
  setBattleSummary: (summary) => set({ battleSummary: summary }),
  setSkillAnalysis: (skills) => set({ skillAnalysis: skills }),
  setTraits: (traits) => set({ traits }),
  setOppTraits: (traits) => set({ oppTraits: traits }),
  setHookAdvice: (advice) => set({ hookAdvice: advice }),
  setOppSkillAnalysis: (skills, source) => set({ oppSkillAnalysis: skills, oppSkillSource: source }),
  clearExpiredAdvice: (currentRound) => set((st) => ({
    hookAdvice: st.hookAdvice.filter(
      (a) => a.expires_round == null || a.expires_round >= currentRound
    ),
  })),
  setTacticalRecommendations: (rec) => set({ tacticalRecommendations: rec }),
}));

function contextMatches(state: BattleState, context?: AnalysisContext): boolean {
  if (!context) return true;
  if (context.round_number != null && state.round !== context.round_number) return false;
  if (context.my_active_uid && petIdentity(state.my_active) !== context.my_active_uid) return false;
  if (context.opp_active_uid && petIdentity(state.opp_active) !== context.opp_active_uid) return false;
  return true;
}

function petIdentity(pet: BattlePet | null): string {
  if (!pet) return '';
  if (pet.battle_uid) return `battle_uid:${pet.battle_uid}`;
  if (pet.pet_id != null) return `pet_id:${pet.pet_id}`;
  if (pet.base_id != null) return `base_id:${pet.base_id}`;
  if (pet.base_conf_id != null) return `base_conf_id:${pet.base_conf_id}`;
  return pet.name ? `name:${pet.name}` : '';
}
