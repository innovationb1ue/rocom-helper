import React from 'react';
import { Card } from 'antd';
import TypeBadge from './TypeBadge';

interface Props {
  pet: { id: number; name: string; types?: number[]; base_id?: number };
  onClick?: () => void;
  selected?: boolean;
}

const PetCard: React.FC<Props> = ({ pet, onClick, selected }) => (
  <Card
    hoverable
    size="small"
    onClick={onClick}
    style={{ border: selected ? '2px solid #1890ff' : undefined, cursor: 'pointer' }}
    title={pet.name}
    extra={<span style={{ color: '#888' }}>#{pet.id}</span>}
  >
    <div>
      {(pet.types || []).map((t) => (
        <TypeBadge key={t} typeId={t} size="small" />
      ))}
    </div>
  </Card>
);

export default PetCard;
