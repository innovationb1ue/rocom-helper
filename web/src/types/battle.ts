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
  base_conf_id?: number;
  side?: number;
  base_speed?: number;
  effective_speed?: number;
  battle_uid?: string;
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

export interface ActionScore {
  action_type: string;
  skill_id: number | null;
  skill_name: string | null;
  switch_to_name: string | null;
  score: number;
  reason: string;
  damage_dealt: number | null;
  damage_taken: number | null;
  can_ko: boolean;
  energy_cost: number;
}

export interface OpponentAction {
  action_type: string;
  skill_id: number | null;
  skill_name: string | null;
  switch_to_name: string | null;
  probability: number;
}

export interface TacticalRecommendation {
  actions: ActionScore[];
  opp_predicted: OpponentAction[];
  round_number: number;
  confidence: string;
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
  oppSkillAnalysis: SkillAnalysis[];
  oppSkillSource: string;
  tacticalRecommendations: TacticalRecommendation | null;
}
