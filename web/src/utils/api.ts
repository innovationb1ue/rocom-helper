import axios from 'axios';

import { apiBaseUrl } from '../config';

const api = axios.create({ baseURL: apiBaseUrl() });

export interface Pet {
  id: number;
  name: string;
  base_id: number;
}

export interface Skill {
  id: number;
  name: string;
  type: number;
  power: number;
  energy_cost: number;
  hit_rate: number;
}

export interface TypeInfo {
  id: number;
  name: string;
  name_en: string;
  color: string;
}

export interface TeamAnalysis {
  score: number;
  offensive_coverage: Record<string, number>;
  defensive_coverage: Record<string, string[]>;
  shared_weaknesses: Record<string, number>;
  uncovered_types: string[];
  speed_tier: { name: string; speed: number; types: string[] }[];
  role_analysis: { name: string; role: string }[];
  suggestions: { type: string; message: string }[];
}

export interface CounterResult {
  id: number;
  name: string;
  types: number[];
  _counter_score: number;
  _counter_detail: Record<string, number>;
}

export const fetchPets = (params?: { type_id?: number; name?: string; limit?: number; offset?: number }) =>
  api.get('/pets', { params }).then(r => r.data);

export const fetchPetDetail = (id: number) =>
  api.get(`/pets/${id}`).then(r => r.data);

export const fetchSkills = (params?: { type_id?: number; limit?: number }) =>
  api.get('/skills', { params }).then(r => r.data);

export const fetchTypes = () =>
  api.get('/types').then(r => r.data);

export const fetchTypeMatchups = (typeId: number) =>
  api.get(`/types/${typeId}/matchups`).then(r => r.data);

export const analyzeTeam = (petIds: number[]) =>
  api.post('/teams/analyze', { pet_ids: petIds }).then(r => r.data);

export const findCounters = (opponentIds: number[], poolIds?: number[]) =>
  api.post('/teams/counter', { opponent_ids: opponentIds, pool_ids: poolIds }).then(r => r.data);

export const fetchCoverage = (petIds: number[]) =>
  api.post('/teams/coverage', { pet_ids: petIds }).then(r => r.data);

export const fetchSuggestions = (coreIds: number[], poolIds?: number[]) =>
  api.post('/teams/suggest', { core_ids: coreIds, pool_ids: poolIds }).then(r => r.data);

export const fetchDataStatus = () =>
  api.get('/data/status').then(r => r.data);

export const refreshData = () =>
  api.post('/data/refresh').then(r => r.data);

// ── 热门技能预设 ──

export interface PopularSkillPreset {
  name: string;
  skills: number[];
  note: string;
}

export interface PopularSkillsData {
  version: number;
  presets: Record<string, PopularSkillPreset>;
}

export interface PetWithSkills {
  base_id: number;
  name: string;
  skill_count: number;
}

export interface LearnableSkill {
  skill_id: number;
  name: string;
  element: number;
  damage_type: number;
  energy_cost: number;
  power: number;
  desc: string;
  source: number;
}

export const fetchPopularSkills = () =>
  api.get<PopularSkillsData>('/config/popular-skills').then(r => r.data);

export const updatePopularSkill = (baseId: number, data: { name?: string; skills: number[]; note?: string }) =>
  api.put(`/config/popular-skills/${baseId}`, data).then(r => r.data);

export const deletePopularSkill = (baseId: number) =>
  api.delete(`/config/popular-skills/${baseId}`).then(r => r.data);

export const fetchPetsWithSkills = () =>
  api.get<{ total: number; pets: PetWithSkills[] }>('/config/pets-with-skills').then(r => r.data);

export const fetchPetLearnableSkills = (baseId: number) =>
  api.get<{ base_id: number; name: string; skills: LearnableSkill[] }>(`/config/pets-with-skills/${baseId}/skills`).then(r => r.data);

export type SnifferTestResult = {
  status: 'ok' | 'no_traffic' | 'error';
  message: string;
  details: {
    flow_count: number;
    flows: { flow_id: string; has_key: boolean; c2s_buffer_len?: number; s2c_buffer_len?: number }[];
    records_summary: {
      total: number;
      tgcp_control: number;
      business: number;
      commands_seen: string[];
      opcodes_seen: string[];
    };
    diagnostics?: {
      tcp_packets: number;
      tcp_bytes_c2s: number;
      tcp_bytes_s2c: number;
      be21_frames: number;
      be21_cmds: Record<string, number>;
      be21_no_key_drops: number;
      parse_failures: number;
    };
    key_captured: boolean;
    key_status: 'new' | 'loaded' | 'updated' | 'mismatch' | 'none';
    capture_duration_ms: number;
  } | null;
}

export const testSniffer = (refreshKey = false) =>
  api.post<SnifferTestResult>('/sniffer/test', null, { params: refreshKey ? { refresh_key: true } : {} })
    .then(r => r.data);

export interface BattleReportSummary {
  report_id: string;
  session_id: string;
  battle_index: number;
  enter_ts: string;
  finish_ts: string;
  duration_seconds: number;
  complete: boolean;
  file_count: number;
  battle_packet_count: number;
  rounds: number | null;
  result: string | null;
  session_path: string;
  archived: boolean;
  archive_path: string | null;
}

export const fetchBattleReports = () =>
  api.get<{ reports: BattleReportSummary[] }>('/battle/reports').then(r => r.data);

export const fetchBattleReport = (reportId: string) =>
  api.get<BattleReportSummary>(`/battle/reports/${encodeURIComponent(reportId)}`).then(r => r.data);

export const downloadBattleReport = (reportId: string) =>
  api.get<Blob>(`/battle/reports/${encodeURIComponent(reportId)}/download`, { responseType: 'blob' })
    .then(r => ({
      blob: r.data,
      filename: r.headers['x-report-filename'] || `raco-report_${reportId.replace(/[:\\/.]/g, '_')}.raco-report`,
    }));

export default api;
