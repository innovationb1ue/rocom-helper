import { Card, Tag, Typography, Tooltip } from 'antd';
import type { DamagePrediction, BattlePet } from '../stores/battleStore';
import { TYPE_COLORS } from '../utils/typeColors';

const { Text } = Typography;

function effectivenessColor(label: string): string {
  if (label === '超级有效') return '#52c41a';
  if (label === '效果拔群') return '#73d13d';
  if (label === '效果不错') return '#95de64';
  if (label === '普通') return '#d9d9d9';
  if (label === '效果不佳') return '#ff7875';
  if (label === '效果甚微') return '#ff4d4f';
  if (label === '无效') return '#8c8c8c';
  return '#d9d9d9';
}

function confidenceTag(confidence: string) {
  if (confidence === 'high') return <Tag color="green" style={{ fontSize: 11 }}>高精度</Tag>;
  if (confidence === 'medium') return <Tag color="orange" style={{ fontSize: 11 }}>中精度</Tag>;
  return <Tag color="red" style={{ fontSize: 11 }}>低精度</Tag>;
}

interface Props {
  predictions: DamagePrediction[];
  oppActive: BattlePet | null;
}

export default function DamagePredictionPanel({ predictions, oppActive }: Props) {
  if (!predictions.length) return null;

  const oppName = oppActive?.name || '对方精灵';
  const oppHp = oppActive?.current_hp ?? 0;

  return (
    <Card
      title={`伤害预测 vs ${oppName}`}
      size="small"
      style={{ marginBottom: 12 }}
      styles={{ body: { padding: '8px 12px' } }}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {predictions.map((p) => {
          const typeColor = TYPE_COLORS[p.skill_element] || '#999';
          const effColor = effectivenessColor(p.effectiveness_label);
          const isCombo = (p.hit_count ?? 1) > 1;
          const hitCount = p.hit_count ?? 1;
          const totalMin = p.total_min_damage || p.min_damage * hitCount;
          const totalMax = p.total_max_damage || p.max_damage * hitCount;

          // HP 百分比基于总伤害
          const hpPct = oppHp > 0
            ? `${Math.round(totalMin / oppHp * 100)}%~${Math.round(totalMax / oppHp * 100)}%`
            : '-';

          return (
            <div
              key={p.skill_id}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                padding: '4px 8px',
                borderRadius: 6,
                background: p.can_ko ? '#f6ffed' : 'transparent',
                border: p.can_ko ? '1px solid #b7eb8f' : '1px solid transparent',
              }}
            >
              {/* 技能名 + 属性标签 */}
              <Tag color={typeColor} style={{ margin: 0, minWidth: 60, textAlign: 'center' }}>
                {p.skill_element_name}
              </Tag>
              <Text strong style={{ minWidth: 90, fontSize: 13 }}>{p.skill_name}</Text>

              {/* 威力 */}
              <Text type="secondary" style={{ fontSize: 12, minWidth: 36 }}>
                Pwr {p.power}
              </Text>

              {/* 伤害范围 */}
              {isCombo ? (
                <Tooltip title={`单次伤害: ${p.min_damage}~${p.max_damage}`}>
                  <Text style={{ fontSize: 13, fontWeight: p.can_ko ? 700 : 400 }}>
                    {totalMin}~{totalMax}
                  </Text>
                </Tooltip>
              ) : (
                <Text style={{ fontSize: 13, minWidth: 80, fontWeight: p.can_ko ? 700 : 400 }}>
                  {p.min_damage}~{p.max_damage}
                </Text>
              )}

              {/* 连击标记 */}
              {isCombo && (
                <Tag color="purple" style={{ fontSize: 11, margin: 0 }}>
                  ×{hitCount} 连击
                </Tag>
              )}

              {/* HP 百分比 */}
              <Text type="secondary" style={{ fontSize: 12, minWidth: 50 }}>
                ({hpPct})
              </Text>

              {/* 属性克制标签 */}
              <Tag
                style={{ fontSize: 11, margin: 0, borderColor: effColor, color: effColor }}
              >
                {p.effectiveness_label}
                {p.effectiveness !== 1.0 && ` ×${p.effectiveness}`}
              </Tag>

              {/* STAB */}
              {p.is_stab && <Tag color="blue" style={{ fontSize: 11, margin: 0 }}>STAB</Tag>}

              {/* KO 标记 */}
              {p.can_ko && <Tag color="red" style={{ fontSize: 11, margin: 0 }}>KO!</Tag>}

              {/* 能耗 */}
              <Text type="secondary" style={{ fontSize: 11, marginLeft: 'auto' }}>
                {p.energy_cost > 0 ? `${p.energy_cost}EP` : '免费'}
              </Text>

              {/* 精度 + 警告 */}
              <Tooltip title={p.warnings.length ? p.warnings.join('\n') : undefined}>
                {confidenceTag(p.confidence)}
              </Tooltip>
            </div>
          );
        })}
      </div>
    </Card>
  );
}
