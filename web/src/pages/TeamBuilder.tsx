import React, { useState } from 'react';
import { Row, Col, Card, Button, Input, Space, List, Tag, Progress, Alert } from 'antd';
import { fetchPets, analyzeTeam, findCounters } from '../utils/api';
import TeamSlot from '../components/TeamSlot';
import type { TeamAnalysis, CounterResult } from '../utils/api';

const TeamBuilderPage: React.FC = () => {
  const [team, setTeam] = useState<Array<{ id: number; name: string; types?: number[] } | null>>(
    Array(6).fill(null)
  );
  const [analysis, setAnalysis] = useState<TeamAnalysis | null>(null);
  const [searchResults, setSearchResults] = useState<Array<{ id: number; name: string; types?: number[] }>>([]);
  const [selectingSlot, setSelectingSlot] = useState<number | null>(null);
  const [searchText, setSearchText] = useState('');
  const [counters, setCounters] = useState<CounterResult[]>([]);

  const searchPets = async (text: string) => {
    setSearchText(text);
    if (text.length < 1) { setSearchResults([]); return; }
    const data = await fetchPets({ name: text, limit: 10 });
    setSearchResults(data.pets);
  };

  const selectPet = (pet: { id: number; name: string; types?: number[] }) => {
    if (selectingSlot === null) return;
    const newTeam = [...team];
    newTeam[selectingSlot] = pet;
    setTeam(newTeam);
    setSelectingSlot(null);
    setSearchResults([]);
    setSearchText('');
  };

  const removePet = (idx: number) => {
    const newTeam = [...team];
    newTeam[idx] = null;
    setTeam(newTeam);
  };

  const doAnalyze = async () => {
    const ids = team.filter(Boolean).map(p => p!.id);
    if (ids.length === 0) return;
    const result = await analyzeTeam(ids);
    setAnalysis(result);
  };

  const doCounter = async () => {
    const ids = team.filter(Boolean).map(p => p!.id);
    if (ids.length === 0) return;
    const result = await findCounters(ids);
    setCounters(result.counters || []);
  };

  return (
    <div>
      <Row gutter={16}>
        <Col span={16}>
          <Card title="队伍" size="small">
            <Row gutter={[8, 8]}>
              {team.map((pet, i) => (
                <Col span={8} key={i}>
                  <TeamSlot
                    pet={pet}
                    slotIndex={i}
                    onRemove={() => removePet(i)}
                    onSelect={() => setSelectingSlot(i)}
                  />
                </Col>
              ))}
            </Row>
            <Space style={{ marginTop: 12 }}>
              <Button type="primary" onClick={doAnalyze}>分析队伍</Button>
              <Button onClick={doCounter}>反制推荐</Button>
            </Space>
          </Card>
          {selectingSlot !== null && (
            <Card title={`选择精灵 (Slot ${selectingSlot + 1})`} size="small" style={{ marginTop: 12 }}>
              <Input.Search
                placeholder="搜索精灵"
                value={searchText}
                onChange={e => searchPets(e.target.value)}
                style={{ marginBottom: 8 }}
              />
              <List
                size="small"
                dataSource={searchResults}
                renderItem={(pet) => (
                  <List.Item style={{ cursor: 'pointer' }} onClick={() => selectPet(pet)}>
                    {pet.name} (#{pet.id})
                  </List.Item>
                )}
              />
            </Card>
          )}
        </Col>
        <Col span={8}>
          {analysis && (
            <Card title={`队伍评分: ${analysis.score}`} size="small">
              <div style={{ marginBottom: 12 }}>
                <Progress percent={Math.round(analysis.score)} size="small" />
              </div>
              {analysis.suggestions.length > 0 && (
                <div>
                  <strong>建议:</strong>
                  {analysis.suggestions.map((s, i) => (
                    <Alert key={i} message={s.message} type={
                      s.type === 'shared_weakness' ? 'warning' :
                      s.type === 'weak_coverage' ? 'info' : 'success'
                    } style={{ marginBottom: 4 }} showIcon={false} />
                  ))}
                </div>
              )}
              <div style={{ marginTop: 8 }}>
                <strong>速度线:</strong>
                {analysis.speed_tier.map((s, i) => (
                  <div key={i}>{s.name}: {s.speed}</div>
                ))}
              </div>
            </Card>
          )}
          {counters.length > 0 && (
            <Card title="反制推荐" size="small" style={{ marginTop: 12 }}>
              <List
                size="small"
                dataSource={counters.slice(0, 5)}
                renderItem={(c) => (
                  <List.Item>
                    {c.name} <Tag color="blue">{c._counter_score.toFixed(1)}</Tag>
                  </List.Item>
                )}
              />
            </Card>
          )}
        </Col>
      </Row>
    </div>
  );
};

export default TeamBuilderPage;
