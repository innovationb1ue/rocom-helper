import React from 'react';
import { Alert, Card, Progress, Space, Tag, Tooltip, Typography } from 'antd';
import {
  AimOutlined,
  FieldTimeOutlined,
  SafetyOutlined,
  SwapOutlined,
  ThunderboltOutlined,
  WarningOutlined,
} from '@ant-design/icons';
import type { TacticalRecommendation, ActionScore, OpponentAction } from '../stores/battleStore';

const { Text } = Typography;

interface Props {
  recommendations: TacticalRecommendation | null;
}

const confidenceConfig: Record<string, { color: string; label: string }> = {
  high: { color: 'green', label: '高置信' },
  medium: { color: 'orange', label: '中置信' },
  low: { color: 'red', label: '低置信' },
};

const categoryConfig: Record<string, { color: string; label: string }> = {
  finisher: { color: 'red', label: '击杀线' },
  pressure: { color: 'volcano', label: '压制' },
  conservative: { color: 'green', label: '保守' },
  gamble: { color: 'magenta', label: '赌线' },
  switch: { color: 'blue', label: '换宠' },
  setup: { color: 'purple', label: '铺垫' },
  balanced: { color: 'geekblue', label: '均衡' },
};

function scorePercent(score: number): number {
  return Math.round(Math.max(0, Math.min(1, score + 0.35)) * 100);
}

function confidenceTag(confidence?: string) {
  const conf = confidenceConfig[confidence || 'medium'] || confidenceConfig.medium;
  return <Tag color={conf.color} style={{ margin: 0, fontSize: 11 }}>{conf.label}</Tag>;
}

function actionName(action: ActionScore): string {
  return action.action_type === 'switch'
    ? `换上 ${action.switch_to_name || '?'}`
    : action.skill_name || '?';
}

const ActionRow: React.FC<{ action: ActionScore; rank: number; isTop: boolean }> = ({ action, rank, isTop }) => {
  const cat = categoryConfig[action.category || 'balanced'] || categoryConfig.balanced;
  const pct = scorePercent(action.score);
  const metrics = action.metrics || {};
  const unknowns = action.unknowns || [];

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: '28px minmax(0, 1fr) 76px',
        gap: 8,
        alignItems: 'center',
        padding: '8px 10px',
        borderRadius: 6,
        background: isTop ? '#f6ffed' : '#fff',
        border: isTop ? '1px solid #b7eb8f' : '1px solid #f0f0f0',
      }}
    >
      <Text strong={isTop} style={{ color: isTop ? '#389e0d' : '#666' }}>{rank}</Text>
      <div style={{ minWidth: 0 }}>
        <Space size={4} wrap>
          <Text strong style={{ fontSize: 13 }}>{actionName(action)}</Text>
          <Tag color={cat.color} style={{ margin: 0, fontSize: 11 }}>{cat.label}</Tag>
          {action.can_ko && <Tag color="red" style={{ margin: 0, fontSize: 11 }}>KO</Tag>}
          {action.energy_cost > 0 && <Tag color="purple" style={{ margin: 0, fontSize: 11 }}>耗能 {action.energy_cost}</Tag>}
          {confidenceTag(action.confidence)}
        </Space>
        <div style={{ marginTop: 4, fontSize: 12, lineHeight: 1.45 }}>
          <Text>{action.expected_gain || action.reason}</Text>
          <br />
          <Text type={action.risk?.includes('反杀') ? 'danger' : 'secondary'}>
            {action.risk || '风险较低'}
          </Text>
        </div>
        <Space size={6} wrap style={{ marginTop: 4 }}>
          {action.damage_dealt != null && action.damage_dealt > 0 && (
            <Tag icon={<AimOutlined />} color="red" style={{ margin: 0 }}>伤害 {action.damage_dealt}</Tag>
          )}
          {action.damage_taken != null && action.damage_taken > 0 && (
            <Tag icon={<WarningOutlined />} color="orange" style={{ margin: 0 }}>承受 {action.damage_taken}</Tag>
          )}
          {metrics.speed_order && (
            <Tag icon={<FieldTimeOutlined />} color="blue" style={{ margin: 0 }}>{metrics.speed_order}</Tag>
          )}
          {metrics.energy_after != null && (
            <Tag icon={<ThunderboltOutlined />} color="gold" style={{ margin: 0 }}>余能 {metrics.energy_after}</Tag>
          )}
          {unknowns.length > 0 && (
            <Tooltip title={unknowns.join('\n')}>
              <Tag color="default" style={{ margin: 0 }}>未知 {unknowns.length}</Tag>
            </Tooltip>
          )}
        </Space>
      </div>
      <Tooltip title={`行动评分 ${action.score.toFixed(3)}`}>
        <Progress
          percent={pct}
          size="small"
          strokeColor={isTop ? '#52c41a' : '#1677ff'}
          showInfo={false}
        />
      </Tooltip>
    </div>
  );
};

