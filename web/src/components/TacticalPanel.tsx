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

const VISIBLE_ACTIONS = 5;

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

function buildMetricTags(action: ActionScore, metrics: ActionScore['metrics'], unknowns: string[]): React.ReactNode[] {
  const tags: React.ReactNode[] = [];

  if (action.damage_dealt != null && action.damage_dealt > 0) {
    tags.push(
      <Tag key="damage-dealt" icon={<AimOutlined />} color="red" style={{ margin: 0 }}>
        伤害 {action.damage_dealt}
      </Tag>
    );
  }
  if (action.damage_taken != null && action.damage_taken > 0) {
    tags.push(
      <Tag key="damage-taken" icon={<WarningOutlined />} color="orange" style={{ margin: 0 }}>
        承受 {action.damage_taken}
      </Tag>
    );
  }
  if (metrics?.speed_order) {
    tags.push(
      <Tag key="speed" icon={<FieldTimeOutlined />} color="blue" style={{ margin: 0 }}>
        {metrics.speed_order}
      </Tag>
    );
  }
  if (metrics?.energy_after != null) {
    tags.push(
      <Tag key="energy" icon={<ThunderboltOutlined />} color="gold" style={{ margin: 0 }}>
        余能 {metrics.energy_after}
      </Tag>
    );
  }
  if (unknowns.length > 0) {
    tags.push(
      <Tooltip key="unknowns" title={unknowns.join('\n')}>
        <Tag color="default" style={{ margin: 0 }}>
          未知 {unknowns.length}
        </Tag>
      </Tooltip>
    );
  }

  return tags;
}

const ActionRow: React.FC<{ action: ActionScore; rank: number; isTop: boolean }> = ({ action, rank, isTop }) => {
  const cat = categoryConfig[action.category || 'balanced'] || categoryConfig.balanced;
  const emphasized = isTop && action.confidence !== 'low';
  const pct = scorePercent(action.score);
  const metrics = action.metrics || {};
  const unknowns = action.unknowns || [];
  const name = actionName(action);
  const summary = action.expected_gain || action.reason || '暂无收益说明';
  const risk = action.risk || '风险较低';
  const metricTags = buildMetricTags(action, metrics, unknowns);
  const visibleMetricTags = metricTags.slice(0, 3);
  const hiddenMetricCount = metricTags.length - visibleMetricTags.length;
  const detailText = `${summary} · ${risk}`;
  const detailsTitle = (
    <div>
      <div>{summary}</div>
      <div>{risk}</div>
    </div>
  );

  return (
    <div
      className={isTop ? 'tactical-action-row tactical-action-row-top' : 'tactical-action-row'}
      style={{
        background: emphasized ? '#f6ffed' : '#fff',
        border: emphasized ? '1px solid #b7eb8f' : '1px solid #f0f0f0',
      }}
    >
      <Text strong={isTop} className="tactical-action-rank" style={{ color: emphasized ? '#389e0d' : '#666' }}>
        {rank}
      </Text>
      <div style={{ minWidth: 0 }}>
        <div className="tactical-action-main">
          <Tooltip title={name}>
            <Text strong className="tactical-action-name">
              {name}
            </Text>
          </Tooltip>
          <Tag color={cat.color} style={{ margin: 0, fontSize: 11 }}>{cat.label}</Tag>
          {action.can_ko && <Tag color="red" style={{ margin: 0, fontSize: 11 }}>KO</Tag>}
          {action.energy_cost > 0 && <Tag color="purple" style={{ margin: 0, fontSize: 11 }}>耗能 {action.energy_cost}</Tag>}
          {confidenceTag(action.confidence)}
        </div>
        <Tooltip title={detailsTitle}>
          <div className="tactical-action-subline">
            <Text
              type={risk.includes('反杀') ? 'danger' : 'secondary'}
              className="tactical-action-detail"
            >
              {detailText}
            </Text>
            <div className="tactical-action-metrics">
              {visibleMetricTags}
              {hiddenMetricCount > 0 && (
                <Tooltip title={`还有 ${hiddenMetricCount} 项指标`}>
                  <Tag color="default" style={{ margin: 0 }}>
                    +{hiddenMetricCount}
                  </Tag>
                </Tooltip>
              )}
            </div>
          </div>
        </Tooltip>
      </div>
      <div className="tactical-action-score">
        <Tooltip title={`行动评分 ${action.score.toFixed(3)}`}>
          <Text type="secondary" style={{ fontSize: 11 }}>
            {pct}
          </Text>
          <Progress
            percent={pct}
            size="small"
            strokeColor={emphasized ? '#52c41a' : '#1677ff'}
            showInfo={false}
          />
        </Tooltip>
      </div>
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
  const visibleCount = Math.min(VISIBLE_ACTIONS, recommendations.actions.length);
  const topAction = recommendations.actions[0];
  const primaryIsLowConfidence = topAction?.confidence === 'low';

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
          type={recommendations.confidence === 'low' || primaryIsLowConfidence ? 'warning' : 'success'}
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

      <div className="tactical-action-header">
        <Text type="secondary" style={{ fontSize: 12 }}>
          候选 {visibleCount}/{recommendations.actions.length}
        </Text>
      </div>
      <div className="tactical-action-list">
        <div className="tactical-action-list-inner">
          {recommendations.actions.map((action, i) => (
            <ActionRow key={`${action.action_type}-${action.skill_id || action.switch_to_name || i}`} action={action} rank={i + 1} isTop={i === 0} />
          ))}
        </div>
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
