import React, { useState } from 'react';
import { Table, Input, Space, Drawer, Descriptions } from 'antd';
import { usePets } from '../hooks/usePets';
import TypeBadge from '../components/TypeBadge';
import { fetchPetDetail } from '../utils/api';

const PetBrowser: React.FC = () => {
  const { pets, total, types, loading, searchName, page, pageSize, setSearchName, setPage } = usePets();
  const [detail, setDetail] = useState<Record<string, unknown> | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);

  const showDetail = async (id: number) => {
    const data = await fetchPetDetail(id);
    setDetail(data);
    setDrawerOpen(true);
  };

  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <Input.Search
          placeholder="搜索精灵名称"
          value={searchName}
          onChange={(e) => setSearchName(e.target.value)}
          onSearch={() => setPage(1)}
          style={{ width: 250 }}
        />
      </Space>
      <Table
        dataSource={pets}
        rowKey="id"
        loading={loading}
        pagination={{ current: page, pageSize, total, onChange: setPage }}
        onRow={(record) => ({ onClick: () => showDetail(record.id), style: { cursor: 'pointer' } })}
        columns={[
          { title: 'ID', dataIndex: 'id', width: 100 },
          { title: '名称', dataIndex: 'name', width: 150 },
          { title: 'Base ID', dataIndex: 'base_id', width: 100 },
        ]}
      />
      <Drawer title="精灵详情" open={drawerOpen} onClose={() => setDrawerOpen(false)} width={400}>
        {detail && (
          <Descriptions column={1} size="small">
            <Descriptions.Item label="ID">{(detail.pet as Record<string, unknown>)?.id}</Descriptions.Item>
            <Descriptions.Item label="名称">{(detail.pet as Record<string, unknown>)?.name as string}</Descriptions.Item>
            <Descriptions.Item label="Base ID">{(detail.pet as Record<string, unknown>)?.base_id as number}</Descriptions.Item>
          </Descriptions>
        )}
      </Drawer>
    </div>
  );
};

export default PetBrowser;
