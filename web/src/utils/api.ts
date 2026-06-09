import axios from 'axios';

import { apiBaseUrl } from '../config';

const api = axios.create({ baseURL: apiBaseUrl(), timeout: 12000 });

export const SNIFFER_START_TIMEOUT_MS = 30000;

// 热门技能预设
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

export interface BattleReportDiagnostics {
  report_count: number;
  packet_session_count: number;
  packet_file_count: number;
  latest_session_id: string | null;
  latest_session_path: string | null;
  latest_session_file_count: number;
  battle_enter_count: number;
  battle_finish_count: number;
  completed_battle_count: number;
  incomplete_battle_count: number;
  has_battle_enter: boolean;
  has_battle_finish: boolean;
}

export interface BattleReportsResponse {
  reports: BattleReportSummary[];
  diagnostics: BattleReportDiagnostics;
}

export const fetchBattleReports = () =>
  api.get<BattleReportsResponse>('/battle/reports').then(r => r.data);

export const fetchBattleReport = (reportId: string) =>
  api.get<BattleReportSummary>(`/battle/reports/${encodeURIComponent(reportId)}`).then(r => r.data);

export const downloadBattleReport = (reportId: string) =>
  api.get<Blob>(`/battle/reports/${encodeURIComponent(reportId)}/download`, { responseType: 'blob' })
    .then(r => ({
      blob: r.data,
      filename: r.headers['x-report-filename'] || `raco-report_${reportId.replace(/[:\\/.]/g, '_')}.raco-report`,
    }));

export default api;
