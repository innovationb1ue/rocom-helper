import React, { useState } from 'react';
import { Table, Input, Space, Drawer, Descriptions } from 'antd';
import { usePets } from '../hooks/usePets';
import { fetchPetDetail } from '../utils/api';

type PetDetail = {
  pet?: {
    id?: React.ReactNode;
    name?: React.ReactNode;
    base_id?: React.ReactNode;
  };
};

const PetBrowser: React.FC = () => {
  const { pets, total, loading, searchName, page, pageSize, setSearchName, setPage } = usePets();
  const [detail, setDetail] = useState<PetDetail | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);

  const showDetail = async (id: number) => {
    const data = await fetchPetDetail(id);
    setDetail(data as PetDetail);
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
            <Descriptions.Item label="ID">{detail.pet?.id}</Descriptions.Item>
            <Descriptions.Item label="名称">{detail.pet?.name}</Descriptions.Item>
            <Descriptions.Item label="Base ID">{detail.pet?.base_id}</Descriptions.Item>
          </Descriptions>
        )}
      </Drawer>
    </div>
  );
};

export default PetBrowser;
