import React from 'react';
import { Card, Empty } from 'antd';

const BattleHistory: React.FC = () => (
  <Card title="战斗历史">
    <Empty description="暂无战斗记录 — 开始一场 PvP 战斗后这里会显示历史" />
  </Card>
);

export default BattleHistory;
