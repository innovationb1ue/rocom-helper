import React from 'react';
import { Progress, Tooltip } from 'antd';
import { multiplierColor, TYPE_NAMES } from '../utils/typeColors';

interface Props {
  coverage: Record<string, number>;
}

const CoverageRadar: React.FC<Props> = ({ coverage }) => {
  const entries = Object.entries(coverage);
  const effective = entries.filter(([, m]) => m >= 2.0).length;
  const neutral = entries.filter(([, m]) => m >= 1.0 && m < 2.0).length;
  const resisted = entries.filter(([, m]) => m > 0 && m < 1.0).length;
  const immune = entries.filter(([, m]) => m === 0).length;
  const total = entries.length;
  const score = total > 0 ? ((effective * 2 + neutral) / (total * 2) * 100).toFixed(0) : '0';

  return (
    <div>
      <div style={{ marginBottom: 8 }}>
        <Progress percent={Number(score)} size="small" />
        <span>有效覆盖: {effective}/{total} | 抵抗: {resisted} | 无效: {immune}</span>
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
        {entries.map(([name, mult]) => (
          <Tooltip key={name} title={`${name}: ×${mult}`}>
            <span style={{
              display: 'inline-block', padding: '2px 6px', borderRadius: 4,
              background: multiplierColor(mult), color: '#fff', fontSize: 11,
            }}>
              {name} ×{mult}
            </span>
          </Tooltip>
        ))}
      </div>
    </div>
  );
};

export default CoverageRadar;
