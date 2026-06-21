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
  currentStreamId: string | null;
  lastSeq: number;
  updateState: (state: Partial<BattleState>, streamId?: string, seq?: number) => void;
  beginBattleStream: (streamId: string) => void;
  applyBattleFrame: (frame: BattleFramePayload) => void;
  completeBattleStream: (payload: ReplayCompletePayload) => void;
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

export interface BattleFramePayload {
  stream_id: string;
  seq: number;
  state: Partial<BattleState>;
  round_number?: number;
  my_active_uid?: string;
  opp_active_uid?: string;
  events?: FormattedBattleEvent[];
  suggestions?: { type: string; message: string }[];
  skills?: SkillAnalysis[];
  traits?: PetTrait[];
  opp_traits?: PetTrait[];
  opp_skill_analysis?: SkillAnalysis[];
  opp_skill_source?: string;
  hook_advice?: HookAdvice[];
  tactical_recommendations?: TacticalRecommendation | null;
  battle_summary?: BattleSummary | null;
  has_battle_advice?: boolean;
  has_hook_advice?: boolean;
  has_tactical_recommendations?: boolean;
}

export interface ReplayCompletePayload {
  stream_id: string;
  seq: number;
  state: Partial<BattleState>;
  result?: string | null;
  suggestions?: { type: string; message: string }[];
}

const initialState: BattleState = {
  battle_id: null,
  battle_mode: null,
  round: 0,
  max_round: 0,
  phase: 'idle',
  my_pets: [],
  opp_pets: [],
  my_active: null,
  opp_active: null,
  result: null,
  terminal_pending: false,
  role_resources: {},
  battle_resource: {},
  role_resource_events: [],
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
  currentStreamId: null,
  lastSeq: 0,
  updateState: (partial, streamId, seq) => set((s) => {
    if (!canApplyStateUpdate(s, streamId, seq)) return s;
    const nextSeq = streamId && seq != null ? seq : s.lastSeq;
    const inactive = isInactive(partial);
    return {
      ...s,
      ...partial,
      currentStreamId: streamId || s.currentStreamId,
      lastSeq: nextSeq,
      suggestions: inactive ? [] : s.suggestions,
      skillAnalysis: inactive ? [] : s.skillAnalysis,
      oppSkillAnalysis: inactive ? [] : s.oppSkillAnalysis,
      oppSkillSource: inactive ? '' : s.oppSkillSource,
      hookAdvice: inactive ? [] : s.hookAdvice,
      tacticalRecommendations: inactive ? null : s.tacticalRecommendations,
    };
  }),
  beginBattleStream: (streamId) => set((st) => ({
    ...initialState,
    connected: st.connected,
    currentStreamId: streamId,
    lastSeq: 0,
  })),
  applyBattleFrame: (frame) => set((st) => {
    if (!canApplyFrame(st, frame.stream_id, frame.seq)) return st;
    const partial = frame.state || {};
    const inactive = isInactive(partial);
    const activeChanged = activeIdentityChanged(st, partial);
    const hasBattleAdvice = frame.has_battle_advice === true;
    const hasHookAdvice = frame.has_hook_advice === true;
    const hasTactical = frame.has_tactical_recommendations === true;
    return {
      ...st,
      ...partial,
      currentStreamId: frame.stream_id,
      lastSeq: frame.seq,
      formattedEvents: takeLast([
        ...st.formattedEvents,
        ...(frame.events || []),
      ], MAX_FORMATTED_EVENTS),
      suggestions: inactive ? [] : takeLast(frame.suggestions || [], MAX_SUGGESTIONS),
      skillAnalysis: inactive || activeChanged ? [] : (hasBattleAdvice ? (frame.skills || []) : st.skillAnalysis),
      traits: inactive || activeChanged ? [] : (hasBattleAdvice ? (frame.traits || []) : st.traits),
      oppTraits: inactive || activeChanged ? [] : (hasBattleAdvice ? (frame.opp_traits || []) : st.oppTraits),
      oppSkillAnalysis: inactive || activeChanged ? [] : (hasBattleAdvice ? (frame.opp_skill_analysis || []) : st.oppSkillAnalysis),
      oppSkillSource: inactive || activeChanged ? '' : (hasBattleAdvice ? (frame.opp_skill_source || '') : st.oppSkillSource),
      hookAdvice: inactive || activeChanged ? [] : (hasHookAdvice ? (frame.hook_advice || []) : st.hookAdvice),
      tacticalRecommendations: inactive || activeChanged ? null : (hasTactical ? (frame.tactical_recommendations || null) : st.tacticalRecommendations),
      battleSummary: frame.battle_summary || st.battleSummary,
    };
  }),
  completeBattleStream: (payload) => set((st) => {
    if (!canApplyFrame(st, payload.stream_id, payload.seq)) return st;
    const partial = payload.state || {};
    const inactive = isInactive(partial) || payload.result != null;
    return {
      ...st,
      ...partial,
      currentStreamId: payload.stream_id,
      lastSeq: payload.seq,
      result: partial.result ?? payload.result ?? st.result,
      suggestions: inactive ? [] : takeLast(payload.suggestions || [], MAX_SUGGESTIONS),
      skillAnalysis: inactive ? [] : st.skillAnalysis,
      oppSkillAnalysis: inactive ? [] : st.oppSkillAnalysis,
      oppSkillSource: inactive ? '' : st.oppSkillSource,
      hookAdvice: inactive ? [] : st.hookAdvice,
      tacticalRecommendations: inactive ? null : st.tacticalRecommendations,
    };
  }),
  addSuggestion: (s) => set((st) => {
    if (st.suggestions.some(x => x.type === s.type && x.message === s.message)) return st;
    return { suggestions: takeLast([...st.suggestions, s], MAX_SUGGESTIONS) };
  }),
  setConnected: (c) => set({ connected: c }),
  reset: () => set((st) => ({ ...initialState, connected: st.connected, currentStreamId: null, lastSeq: 0 })),
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

function canApplyFrame(state: BattleStore, streamId: string, seq: number): boolean {
  if (!streamId) return false;
  if (state.currentStreamId && state.currentStreamId !== streamId) return false;
  return seq > state.lastSeq;
}

function canApplyStateUpdate(state: BattleStore, streamId?: string, seq?: number): boolean {
  if (!streamId || seq == null) {
    return !state.currentStreamId;
  }
  return canApplyFrame(state, streamId, seq);
}

function isInactive(state: Partial<BattleState>): boolean {
  return Boolean(
    state.result != null ||
    state.terminal_pending ||
    state.phase === 'finished' ||
    state.phase === 'settling'
  );
}

function activeIdentityChanged(state: BattleState, partial: Partial<BattleState>): boolean {
  if (partial.my_active !== undefined && petIdentity(partial.my_active) !== petIdentity(state.my_active)) {
    return true;
  }
  if (partial.opp_active !== undefined && petIdentity(partial.opp_active) !== petIdentity(state.opp_active)) {
    return true;
  }
  return false;
}

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
