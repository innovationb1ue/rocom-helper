import React from 'react';
import { Tag } from 'antd';
import { TYPE_COLORS, TYPE_NAMES, textColorFor } from '../utils/typeColors';

interface Props {
  typeId: number;
  size?: 'small' | 'default';
}

const TypeBadge: React.FC<Props> = ({ typeId, size = 'default' }) => {
  const bg = TYPE_COLORS[typeId] || '#999';
  const name = TYPE_NAMES[typeId] || `Type ${typeId}`;
  const textColor = textColorFor(bg);
  return (
    <Tag style={{
      background: bg,
      color: textColor,
      border: 'none',
      fontWeight: 600,
      fontSize: size === 'small' ? '11px' : '13px',
      padding: size === 'small' ? '0 4px' : '2px 8px',
      lineHeight: size === 'small' ? '18px' : '20px',
    }}>
      {name}
    </Tag>
  );
};

export default TypeBadge;
