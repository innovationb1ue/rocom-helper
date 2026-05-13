import React, { useEffect, useState, useCallback } from 'react';
import {
  Row, Col, Card, List, Input, Button, Tag, Space, Empty, message,
  Popconfirm, Typography, Spin, Checkbox, Tooltip,
} from 'antd';
import { DeleteOutlined, SaveOutlined } from '@ant-design/icons';
import {
  fetchPopularSkills, updatePopularSkill, deletePopularSkill,
  fetchPetsWithSkills, fetchPetLearnableSkills,
  type PopularSkillPreset, type PetWithSkills, type LearnableSkill,
} from '../utils/api';

const { Search } = Input;
const { Text } = Typography;

const SkillPresets: React.FC = () => {
  // 左侧：精灵列表
  const [pets, setPets] = useState<PetWithSkills[]>([]);
  const [filteredPets, setFilteredPets] = useState<PetWithSkills[]>([]);
  const [searchText, setSearchText] = useState('');
  const [petsLoading, setPetsLoading] = useState(false);

  // 右侧：选中精灵的技能配置
  const [selectedPet, setSelectedPet] = useState<PetWithSkills | null>(null);
  const [learnableSkills, setLearnableSkills] = useState<LearnableSkill[]>([]);
  const [selectedSkillIds, setSelectedSkillIds] = useState<number[]>([]);
  const [skillsLoading, setSkillsLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  // 预设数据
  const [presets, setPresets] = useState<Record<string, PopularSkillPreset>>({});

  // 加载数据
  const loadData = useCallback(async () => {
    setPetsLoading(true);
    try {
      const [petsRes, presetsRes] = await Promise.all([
        fetchPetsWithSkills(),
        fetchPopularSkills(),
      ]);
      setPets(petsRes.pets);
      setFilteredPets(petsRes.pets);
      setPresets(presetsRes.presets || {});
    } catch {
      message.error('加载数据失败');
    } finally {
      setPetsLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  // 搜索过滤
  useEffect(() => {
    if (!searchText) {
      setFilteredPets(pets);
    } else {
      const lower = searchText.toLowerCase();
      setFilteredPets(pets.filter(p => p.name.toLowerCase().includes(lower)));
    }
  }, [searchText, pets]);

  // 选中精灵
  const handleSelectPet = useCallback(async (pet: PetWithSkills) => {
    setSelectedPet(pet);
    setSkillsLoading(true);
    try {
      const res = await fetchPetLearnableSkills(pet.base_id);
      setLearnableSkills(res.skills);
      // 加载已有预设
      const preset = presets[String(pet.base_id)];
      setSelectedSkillIds(preset?.skills || []);
    } catch {
      message.error('加载技能列表失败');
      setLearnableSkills([]);
    } finally {
      setSkillsLoading(false);
    }
  }, [presets]);

  // 切换技能选择
  const toggleSkill = (skillId: number) => {
    setSelectedSkillIds(prev => {
      if (prev.includes(skillId)) {
        return prev.filter(id => id !== skillId);
      }
      if (prev.length >= 4) {
        message.warning('最多选择 4 个技能');
        return prev;
      }
      return [...prev, skillId];
    });
  };

  // 保存预设
  const handleSave = async () => {
    if (!selectedPet) return;
    setSaving(true);
    try {
      await updatePopularSkill(selectedPet.base_id, {
        name: selectedPet.name,
        skills: selectedSkillIds,
      });
      message.success('保存成功');
      // 刷新预设数据
      const presetsRes = await fetchPopularSkills();
      setPresets(presetsRes.presets || {});
    } catch {
      message.error('保存失败');
    } finally {
      setSaving(false);
    }
  };

  // 删除预设
  const handleDelete = async () => {
    if (!selectedPet) return;
    try {
      await deletePopularSkill(selectedPet.base_id);
      message.success('已删除');
      setSelectedSkillIds([]);
      const presetsRes = await fetchPopularSkills();
      setPresets(presetsRes.presets || {});
    } catch {
      message.error('删除失败');
    }
  };

  // 获取技能来源标签
  const getSourceTag = (source: number) => {
    if (source === 1) return <Tag color="blue">升级</Tag>;
    if (source === 2) return <Tag color="green">Wiki</Tag>;
    return <Tag>其他</Tag>;
  };

  // 获取属性颜色
  const getElementColor = (element: number) => {
    const colors: Record<number, string> = {
      1: '#f5222d', 2: '#1890ff', 3: '#52c41a', 4: '#faad14',
      5: '#722ed1', 6: '#13c2c2', 7: '#eb2f96', 8: '#8c8c8c',
      9: '#fa8c16', 10: '#2f54eb', 11: '#a0d911', 12: '#fadb14',
      13: '#9254de', 14: '#36cfc9', 15: '#ff4d4f', 16: '#597ef7',
      17: '#ff85c0', 18: '#ffc53d',
    };
    return colors[element] || '#d9d9d9';
  };

  const hasPreset = selectedPet && presets[String(selectedPet.base_id)];

  return (
    <Row gutter={16} style={{ height: 'calc(100vh - 130px)' }}>
      {/* 左侧：精灵列表 */}
      <Col span={8}>
        <Card
          title="精灵列表"
          size="small"
          style={{ height: '100%' }}
          bodyStyle={{ padding: 0, height: 'calc(100% - 55px)', overflow: 'auto' }}
        >
          <div style={{ padding: '8px 12px' }}>
            <Search
              placeholder="搜索精灵名称"
              allowClear
              onChange={e => setSearchText(e.target.value)}
              style={{ marginBottom: 8 }}
            />
            <Text type="secondary" style={{ fontSize: 12 }}>
              共 {filteredPets.length} 个精灵有可学技能数据
            </Text>
          </div>
          <List
            loading={petsLoading}
            dataSource={filteredPets}
            size="small"
            renderItem={pet => {
              const preset = presets[String(pet.base_id)];
              return (
                <List.Item
                  onClick={() => handleSelectPet(pet)}
                  style={{
                    cursor: 'pointer',
                    background: selectedPet?.base_id === pet.base_id ? '#e6f7ff' : undefined,
                    padding: '6px 12px',
                  }}
                >
                  <Space>
                    <span>{pet.name}</span>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      {pet.skill_count} 技能
                    </Text>
                    {preset && <Tag color="orange">已配置</Tag>}
                  </Space>
                </List.Item>
              );
            }}
          />
        </Card>
      </Col>

      {/* 右侧：技能配置 */}
      <Col span={16}>
        <Card
          title={selectedPet ? `${selectedPet.name} — 热门技能配置` : '选择精灵'}
          size="small"
          style={{ height: '100%' }}
          bodyStyle={{ height: 'calc(100% - 55px)', overflow: 'auto' }}
          extra={selectedPet && (
            <Space>
              <Tag color="blue">已选 {selectedSkillIds.length}/4</Tag>
              {hasPreset && (
                <Popconfirm title="确认删除预设？" onConfirm={handleDelete}>
                  <Button icon={<DeleteOutlined />} size="small" danger>删除预设</Button>
                </Popconfirm>
              )}
              <Button
                type="primary"
                icon={<SaveOutlined />}
                size="small"
                loading={saving}
                onClick={handleSave}
                disabled={selectedSkillIds.length === 0}
              >
                保存
              </Button>
            </Space>
          )}
        >
          {!selectedPet ? (
            <Empty description="请从左侧选择一个精灵" />
          ) : skillsLoading ? (
            <div style={{ textAlign: 'center', padding: 40 }}><Spin /></div>
          ) : (
            <>
              <div style={{ marginBottom: 12 }}>
                <Text type="secondary">
                  选择该精灵在 PvP 中常见的技能组合（最多 4 个），
                  对手使用该精灵时会优先展示这些技能的伤害分析。
                </Text>
              </div>
              <List
                dataSource={learnableSkills}
                size="small"
                renderItem={skill => {
                  const isSelected = selectedSkillIds.includes(skill.skill_id);
                  return (
                    <List.Item
                      onClick={() => toggleSkill(skill.skill_id)}
                      style={{
                        cursor: 'pointer',
                        background: isSelected ? '#f6ffed' : undefined,
                        borderLeft: isSelected ? '3px solid #52c41a' : '3px solid transparent',
                        padding: '8px 12px',
                      }}
                    >
                      <Space>
                        <Checkbox checked={isSelected} />
                        <Tag color={getElementColor(skill.element)}>
                          {skill.name}
                        </Tag>
                        {getSourceTag(skill.source)}
                        {skill.power > 0 && (
                          <Text type="secondary" style={{ fontSize: 12 }}>
                            威力 {skill.power}
                          </Text>
                        )}
                        {skill.energy_cost > 0 && (
                          <Text type="secondary" style={{ fontSize: 12 }}>
                            能耗 {skill.energy_cost}
                          </Text>
                        )}
                        {skill.desc && (
                          <Tooltip title={skill.desc}>
                            <Text type="secondary" ellipsis style={{ maxWidth: 300, fontSize: 12 }}>
                              {skill.desc}
                            </Text>
                          </Tooltip>
                        )}
                      </Space>
                    </List.Item>
                  );
                }}
              />
            </>
          )}
        </Card>
      </Col>
    </Row>
  );
};

export default SkillPresets;
