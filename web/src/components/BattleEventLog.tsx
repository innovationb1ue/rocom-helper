import React, { useMemo, useState } from 'react';
import { Timeline, Tag, Select, Button, Space } from 'antd';
import type { FormattedBattleEvent } from '../stores/battleStore';

const KIND_LABELS: Record<string, string> = {
  battle_enter: '战斗开始',
  round_start: '回合开始',
  battle_finish: '战斗结束',
  skill_cast: '技能施放',
  damage: '伤害',
  defeat: '击败',
  heal: '治疗',
  energy: '能量',
  change_pet: '换宠',
  effect_apply: '效果附加',
  effect_stage: '效果阶段',
  effect_link: '效果链接',
  effect_trigger: '效果触发',
  revive: '复活',
  skill_select: '选择技能',
  skill_declare: '技能声明',
  action_ack: '动作确认',
  special_refresh: '特殊刷新',
  round_flow: '回合流',
  ai_action: 'AI行动',
  pvp_perform: 'PVP演出',
  reinforcement: '补宠',
};

const KIND_COLORS: Record<string, string> = {
  battle_enter: '#52c41a',
  battle_finish: '#ff4d4f',
  damage: '#ff4d4f',
  defeat: '#ff4d4f',
  heal: '#52c41a',
  change_pet: '#13c2c2',
  skill_cast: '#1890ff',
  energy: '#faad14',
  pvp_perform: '#722ed1',
  reinforcement: '#13c2c2',
};

interface Props {
  events: FormattedBattleEvent[];
  maxDisplay?: number;
}

const BattleEventLog: React.FC<Props> = ({ events = [], maxDisplay = 80 }) => {
  const [filter, setFilter] = useState<string | undefined>(undefined);
  const [showCount, setShowCount] = useState(maxDisplay);

  const filtered = useMemo(() => {
    let result = events;
    if (filter) {
      result = events.filter((e) => e.kind === filter);
    }
    return result.slice(-showCount).reverse();
  }, [events, filter, showCount]);

  const allKinds = useMemo(() => {
    const kinds = new Set(events.map((e) => e.kind));
    return Array.from(kinds).sort();
  }, [events]);

  const hasMore = filter
    ? events.filter((e) => e.kind === filter).length > showCount
    : events.length > showCount;

  return (
    <div>
      <div style={{ marginBottom: 8, display: 'flex', gap: 8, alignItems: 'center' }}>
        <Select
          allowClear
          placeholder="过滤事件类型"
          style={{ width: 160 }}
          value={filter}
          onChange={(v) => { setFilter(v); setShowCount(maxDisplay); }}
          options={allKinds.map((k) => ({
            value: k,
            label: KIND_LABELS[k] || k,
          }))}
        />
        <span style={{ color: '#999', fontSize: 12 }}>
          共 {filter ? events.filter((e) => e.kind === filter).length : events.length} 条
        </span>
      </div>
      <Timeline
        items={filtered.map((ev) => ({
          color: KIND_COLORS[ev.kind] || ev.color || 'blue',
          content: (
            <div style={{ fontSize: 13 }}>
              <Space size={4}>
                <Tag style={{ margin: 0, fontSize: 11 }}>
                  {KIND_LABELS[ev.kind] || ev.kind}
                </Tag>
                {ev.round > 0 && <span style={{ color: '#999' }}>R{ev.round}</span>}
              </Space>
              <div style={{ marginTop: 2 }}>{ev.summary}</div>
            </div>
          ),
        }))}
      />
      {hasMore && (
        <Button type="link" size="small" onClick={() => setShowCount((c) => c + maxDisplay)}>
          加载更多...
        </Button>
      )}
    </div>
  );
};

export default BattleEventLog;
