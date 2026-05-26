import { Alert, Card, Space, Tag } from 'antd';
import type { HookAdvice } from '../stores/battleStore';

interface Props {
  advice: HookAdvice[];
}

const priorityConfig: Record<number, { color: string; label: string }> = {
  0: { color: 'red', label: '紧急' },
  1: { color: 'orange', label: '重要' },
  2: { color: 'blue', label: '提示' },
};

export default function HookAdvicePanel({ advice }: Props) {
  if (advice.length === 0) return null;

  const grouped = new Map<string, HookAdvice[]>();
  for (const a of advice) {
    const list = grouped.get(a.hook_id) || [];
    list.push(a);
    grouped.set(a.hook_id, list);
  }

  return (
    <Card size="small" title="战术分析" style={{ marginBottom: 12 }}>
      <Space orientation="vertical" style={{ width: '100%' }}>
        {Array.from(grouped.entries()).map(([hookId, items]) =>
          items.map((item, idx) => {
            const cfg = priorityConfig[item.priority] ?? priorityConfig[2];
            return (
              <Alert
                key={`${hookId}-${idx}`}
                type={item.priority === 0 ? 'error' : item.priority === 1 ? 'warning' : 'info'}
                showIcon
                title={
                  <Space>
                    <span>{item.title}</span>
                    <Tag color={cfg.color}>{cfg.label}</Tag>
                  </Space>
                }
                description={
                  <ul style={{ margin: 0, paddingLeft: 16 }}>
                    {item.messages.map((m, i) => (
                      <li key={i}>{m.message}</li>
                    ))}
                  </ul>
                }
                style={{ padding: '8px 12px' }}
              />
            );
          })
        )}
      </Space>
    </Card>
  );
}