const OpponentActionRow: React.FC<{ action: OpponentAction }> = ({ action }) => {
  const label = action.action_type === 'switch'
    ? `换上 ${action.switch_to_name || '?'}`
    : action.skill_name || '?';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 160 }}>
      {action.action_type === 'switch' ? <SwapOutlined /> : <AimOutlined />}
      <Text style={{ fontSize: 12, maxWidth: 130 }} ellipsis>{label}</Text>
      <Tag color={action.can_ko ? 'red' : 'default'} style={{ margin: 0, fontSize: 11 }}>
        {Math.round(action.probability * 100)}%
      </Tag>
      {action.threat_damage != null && action.threat_damage > 0 && (
        <Text type="secondary" style={{ fontSize: 11 }}>{action.threat_damage}</Text>
      )}
    </div>
  );
};

const TacticalPanel: React.FC<Props> = ({ recommendations }) => {
  if (!recommendations || !recommendations.actions || recommendations.actions.length === 0) {
    return null;
  }

  const conf = confidenceConfig[recommendations.confidence] || confidenceConfig.medium;
  const reliability = recommendations.reliability;
  const speedLine = recommendations.metrics?.speed_line as { order?: string } | undefined;
  const energyWindow = recommendations.metrics?.energy_window as { my?: number; opp?: number } | undefined;
  const petCount = recommendations.metrics?.pet_count as { my_alive?: number; opp_alive?: number; delta?: number } | undefined;

  return (
    <Card
      size="small"
      title={
        <Space size={8} wrap>
          <span>本回合行动</span>
          <Tag color={conf.color} style={{ margin: 0, fontSize: 11 }}>{conf.label}</Tag>
          {recommendations.round_number > 0 && <Tag style={{ margin: 0 }}>R{recommendations.round_number}</Tag>}
        </Space>
      }
      style={{ marginBottom: 12 }}
      styles={{ body: { padding: '10px 12px' } }}
    >
      {recommendations.primary_plan && (
        <Alert
          type={recommendations.confidence === 'low' ? 'warning' : 'success'}
          showIcon
          title={recommendations.primary_plan}
          style={{ marginBottom: 8 }}
        />
      )}

      <Space size={6} wrap style={{ marginBottom: 8 }}>
        {speedLine?.order && <Tag icon={<FieldTimeOutlined />} color="blue">{speedLine.order}</Tag>}
        {energyWindow && <Tag icon={<ThunderboltOutlined />} color="gold">能量 {energyWindow.my ?? '-'} / {energyWindow.opp ?? '-'}</Tag>}
        {petCount && <Tag icon={<SafetyOutlined />} color={petCount.delta && petCount.delta > 0 ? 'green' : 'default'}>存活 {petCount.my_alive} / {petCount.opp_alive}</Tag>}
        {reliability && <Tag color={confidenceConfig[reliability.confidence]?.color || 'default'}>可靠性 {reliability.score}</Tag>}
      </Space>

      {recommendations.warnings && recommendations.warnings.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginBottom: 8 }}>
          {recommendations.warnings.map((warning) => (
            <Alert key={warning} type="warning" title={warning} showIcon style={{ padding: '4px 8px' }} />
          ))}
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {recommendations.actions.map((action, i) => (
          <ActionRow key={`${action.action_type}-${action.skill_id || action.switch_to_name || i}`} action={action} rank={i + 1} isTop={i === 0} />
        ))}
      </div>

      <div style={{ marginTop: 10, borderTop: '1px solid #f0f0f0', paddingTop: 8 }}>
        <Text type="secondary" style={{ fontSize: 12 }}>对手最可能行动</Text>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 6 }}>
          {recommendations.opp_predicted.slice(0, 4).map((action, i) => (
            <Tooltip key={`${action.action_type}-${action.skill_id || action.switch_to_name || i}`} title={action.reason || undefined}>
              <div>
                <OpponentActionRow action={action} />
              </div>
            </Tooltip>
          ))}
        </div>
      </div>

      {reliability && (reliability.flags.length > 0 || reliability.missing_reasons.length > 0) && (
        <div style={{ marginTop: 10, borderTop: '1px solid #f0f0f0', paddingTop: 8 }}>
          <Space size={4} wrap>
            {reliability.flags.slice(0, 4).map((flag) => (
              <Tag key={flag.code} color={flag.code === 'calibrated' ? 'green' : 'default'} style={{ margin: 0 }}>
                {flag.label} {flag.count}
              </Tag>
            ))}
            {reliability.missing_reasons.slice(0, 3).map((reason) => (
              <Tooltip key={reason} title={reason}>
                <Tag color="orange" style={{ margin: 0 }}>待确认</Tag>
              </Tooltip>
            ))}
          </Space>
        </div>
      )}
    </Card>
  );
};

export default TacticalPanel;
