import type {
  BattleSummary,
  FormattedBattleEvent,
  HookAdvice,
  PetTrait,
  SkillAnalysis,
  TacticalRecommendation,
  BattleState,
} from '../types/battle';

export type BattleMessage =
  | { type: 'state_update'; state: Partial<BattleState> }
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
    }
  | { type: 'hook_advice'; advice: HookAdvice[] }
  | ({ type: 'tactical_recommendations' } & TacticalRecommendation)
  | { type: 'connected'; message: string };

export interface BattleMessageHandlers {
  updateState: (state: Partial<BattleState>) => void;
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
}

export function handleBattleMessage(msg: BattleMessage, handlers: BattleMessageHandlers) {
  switch (msg.type) {
    case 'state_update':
      handlers.updateState(msg.state);
      handlers.clearExpiredAdvice(msg.state?.round ?? 0);
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
      handlers.setTacticalRecommendations(msg);
      break;
    default:
      break;
  }
}
