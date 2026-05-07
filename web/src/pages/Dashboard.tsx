import React, { useEffect, useState } from 'react';
import { Card, Row, Col, Statistic, Typography } from 'antd';
import { ThunderboltOutlined, TeamOutlined, DatabaseOutlined } from '@ant-design/icons';
import { fetchDataStatus } from '../utils/api';

const Dashboard: React.FC = () => {
  const [status, setStatus] = useState<Record<string, unknown>>({});

  useEffect(() => {
    fetchDataStatus().then(setStatus).catch(() => {});
  }, []);

  const tables = (status as { loaded_tables?: Record<string, number> }).loaded_tables || {};
  const total = (status as { total_records?: number }).total_records || 0;

  return (
    <div>
      <Typography.Title level={3}>Roco PvP Helper</Typography.Title>
      <Row gutter={16}>
        <Col span={8}>
          <Card><Statistic title="数据记录" value={total} prefix={<DatabaseOutlined />} /></Card>
        </Col>
        <Col span={8}>
          <Card><Statistic title="数据表" value={Object.keys(tables).length} prefix={<DatabaseOutlined />} /></Card>
        </Col>
        <Col span={8}>
          <Card><Statistic title="属性类型" value={21} prefix={<ThunderboltOutlined />} /></Card>
        </Col>
      </Row>
      <div style={{ marginTop: 16 }}>
        <Card title="数据表统计" size="small">
          <Row gutter={[8, 8]}>
            {Object.entries(tables).map(([key, count]) => (
              <Col span={8} key={key}>
                <Statistic title={key} value={count as number} />
              </Col>
            ))}
          </Row>
        </Card>
      </div>
    </div>
  );
};

export default Dashboard;
