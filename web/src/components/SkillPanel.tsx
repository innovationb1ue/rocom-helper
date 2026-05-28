import { Card, Tag, Tooltip, Typography } from 'antd';
import type { BattlePet, PetTrait, SkillAnalysis } from '../stores/battleStore';
import { TYPE_COLORS, TYPE_NAMES, textColorFor } from '../utils/typeColors';

const { Text } = Typography;

function isAttackSkill(s: SkillAnalysis): boolean {
  return s.skill_damage_type === 2 || s.skill_damage_type === 3;
}

function effectivenessColor(label: string | null | undefined): string {
  if (!label) return '#d9d9d9';
  if (label === '超级有效') return '#52c41a';
  if (label === '效果拔群') return '#73d13d';
  if (label === '效果不错') return '#95de64';
  if (label === '普通') return '#d9d9d9';
  if (label === '效果不佳') return '#ff7875';
  if (label === '效果甚微') return '#ff4d4f';
  if (label === '无效') return '#8c8c8c';
  return '#d9d9d9';
}

function confidenceTag(confidence: string | null | undefined) {
  if (confidence === 'high') return <Tag color="green" style={{ fontSize: 11, margin: 0 }}>高精度</Tag>;
  if (confidence === 'medium') return <Tag color="orange" style={{ fontSize: 11, margin: 0 }}>中精度</Tag>;
  if (confidence === 'low') return <Tag color="red" style={{ fontSize: 11, margin: 0 }}>低精度</Tag>;
  return null;
}

function totalDamage(s: SkillAnalysis): number {
  return s.prediction?.total ?? s.total_max_damage ?? s.expected_damage ?? 0;
}

function perHitDamage(s: SkillAnalysis): number {
  return s.prediction?.per_hit ?? s.expected_damage ?? 0;
}

function hitCount(s: SkillAnalysis): number {
  return s.prediction?.hit_count ?? s.hit_count ?? 1;
}

function confidence(s: SkillAnalysis): string | null | undefined {
  return s.prediction?.confidence ?? s.confidence;
}

function numberValue(value: unknown): number | undefined {
  return typeof value === 'number' && Number.isFinite(value) ? value : undefined;
}

function recordValue(value: unknown): Record<string, unknown> | undefined {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : undefined;
}

function powerInfo(s: SkillAnalysis): { value?: number; line: string } {
  const bd = s.damage_breakdown ?? {};
  const basePower = numberValue(bd.base_power) ?? s.power ?? 0;
  const finalPower = numberValue(bd.final_power);
  const serverRuntime = recordValue(bd.server_runtime);
  const serverPower = numberValue(serverRuntime?.power);
  const usesServerPower = serverRuntime?.power_source === 'server_damage_params' && serverPower !== undefined;
  const value = usesServerPower ? serverPower : finalPower ?? s.effective_power ?? basePower;

  if (usesServerPower && value !== basePower) {
    return { value, line: `威力: 静态 ${basePower} -> 服务器目标威力 ${value}` };
  }
  if (value !== basePower) {
    return { value, line: `威力: ${basePower} -> ${value}` };
  }
  return { value, line: `威力: ${basePower}` };
}

function formatBreakdown(s: SkillAnalysis, oppHp: number): string {
  const lines: string[] = [];
  const bd = s.damage_breakdown;
  const explain = s.explain;
  lines.push(powerInfo(s).line);

  const statSources = explain?.stat_sources;
  if (statSources) {
    lines.push(`属性来源: 攻=${statSources.attack || '-'} 防=${statSources.defense || '-'}`);
  }

  const al = bd?.ability_level as number | undefined;
  if (al !== undefined && al !== 1.0) lines.push(`能力等级: x${al.toFixed(2)}`);
  if (s.effectiveness != null && s.effectiveness !== 1.0) {
    lines.push(`属性克制: x${s.effectiveness} (${s.effectiveness_label || ''})`);
  }
  if (s.is_stab) lines.push('本系加成: x1.5');
  const wm = (bd?.weather_mult as number | undefined) ?? s.weather_mult;
  if (wm !== undefined && wm !== 1.0) lines.push(`天气: x${wm}`);
  const pm = (bd?.power_mult as number | undefined) ?? s.power_mult;
  if (pm !== undefined && pm !== 1.0) lines.push(`技能修正: x${pm}`);

  const cal = explain?.calibration;
  if (cal?.applied) lines.push(`校准: x${cal.multiplier}`);

  const hc = hitCount(s);
  if (hc > 1) lines.push(`连击: ${perHitDamage(s)} x ${hc}`);
  const total = totalDamage(s);
  if (oppHp > 0) lines.push(`预计总伤害: ${total} (${Math.round(total / oppHp * 100)}% HP)`);
  if (s.validation_hint) lines.push(`提示: ${s.validation_hint}`);
  if (s.warnings?.length) lines.push(...s.warnings.map((w) => `警告: ${w}`));
  return lines.join('\n');
}

