import React from 'react';
import { Card, Table, Tag } from 'antd';
import { TYPE_COLORS, TYPE_LIST, TYPE_CHART, multiplierColor, textColorFor } from '../utils/typeColors';

const TypeChartPage: React.FC = () => {
  const types = TYPE_LIST;
  const chart = TYPE_CHART;

  const columns = [
    { title: '攻\\防', dataIndex: 'name', fixed: 'left' as const, width: 60,
      render: (name: string) => {
        const id = types.find(t => t.name === name)?.id ?? 0;
        const bg = TYPE_COLORS[id] || '#999';
        return (
          <span style={{
            background: bg,
            color: textColorFor(bg),
            padding: '2px 4px',
            borderRadius: 4,
            fontSize: 11,
            fontWeight: 600,
          }}>{name}</span>
        );
      },
    },
    ...types.map(t => ({
      title: <span style={{ fontSize: 10 }}>{t.name}</span>,
      dataIndex: `type_${t.id}`,
      width: 45,
      render: (val: number) => {
        if (val === 1.0 || val === undefined) return <span style={{ color: '#ccc' }}>-</span>;
        const bg = multiplierColor(val);
        return (
          <span style={{
            background: bg,
            color: textColorFor(bg),
            padding: '1px 3px',
            borderRadius: 3,
            fontSize: 10,
            fontWeight: 600,
          }}>
            ×{val}
          </span>
        );
      },
    })),
  ];

  const dataSource = types.map(atk => {
    const row: Record<string, unknown> = { name: atk.name, key: atk.id };
    const atkChart = chart[String(atk.id)] || {};
    types.forEach(def => {
      row[`type_${def.id}`] = atkChart[String(def.id)] || 1.0;
    });
    return row;
  });

  return (
    <Card title="属性克制表" size="small">
      <Table
        dataSource={dataSource}
        columns={columns}
        pagination={false}
        scroll={{ x: types.length * 45 + 60 }}
        size="small"
        bordered
      />
      <div style={{ marginTop: 8, fontSize: 12 }}>
        <Tag color="#44AA44">克制 ≥2x</Tag>
        <Tag color="#888888">普通 1x</Tag>
        <Tag color="#FF8888">抵抗 &lt;1x</Tag>
        <Tag color="#333">无效 0x</Tag>
      </div>
    </Card>
  );
};

export default TypeChartPage;
