import React from 'react';
import { Card, Progress, Tag, Badge } from 'antd';
import { CloseCircleFilled } from '@ant-design/icons';
import TypeBadge from './TypeBadge';
import type { BattlePet } from '../stores/battleStore';

interface Props {
  pets: BattlePet[];
  activePet: BattlePet | null;
  side: 'my' | 'opp';
  label: string;
}

const TeamRoster: React.FC<Props> = ({ pets, activePet, label }) => {
  return (
    <Card size="small" title={label} style={{ height: '100%' }}>
      {pets.length === 0 && <div style={{ color: '#999', fontSize: 13 }}>暂无精灵</div>}
      {pets.map((pet) => {
        const isActive = activePet?.pet_id === pet.pet_id;
        const isDefeated = pet.current_hp <= 0;
        const pct = Math.round(pet.hp_pct * 100);
        return (
          <div
            key={pet.pet_id}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              padding: '4px 6px',
              marginBottom: 4,
              background: isActive ? '#e6f7ff' : 'transparent',
              borderLeft: isActive ? '3px solid #1890ff' : '3px solid transparent',
              borderRadius: 4,
              opacity: isDefeated ? 0.5 : 1,
            }}
          >
            <span style={{ width: 70, fontWeight: isActive ? 'bold' : 'normal', fontSize: 13, flexShrink: 0 }}>
              {pet.name}
            </span>
            <div style={{ flexShrink: 0, display: 'flex', gap: 2 }}>
              {pet.types.map((t) => <TypeBadge key={t} typeId={t} size="small" />)}
            </div>
            <div style={{ flex: 1, minWidth: 80 }}>
              <Progress
                percent={pct}
                size="small"
                status={isDefeated ? 'exception' : pct < 25 ? 'exception' : 'active'}
                format={() => `${pet.current_hp}/${pet.max_hp}`}
              />
            </div>
            <Tag style={{ margin: 0, fontSize: 11 }}>
              {isDefeated ? (
                <CloseCircleFilled style={{ color: '#ff4d4f' }} />
              ) : (
                <>E:{pet.energy}</>
              )}
            </Tag>
            {pet.effective_speed != null && !isDefeated && (
              <Tag
                style={{ margin: 0, fontSize: 11 }}
                color={
                  pet.base_speed != null && pet.effective_speed > pet.base_speed ? 'green' :
                  pet.base_speed != null && pet.effective_speed < pet.base_speed ? 'red' :
                  undefined
                }
              >
                S:{pet.effective_speed}
              </Tag>
            )}
            {isActive && (
              <Badge status="processing" style={{ marginLeft: -4 }} />
            )}
          </div>
        );
      })}
    </Card>
  );
};

export default TeamRoster;
