import React from 'react';
import { Timeline, Tag } from 'antd';

interface Props {
  events: { opcode: number; round?: number; [k: string]: unknown }[];
}

const OPCODE_LABELS: Record<number, string> = {
  0x1316: '进入战斗', 0x131A: '回合开始', 0x1322: '技能声明',
  0x1324: '动作结算', 0x132C: '战斗结束', 0x130B: '选技能',
  0x13F4: '特殊刷新', 0x1312: '回合流', 0x130C: '动作确认',
  0x13FC: 'PVP演出', 0x13F3: '预演', 0x0102: '阵容初始化',
  0x1326: '自动战斗', 0x132A: '角色离场', 0x132D: '强制结束',
  0x1334: '表情', 0x133C: '捕捉结果', 0x13F6: 'AI技能提示',
};

const BattleTimeline: React.FC<Props> = ({ events }) => (
  <Timeline
    items={events.slice(-20).reverse().map((ev, i) => ({
      color: ev.opcode === 0x132C ? 'red' : ev.opcode === 0x1316 ? 'green' : 'blue',
      children: (
        <div>
          <Tag>{OPCODE_LABELS[ev.opcode] || `0x${ev.opcode.toString(16)}`}</Tag>
          {ev.round != null && <span>R{ev.round}</span>}
        </div>
      ),
    }))}
  />
);

export default BattleTimeline;
