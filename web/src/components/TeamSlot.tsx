import React from 'react';
import { Card, Button } from 'antd';
import { CloseOutlined } from '@ant-design/icons';
import TypeBadge from './TypeBadge';

interface Props {
  pet: { id: number; name: string; types?: number[] } | null;
  slotIndex: number;
  onRemove: () => void;
  onSelect: () => void;
}

const TeamSlot: React.FC<Props> = ({ pet, slotIndex, onRemove, onSelect }) => (
  <Card
    size="small"
    style={{ minWidth: 140, textAlign: 'center', borderStyle: pet ? 'solid' : 'dashed' }}
    title={pet ? pet.name : `Slot ${slotIndex + 1}`}
    extra={pet ? <Button type="text" size="small" icon={<CloseOutlined />} onClick={onRemove} /> : null}
  >
    {pet ? (
      <div>
        {(pet.types || []).map((t) => <TypeBadge key={t} typeId={t} size="small" />)}
      </div>
    ) : (
      <Button type="dashed" size="small" onClick={onSelect}>选择精灵</Button>
    )}
  </Card>
);

export default TeamSlot;
