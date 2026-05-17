import React from 'react';
import { Card, Tag, Progress } from 'antd';
import type { TacticalRecommendation, ActionScore } from '../stores/battleStore';

interface Props {
  recommendations: TacticalRecommendation | null;
}

const confidenceConfig: Record<string, { color: string; label: string }> = {
  high: { color: 'green', label: '高置信' },
  medium: { color: 'orange', label: '中置信' },
  low: { color: 'red', label: '低置信' },
};

const ActionRow: React.FC<{ action: ActionScore; rank: number; isTop: boolean }> = ({ action, rank, isTop }) => {
  const tags: React.ReactNode[] = [];
  if (action.can_ko) tags.push(<Tag key="ko" color="red" style={{ fontSize: 11 }}>击杀</Tag>);
  if (action.action_type === 'switch') tags.push(<Tag key="sw" color="blue" style={{ fontSize: 11 }}>换宠</Tag>);
  if (action.energy_cost > 0 && action.action_type === 'skill') {
    tags.push(<Tag key="en" color="purple" style={{ fontSize: 11 }}>耗能 {action.energy_cost}</Tag>);
  }

  const name = action.action_type === 'switch'
    ? `换上 ${action.switch_to_name}`
    : action.skill_name || '?';

  const scorePct = Math.round(Math.max(0, Math.min(1, (action.score + 0.5))) * 100);

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        padding: '6px 8px',
        borderRadius: 4,
        background: isTop ? '#f6ffed' : 'transparent',
        border: isTop ? '1px solid #b7eb8f' : '1px solid transparent',
        marginBottom: 4,
      }}
    >
      <span style={{
        fontWeight: isTop ? 700 : 400,
        fontSize: 14,
        color: isTop ? '#389e0d' : '#666',
        minWidth: 24,
      }}>
        {rank}
      </span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontWeight: 500, fontSize: 13 }}>{name}</span>
          {tags}
        </div>
        <div style={{ fontSize: 11, color: '#888', marginTop: 2 }}>
          {action.reason}
          {action.damage_dealt != null && action.damage_dealt > 0 && (
            <span style={{ marginLeft: 8 }}>伤害 {action.damage_dealt}</span>
          )}
          {action.damage_taken != null && action.damage_taken > 0 && (
            <span style={{ marginLeft: 8, color: '#ff4d4f' }}>承受 {action.damage_taken}</span>
          )}
        </div>
      </div>
      <div style={{ width: 60 }}>
        <Progress
          percent={scorePct}
          size="small"
          strokeColor={isTop ? '#52c41a' : '#1890ff'}
          showInfo={false}
        />
      </div>
    </div>
  );
};

const TacticalPanel: React.FC<Props> = ({ recommendations }) => {
  if (!recommendations || !recommendations.actions || recommendations.actions.length === 0) {
    return null;
  }

  const conf = confidenceConfig[recommendations.confidence] || confidenceConfig.medium;

  return (
    <Card
      size="small"
      title={
        <span>
          战术推荐
          <Tag color={conf.color} style={{ marginLeft: 8, fontSize: 10 }}>
            {conf.label}
          </Tag>
          {recommendations.round_number > 0 && (
            <span style={{ marginLeft: 8, fontSize: 12, color: '#888' }}>
              R{recommendations.round_number}
            </span>
          )}
        </span>
      }
      style={{ marginBottom: 12 }}
      styles={{ body: { padding: '8px 12px' } }}
    >
      {recommendations.actions.map((action, i) => (
        <ActionRow key={i} action={action} rank={i + 1} isTop={i === 0} />
      ))}
    </Card>
  );
};

export default TacticalPanel;
