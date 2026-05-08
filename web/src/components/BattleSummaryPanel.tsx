import React from 'react';
import { Card, Descriptions, Tag, Progress, Space } from 'antd';
import { TrophyOutlined, FrownOutlined } from '@ant-design/icons';
import type { BattleSummary } from '../stores/battleStore';

interface Props {
  summary: BattleSummary | null;
}

const BattleSummaryPanel: React.FC<Props> = ({ summary }) => {
  if (!summary) return null;

  const isWin = summary.result === 'WIN';

  const petList = (pets: { name: string; hp: number; max_hp: number; status: string }[]) =>
    pets.map((p) => {
      const pct = p.max_hp > 0 ? Math.round((p.hp / p.max_hp) * 100) : 0;
      return (
        <div key={p.name} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
          <span style={{ width: 60, fontSize: 12 }}>{p.name}</span>
          <Progress percent={pct} size="small" style={{ flex: 1 }} />
          <Tag color={p.status === '存活' ? 'green' : 'red'} style={{ margin: 0, fontSize: 11 }}>
            {p.status}
          </Tag>
        </div>
      );
    });

  return (
    <Card
      size="small"
      title={
        <Space>
          {isWin ? <TrophyOutlined style={{ color: '#faad14' }} /> : <FrownOutlined style={{ color: '#ff4d4f' }} />}
          <span>战斗结束: {summary.result}</span>
        </Space>
      }
      style={{ marginTop: 12 }}
    >
      <Descriptions size="small" column={3} style={{ marginBottom: 12 }}>
        <Descriptions.Item label="回合数">{summary.rounds}</Descriptions.Item>
      </Descriptions>

      <div style={{ display: 'flex', gap: 16 }}>
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 'bold', marginBottom: 4, fontSize: 13 }}>我方</div>
          {petList(summary.my_pets_final)}
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 'bold', marginBottom: 4, fontSize: 13 }}>敌方</div>
          {petList(summary.opp_pets_final)}
        </div>
      </div>
    </Card>
  );
};

export default BattleSummaryPanel;