interface SkillPanelProps {
  skills: SkillAnalysis[];
  oppActive?: BattlePet | null;
  traits?: PetTrait[];
}

export default function SkillPanel({ skills, oppActive, traits }: SkillPanelProps) {
  if (!skills.length) return null;

  const oppName = oppActive?.name || '对方精灵';
  const oppHp = oppActive?.current_hp ?? 0;

  return (
    <Card
      title={`技能 vs ${oppName}`}
      size="small"
      style={{ marginBottom: 12 }}
      styles={{ body: { padding: '8px 12px' } }}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {traits && traits.length > 0 && (
          <div style={{ marginBottom: 4, display: 'flex', flexWrap: 'wrap', gap: 4 }}>
            {traits.map((t) => (
              <Tooltip key={t.name} title={t.description}>
                <Tag color="gold" style={{ fontSize: 11, margin: 0 }}>{t.name}</Tag>
              </Tooltip>
            ))}
          </div>
        )}
        {skills.map((s) => {
          const typeColor = TYPE_COLORS[s.skill_element] || '#999';
          const typeName = TYPE_NAMES[s.skill_element] || '?';
          const attack = isAttackSkill(s);
          const hc = hitCount(s);
          const total = totalDamage(s);
          const breakdownText = attack ? formatBreakdown(s, oppHp) : '';
          const conf = confidence(s);
          const pwr = powerInfo(s);

          return (
            <div
              key={s.skill_id}
              style={{
                display: 'flex',
                alignItems: 'center',
                flexWrap: 'wrap',
                gap: 8,
                padding: '4px 8px',
                borderRadius: 6,
                background: s.can_ko ? '#f6ffed' : 'transparent',
                border: s.can_ko ? '1px solid #b7eb8f' : '1px solid transparent',
              }}
            >
              <Tag style={{ margin: 0, minWidth: 48, textAlign: 'center', background: typeColor, color: textColorFor(typeColor), border: 'none', fontWeight: 600, fontSize: 11 }}>
                {typeName}
              </Tag>
              <Text strong style={{ minWidth: 80, fontSize: 13 }}>{s.skill_name}</Text>
              <Tag color={attack ? 'red' : 'blue'} style={{ fontSize: 11, margin: 0 }}>
                {attack ? '攻击' : '辅助'}
              </Tag>
              <Text type="secondary" style={{ fontSize: 11, minWidth: 36 }}>
                {s.energy_cost > 0 ? `${s.energy_cost}EP` : '免费'}
              </Text>

              {attack && s.expected_damage != null && (
                <>
                  {pwr.value != null && (
                    <Tooltip title={pwr.line}>
                      <Tag style={{ fontSize: 11, margin: 0, background: '#f0f0f0', border: '1px solid #d9d9d9' }}>
                        威力 {pwr.value}
                      </Tag>
                    </Tooltip>
                  )}
                  <Tooltip title={breakdownText || undefined}>
                    <Text style={{ fontSize: 14, fontWeight: s.can_ko ? 700 : 600 }}>
                      {total}
                    </Text>
                  </Tooltip>
                  {hc > 1 && <Tag color="purple" style={{ fontSize: 11, margin: 0 }}>{perHitDamage(s)} x {hc}</Tag>}
                  {oppHp > 0 && (
                    <Text type="secondary" style={{ fontSize: 12, minWidth: 50 }}>
                      ({Math.round(total / oppHp * 100)}%)
                    </Text>
                  )}
                  {s.effectiveness_label && (
                    <Tag style={{ fontSize: 11, margin: 0, borderColor: effectivenessColor(s.effectiveness_label), color: effectivenessColor(s.effectiveness_label) }}>
                      {s.effectiveness_label}{s.effectiveness != null && s.effectiveness !== 1.0 && ` x${s.effectiveness}`}
                    </Tag>
                  )}
                  {s.is_stab && <Tag color="blue" style={{ fontSize: 11, margin: 0 }}>STAB</Tag>}
                  {s.can_ko && <Tag color="red" style={{ fontSize: 11, margin: 0 }}>KO!</Tag>}
                  <Tooltip title={s.validation_hint || s.warnings?.join('\n') || undefined}>
                    {confidenceTag(conf)}
                  </Tooltip>
                </>
              )}

              {!attack && s.skill_desc && (
                <Text type="secondary" style={{ fontSize: 12, flex: 1 }} ellipsis>
                  {s.skill_desc}
                </Text>
              )}
            </div>
          );
        })}
      </div>
    </Card>
  );
}
