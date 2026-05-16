import React, { useState, useEffect, useRef } from 'react';
import { Card, Row, Col, Button, Space, Tag, Alert, Badge } from 'antd';
import {
  ApiOutlined, CheckCircleOutlined, WarningOutlined,
  CloseCircleOutlined, SearchOutlined, StopOutlined,
} from '@ant-design/icons';
import { useBattle } from '../hooks/useBattle';
import { useBattleStore } from '../stores/battleStore';
import { useSnifferMonitor } from '../hooks/useSnifferMonitor';
import { useSnifferStore } from '../stores/snifferStore';
import TeamRoster from '../components/TeamRoster';
import BattleEventLog from '../components/BattleEventLog';
import BattleSummaryPanel from '../components/BattleSummaryPanel';
import SkillPanel from '../components/SkillPanel';
import OpponentSkillPanel from '../components/OpponentSkillPanel';
import HookAdvicePanel from '../components/HookAdvicePanel';

const statusConfig: Record<string, { color: string; icon: React.ReactNode; text: string }> = {
  idle: { color: 'default', icon: <CloseCircleOutlined />, text: '未启动' },
  listening: { color: 'processing', icon: <SearchOutlined />, text: '监听中' },
  connected: { color: 'warning', icon: <WarningOutlined />, text: '游戏已连接' },
  key_captured: { color: 'success', icon: <CheckCircleOutlined />, text: '密钥已获取' },
  disconnected: { color: 'error', icon: <CloseCircleOutlined />, text: '游戏已断开' },
};

const BattleLive: React.FC = () => {
  const { connect: connectBattle, resetBattle, getState } = useBattle();
  const {
    my_pets, opp_pets, my_active, opp_active,
    round, result, suggestions, connected,
    formattedEvents, battleSummary, skillAnalysis, traits, oppTraits,
    hookAdvice, oppSkillAnalysis, oppSkillSource,
  } = useBattleStore();
  const [wsStarted, setWsStarted] = useState(false);
  const [starting, setStarting] = useState(false);

  const { startMonitoring, stopMonitoring, connectWs } = useSnifferMonitor();
  const sniffer = useSnifferStore();

  const autoConnectedRef = useRef(false);

  useEffect(() => {
    if (autoConnectedRef.current) return;
    autoConnectedRef.current = true;
    connectWs();
    connectBattle();
    setWsStarted(true);
  }, []);

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

        {sniffer.status === 'idle' && sniffer.message.includes('失败') && (
          <Alert type="error" title={sniffer.message} style={{ marginTop: 8 }} showIcon closable />
        )}

        {isActive && sniffer.recentRecords.length > 0 && (
          <div style={{ marginTop: 8, maxHeight: 120, overflow: 'auto', fontSize: 12, fontFamily: 'monospace', background: '#fafafa', padding: 8, borderRadius: 4 }}>
            {sniffer.recentRecords.slice(-80).map((r, i) => (
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
          <Button type="primary" onClick={startWs}>
            连接战斗
          </Button>
        ) : (
          <>
            <Tag color={connected ? 'green' : 'red'}>{connected ? '已连接' : '未连接'}</Tag>
            <Button onClick={resetBattle}>重置</Button>
            <Button onClick={getState}>获取状态</Button>
          </>
        )}
        {round > 0 && <Tag color="blue">回合 {round}</Tag>}
      </Space>

      {result && <Alert title={`战斗结束: ${result}`} type={result === 'WIN' ? 'success' : 'error'} style={{ marginBottom: 12 }} />}

      {/* 双方阵容 */}
      <Row gutter={16} style={{ marginBottom: 12 }}>
        <Col span={12}>
          <TeamRoster pets={my_pets} activePet={my_active} side="my" label="我方阵容" />
        </Col>
        <Col span={12}>
          <TeamRoster pets={opp_pets} activePet={opp_active} side="opp" label="敌方阵容" />
        </Col>
      </Row>

      {/* 技能分析面板 */}
      <SkillPanel skills={skillAnalysis} oppActive={opp_active} traits={traits} />

      {/* 对手技能分析面板 */}
      <OpponentSkillPanel
        skills={oppSkillAnalysis}
        source={oppSkillSource}
        myActive={my_active}
        oppName={opp_active?.name}
      />

      {/* 对手特性 */}
      {oppTraits && oppTraits.length > 0 && (
        <Card
          title={`${opp_active?.name || '对方精灵'} 特性`}
          size="small"
          style={{ marginBottom: 12 }}
          styles={{ body: { padding: '8px 12px' } }}
        >
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
            {oppTraits.map((t) => (
              <Tag key={t.name} color="orange" style={{ fontSize: 11, margin: 0 }}>
                {t.name}
              </Tag>
            ))}
          </div>
        </Card>
      )}

      {/* 建议 */}
      {suggestions.length > 0 && (
        <Card title="建议" size="small" style={{ marginBottom: 12 }}>
          {suggestions.slice(-3).map((s, i) => (
            <Alert key={i} title={s.message} type="info" style={{ marginBottom: 4 }} showIcon={false} />
          ))}
        </Card>
      )}

      {/* 钩子战术分析 */}
      <HookAdvicePanel advice={hookAdvice} />

      {/* 战斗总结 */}
      <BattleSummaryPanel summary={battleSummary} />

      {/* 事件日志 */}
      <Card title="战斗事件" size="small" style={{ marginTop: 12 }}>
        <BattleEventLog events={formattedEvents} />
      </Card>
    </div>
  );
};

export default BattleLive;
