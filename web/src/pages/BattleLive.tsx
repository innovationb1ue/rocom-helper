import React, { useState } from 'react';
import { Card, Row, Col, Progress, Button, Space, Tag, Typography, Alert, Badge } from 'antd';
import {
  ApiOutlined, CheckCircleOutlined, WarningOutlined,
  CloseCircleOutlined, SearchOutlined, StopOutlined,
} from '@ant-design/icons';
import { useBattle } from '../hooks/useBattle';
import { useBattleStore } from '../stores/battleStore';
import { useSnifferMonitor } from '../hooks/useSnifferMonitor';
import { useSnifferStore } from '../stores/snifferStore';
import BattleTimeline from '../components/BattleTimeline';

const statusConfig: Record<string, { color: string; icon: React.ReactNode; text: string }> = {
  idle: { color: 'default', icon: <CloseCircleOutlined />, text: '未启动' },
  listening: { color: 'processing', icon: <SearchOutlined />, text: '监听中' },
  connected: { color: 'warning', icon: <WarningOutlined />, text: '游戏已连接' },
  key_captured: { color: 'success', icon: <CheckCircleOutlined />, text: '密钥已获取' },
  disconnected: { color: 'error', icon: <CloseCircleOutlined />, text: '游戏已断开' },
};

const BattleLive: React.FC = () => {
  const { connect: connectBattle, sendEvent, resetBattle, getState } = useBattle();
  const { my_active, opp_active, round, result, events, suggestions, connected } = useBattleStore();
  const [wsStarted, setWsStarted] = useState(false);
  const [starting, setStarting] = useState(false);

  const { startMonitoring, stopMonitoring } = useSnifferMonitor();
  const sniffer = useSnifferStore();

  const startWs = () => { connectBattle(); setWsStarted(true); };

  const handleStart = async () => {
    setStarting(true);
    try {
      await startMonitoring();
    } finally {
      setStarting(false);
    }
  };

  const handleStop = async () => {
    await stopMonitoring();
  };

  const isActive = ['listening', 'connected', 'key_captured'].includes(sniffer.status);
  const sc = statusConfig[sniffer.status] || statusConfig.idle;

  const hpBar = (pet: { name: string; hp_pct: number; current_hp: number; max_hp: number; energy: number } | null, label: string) => {
    if (!pet) return <Card size="small"><em>无精灵</em></Card>;
    const pct = Math.round(pet.hp_pct * 100);
    return (
      <Card size="small" title={`${label}: ${pet.name}`}>
        <Progress percent={pct} status={pct < 25 ? 'exception' : 'active'} />
        <div>HP: {pet.current_hp}/{pet.max_hp} | 能量: {pet.energy}</div>
      </Card>
    );
  };

  return (
    <div>
      {/* 监听控制面板 */}
      <Card size="small" title="网络监听" style={{ marginBottom: 12 }}>
        <Space wrap>
          {!isActive ? (
            <Button
              type="primary"
              icon={<ApiOutlined />}
              onClick={handleStart}
              loading={starting}
            >
              开始监听
            </Button>
          ) : (
            <Button
              danger
              icon={<StopOutlined />}
              onClick={handleStop}
            >
              停止监听
            </Button>
          )}
          <Badge status={isActive ? (sc.color === 'success' ? 'success' : 'processing') : 'default'} />
          <Tag color={sc.color}>{sc.text}</Tag>
          {isActive && <span style={{ color: '#666', fontSize: 13 }}>{sniffer.message}</span>}
          {sniffer.keyHex && (
            <Tag color="blue">密钥: {sniffer.keyHex.slice(0, 16)}...</Tag>
          )}
          {isActive && <Tag>连接: {sniffer.flowCount}</Tag>}
        </Space>

        {/* 错误信息 */}
        {sniffer.status === 'idle' && sniffer.message.includes('失败') && (
          <Alert type="error" message={sniffer.message} style={{ marginTop: 8 }} showIcon closable />
        )}

        {/* 实时包流 */}
        {isActive && sniffer.recentRecords.length > 0 && (
          <div style={{ marginTop: 8, maxHeight: 120, overflow: 'auto', fontSize: 12, fontFamily: 'monospace', background: '#fafafa', padding: 8, borderRadius: 4 }}>
            {sniffer.recentRecords.slice(-10).map((r, i) => (
              <div key={i} style={{ color: r.direction === 'c2s' ? '#1890ff' : '#52c41a' }}>
                {r.captured_at ? `[${r.captured_at}] ` : ''}[{r.direction}] {r.tgcp_command_name || r._summary_kind || r.record_type || '?'} {r.opcode_hex || r.cmd_hex || ''}
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* 战斗 WebSocket 控制 */}
      <Space style={{ marginBottom: 12 }} wrap>
        {!wsStarted ? (
          <Button type="primary" onClick={startWs} disabled={sniffer.status !== 'key_captured'}>
            连接战斗
          </Button>
        ) : (
          <>
            <Tag color={connected ? 'green' : 'red'}>{connected ? '已连接' : '未连接'}</Tag>
            <Button onClick={resetBattle}>重置</Button>
            <Button onClick={getState}>获取状态</Button>
          </>
        )}
      </Space>

      {result && <Alert message={`战斗结束: ${result}`} type={result === 'WIN' ? 'success' : 'error'} style={{ marginBottom: 12 }} />}

      <Row gutter={16}>
        <Col span={12}>
          {hpBar(my_active as never, '我方')}
        </Col>
        <Col span={12}>
          {hpBar(opp_active as never, '敌方')}
        </Col>
      </Row>

      {round > 0 && <Typography.Text style={{ marginTop: 8, display: 'block' }}>回合 {round}</Typography.Text>}

      {suggestions.length > 0 && (
        <Card title="建议" size="small" style={{ marginTop: 12 }}>
          {suggestions.slice(-3).map((s, i) => (
            <Alert key={i} message={s.message} type="info" style={{ marginBottom: 4 }} showIcon={false} />
          ))}
        </Card>
      )}

      <Card title="事件时间线" size="small" style={{ marginTop: 12 }}>
        <BattleTimeline events={events as never} />
      </Card>
    </div>
  );
};

export default BattleLive;
