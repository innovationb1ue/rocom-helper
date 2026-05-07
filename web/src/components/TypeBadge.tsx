import React from 'react';
import { Tag } from 'antd';
import { TYPE_COLORS, TYPE_NAMES } from '../utils/typeColors';

interface Props {
  typeId: number;
  size?: 'small' | 'default';
}

const TypeBadge: React.FC<Props> = ({ typeId, size = 'default' }) => {
  const color = TYPE_COLORS[typeId] || '#999';
  const name = TYPE_NAMES[typeId] || `Type ${typeId}`;
  return (
    <Tag color={color} style={{ color: '#fff', fontWeight: 'bold',
      fontSize: size === 'small' ? '11px' : '13px',
      padding: size === 'small' ? '0 4px' : '2px 8px',
    }}>
      {name}
    </Tag>
  );
};

export default TypeBadge;
