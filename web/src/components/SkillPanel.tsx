import { Card, Tag, Typography, Tooltip } from 'antd';
import type { SkillAnalysis, BattlePet, PetTrait } from '../stores/battleStore';
import { TYPE_COLORS, TYPE_NAMES, textColorFor } from '../utils/typeColors';

const { Text } = Typography;

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

function isAttackSkill(s: SkillAnalysis): boolean {
  return s.skill_damage_type === 2 || s.skill_damage_type === 3;
}

function formatBreakdown(s: SkillAnalysis, oppHp: number): string {
  const bd = s.damage_breakdown;
  if (!bd) return '';
  const lines: string[] = [];
  const basePwr = (bd.base_power as number) ?? s.power ?? 0;
  const effPwr = (bd.effective_power as number) ?? s.effective_power ?? basePwr;
  if (effPwr !== basePwr) {
    lines.push(`威力: ${basePwr} → ${effPwr}`);
  } else {
    lines.push(`威力: ${basePwr}`);
  }
  const al = bd.ability_level as number | undefined;
  if (al !== undefined && al !== 1.0) {
    lines.push(`能力等级: ×${al.toFixed(2)}`);
  }
  if (s.effectiveness != null && s.effectiveness !== 1.0) {
    lines.push(`属性克制: ×${s.effectiveness} (${s.effectiveness_label || ''})`);
  }
  if (s.is_stab) {
    lines.push('本系加成: ×1.5');
  }
  const wm = bd.weather_mult as number | undefined;
  if (wm !== undefined && wm !== 1.0) {
    lines.push(`天气: ×${wm}`);
  }
  const pm = bd.power_mult as number | undefined;
  if (pm !== undefined && pm !== 1.0) {
    lines.push(`威力修正: ×${pm}`);
  }
  const hc = (bd.hit_count as number) ?? s.hit_count ?? 1;
  if (hc > 1) {
    lines.push(`连击: ×${hc}`);
  }
  const totalDmg = s.total_max_damage ?? s.expected_damage ?? 0;
  if (oppHp > 0) {
    lines.push(`─────────`);
    lines.push(`预期伤害: ${totalDmg} (${Math.round(totalDmg / oppHp * 100)}% HP)`);
  }
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
                <Tag color="gold" style={{ fontSize: 11, margin: 0 }}>
                  {t.name}
                </Tag>
              </Tooltip>
            ))}
          </div>
        )}
        {skills.map((s) => {
          const typeColor = TYPE_COLORS[s.skill_element] || '#999';
          const typeName = TYPE_NAMES[s.skill_element] || '?';
          const attack = isAttackSkill(s);
          const isCombo = (s.hit_count ?? 1) > 1;
          const hitCount = s.hit_count ?? 1;
          const totalDmg = s.total_max_damage ?? s.expected_damage ?? 0;
          const breakdownText = attack ? formatBreakdown(s, oppHp) : '';

          return (
            <div
              key={s.skill_id}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                padding: '4px 8px',
                borderRadius: 6,
                background: s.can_ko ? '#f6ffed' : 'transparent',
                border: s.can_ko ? '1px solid #b7eb8f' : '1px solid transparent',
              }}
            >
              {/* 属性标签 */}
              <Tag style={{
                margin: 0,
                minWidth: 48,
                textAlign: 'center',
                background: typeColor,
                color: textColorFor(typeColor),
                border: 'none',
                fontWeight: 600,
                fontSize: 11,
              }}>
                {typeName}
              </Tag>

              {/* 技能名 */}
              <Text strong style={{ minWidth: 80, fontSize: 13 }}>{s.skill_name}</Text>

              {/* 攻/辅 标签 */}
              <Tag color={attack ? 'red' : 'blue'} style={{ fontSize: 11, margin: 0 }}>
                {attack ? '攻' : '辅'}
              </Tag>

              {/* 能耗 */}
              <Text type="secondary" style={{ fontSize: 11, minWidth: 36 }}>
                {s.energy_cost > 0 ? `${s.energy_cost}EP` : '免费'}
              </Text>

              {/* 攻击技能：威力 + 预期伤害 */}
              {attack && s.expected_damage != null && (
                <>
                  {/* 预期威力 */}
                  {s.effective_power != null && (
                    <Tag style={{ fontSize: 11, margin: 0, background: '#f0f0f0', border: '1px solid #d9d9d9' }}>
                      威力 {s.effective_power}
                    </Tag>
                  )}

                  {/* 预期伤害 */}
                  <Tooltip title={breakdownText || undefined}>
                    <Text style={{ fontSize: 14, fontWeight: s.can_ko ? 700 : 600 }}>
                      {isCombo ? totalDmg : s.expected_damage}
                    </Text>
                  </Tooltip>

                  {isCombo && (
                    <Tag color="purple" style={{ fontSize: 11, margin: 0 }}>×{hitCount}</Tag>
                  )}

                  {/* HP 百分比 */}
                  {oppHp > 0 && (
                    <Text type="secondary" style={{ fontSize: 12, minWidth: 50 }}>
                      ({Math.round(totalDmg / oppHp * 100)}%)
                    </Text>
                  )}

                  {/* 克制标签 */}
                  {s.effectiveness_label && (
                    <Tag style={{ fontSize: 11, margin: 0, borderColor: effectivenessColor(s.effectiveness_label), color: effectivenessColor(s.effectiveness_label) }}>
                      {s.effectiveness_label}
                      {s.effectiveness != null && s.effectiveness !== 1.0 && ` ×${s.effectiveness}`}
                    </Tag>
                  )}

                  {s.is_stab && <Tag color="blue" style={{ fontSize: 11, margin: 0 }}>STAB</Tag>}
                  {s.can_ko && <Tag color="red" style={{ fontSize: 11, margin: 0 }}>KO!</Tag>}

                  <Tooltip title={s.warnings?.length ? s.warnings.join('\n') : undefined}>
                    {confidenceTag(s.confidence)}
                  </Tooltip>
                </>
              )}

              {/* 状态技能：描述 */}
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
