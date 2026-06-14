import type {
  BattleSummary,
  FormattedBattleEvent,
  HookAdvice,
  AnalysisContext,
  PetTrait,
  SkillAnalysis,
  TacticalRecommendation,
  BattleState,
} from '../types/battle';
import type { BattleFramePayload, ReplayCompletePayload } from '../stores/battleStore';

export type BattleMessage =
  | { type: 'replay_begin'; stream_id: string; seq?: number }
  | ({ type: 'battle_frame' } & BattleFramePayload)
  | ({ type: 'replay_complete' } & ReplayCompletePayload)
  | { type: 'state_update'; state: Partial<BattleState>; stream_id?: string; seq?: number }
  | { type: 'state'; state: Partial<BattleState>; stream_id?: string; seq?: number }
  | { type: 'suggestions'; suggestions: { type: string; message: string }[] }
  | { type: 'battle_event'; event: FormattedBattleEvent }
  | { type: 'battle_events'; events: FormattedBattleEvent[] }
  | { type: 'battle_summary'; summary: BattleSummary }
  | {
      type: 'skill_analysis';
      skills: SkillAnalysis[];
      traits?: PetTrait[];
      opp_traits?: PetTrait[];
      opp_skill_analysis?: SkillAnalysis[];
      opp_skill_source?: string;
      round_number?: number;
      my_active_uid?: string;
      opp_active_uid?: string;
    }
  | { type: 'hook_advice'; advice: HookAdvice[] }
  | ({ type: 'tactical_recommendations' } & TacticalRecommendation)
  | { type: 'connected'; message: string };

export interface BattleMessageHandlers {
  updateState: (state: Partial<BattleState>, streamId?: string, seq?: number) => void;
  beginBattleStream: (streamId: string) => void;
  applyBattleFrame: (frame: BattleFramePayload) => void;
  completeBattleStream: (payload: ReplayCompletePayload) => void;
  addSuggestion: (s: { type: string; message: string }) => void;
  clearExpiredAdvice: (currentRound: number) => void;
  addFormattedEvent: (event: FormattedBattleEvent) => void;
  addFormattedEvents: (events: FormattedBattleEvent[]) => void;
  setBattleSummary: (summary: BattleSummary) => void;
  setSkillAnalysis: (skills: SkillAnalysis[]) => void;
  setTraits: (traits: PetTrait[]) => void;
  setOppTraits: (traits: PetTrait[]) => void;
  setOppSkillAnalysis: (skills: SkillAnalysis[], source: string) => void;
  setHookAdvice: (advice: HookAdvice[]) => void;
  setTacticalRecommendations: (rec: TacticalRecommendation | null) => void;
  canApplyAnalysisContext: (context?: AnalysisContext) => boolean;
}

export function handleBattleMessage(msg: BattleMessage, handlers: BattleMessageHandlers) {
  switch (msg.type) {
    case 'replay_begin':
      handlers.beginBattleStream(msg.stream_id);
      break;
    case 'battle_frame':
      handlers.applyBattleFrame(msg);
      break;
    case 'replay_complete':
      handlers.completeBattleStream(msg);
      break;
    case 'state_update':
      handlers.updateState(msg.state, msg.stream_id, msg.seq);
      break;
    case 'state':
      handlers.updateState(msg.state, msg.stream_id, msg.seq);
      break;
    case 'suggestions':
      msg.suggestions.forEach((s) => handlers.addSuggestion(s));
      break;
    case 'battle_event':
      handlers.addFormattedEvent(msg.event);
      break;
    case 'battle_events':
      handlers.addFormattedEvents(msg.events);
      break;
    case 'battle_summary':
      handlers.setBattleSummary(msg.summary);
      break;
    case 'skill_analysis':
      if (!handlers.canApplyAnalysisContext(messageContext(msg))) break;
      handlers.setSkillAnalysis(msg.skills);
      if (msg.traits) handlers.setTraits(msg.traits);
      if (msg.opp_traits) handlers.setOppTraits(msg.opp_traits);
      if (msg.opp_skill_analysis) {
        handlers.setOppSkillAnalysis(msg.opp_skill_analysis, msg.opp_skill_source || '');
      }
      break;
    case 'hook_advice':
      handlers.setHookAdvice(msg.advice);
      break;
    case 'tactical_recommendations':
      if (!handlers.canApplyAnalysisContext(messageContext(msg))) break;
      handlers.setTacticalRecommendations(msg);
      break;
    default:
      break;
  }
}

function messageContext(msg: { round_number?: number; my_active_uid?: string; opp_active_uid?: string }): AnalysisContext {
  return {
    round_number: msg.round_number,
    my_active_uid: msg.my_active_uid,
    opp_active_uid: msg.opp_active_uid,
  };
}
