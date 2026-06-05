import { Card, Tag, Tooltip, Typography } from 'antd';
import type { BattlePet, SkillAnalysis } from '../stores/battleStore';
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
  return s.prediction?.tactical_total ?? s.prediction?.total ?? s.total_max_damage ?? s.expected_damage ?? 0;
}

function directDamage(s: SkillAnalysis): number {
  return s.prediction?.total ?? s.total_max_damage ?? s.expected_damage ?? 0;
}

function secondaryDamage(s: SkillAnalysis): number {
  return s.prediction?.secondary_total ?? 0;
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

interface OpponentSkillPanelProps {
  skills: SkillAnalysis[];
  source: string;
  myActive?: BattlePet | null;
  oppName?: string;
}

export default function OpponentSkillPanel({ skills, source, myActive, oppName }: OpponentSkillPanelProps) {
  if (!skills.length) return null;

  const myName = myActive?.name || '我方精灵';
  const myHp = myActive?.current_hp ?? 0;
  const sourceLabel = source === 'protocol' ? '实时数据' : source === 'used' ? '已使用技能' : source === 'preset' ? '预设配置' : '';
  const sourceColor = source === 'protocol' ? 'green' : source === 'used' ? 'blue' : source === 'preset' ? 'orange' : 'default';

  return (
    <Card
      title={
        <span>
          对手技能 vs {myName}
          {sourceLabel && <Tag color={sourceColor} style={{ marginLeft: 8, fontSize: 11 }}>{sourceLabel}</Tag>}
        </span>
      }
      size="small"
      style={{ marginBottom: 12 }}
      styles={{ body: { padding: '8px 12px' } }}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <Text type="secondary" style={{ fontSize: 12 }}>
          {oppName || '对手'} 可能使用的技能及对我方的伤害预测
        </Text>
        {skills.map((s) => {
          const typeColor = TYPE_COLORS[s.skill_element] || '#999';
          const typeName = TYPE_NAMES[s.skill_element] || '?';
          const attack = isAttackSkill(s);
          const hc = hitCount(s);
          const total = totalDamage(s);
          const secondary = secondaryDamage(s);
          const conf = confidence(s);
          const pwr = powerInfo(s);
          const damageTip = secondary > 0
            ? `本体伤害: ${directDamage(s)}\n额外效果: +${secondary}\n预计总伤害: ${total}`
            : undefined;

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
                background: s.can_ko ? '#fff2f0' : 'transparent',
                border: s.can_ko ? '1px solid #ffccc7' : '1px solid transparent',
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
                  <Tooltip title={damageTip}>
                    <Text style={{ fontSize: 14, fontWeight: s.can_ko ? 700 : 600, color: s.can_ko ? '#ff4d4f' : undefined }}>
                      {total}
                    </Text>
                  </Tooltip>
                  {secondary > 0 && <Tag color="magenta" style={{ fontSize: 11, margin: 0 }}>额外 +{secondary}</Tag>}
                  {hc > 1 && <Tag color="purple" style={{ fontSize: 11, margin: 0 }}>{perHitDamage(s)} x {hc}</Tag>}
                  {myHp > 0 && (
                    <Text type="secondary" style={{ fontSize: 12, minWidth: 50 }}>
                      ({Math.round(total / myHp * 100)}%)
                    </Text>
                  )}
                  {s.effectiveness_label && (
                    <Tag style={{ fontSize: 11, margin: 0, borderColor: effectivenessColor(s.effectiveness_label), color: effectivenessColor(s.effectiveness_label) }}>
                      {s.effectiveness_label}{s.effectiveness != null && s.effectiveness !== 1.0 && ` x${s.effectiveness}`}
                    </Tag>
                  )}
                  {s.is_stab && <Tag color="blue" style={{ fontSize: 11, margin: 0 }}>STAB</Tag>}
                  {s.can_ko && <Tag color="red" style={{ fontSize: 11, margin: 0 }}>危险!</Tag>}
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
