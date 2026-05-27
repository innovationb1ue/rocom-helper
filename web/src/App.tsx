import React from 'react';
import { BrowserRouter, Navigate, NavLink, Route, Routes } from 'react-router-dom';
import { Layout, Menu } from 'antd';
import { AimOutlined, HistoryOutlined, StarOutlined } from '@ant-design/icons';

import BattleLive from './pages/BattleLive';
import BattleHistory from './pages/BattleHistory';
import SkillPresets from './pages/SkillPresets';

const { Header, Content } = Layout;

const menuItems = [
  { key: '/battle', icon: <AimOutlined />, label: <NavLink to="/battle">实时战斗</NavLink> },
  { key: '/skill-presets', icon: <StarOutlined />, label: <NavLink to="/skill-presets">热门技能</NavLink> },
  { key: '/history', icon: <HistoryOutlined />, label: <NavLink to="/history">历史记录</NavLink> },
];

const App: React.FC = () => (
  <BrowserRouter>
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{ display: 'flex', alignItems: 'center' }}>
        <div style={{ color: '#fff', fontWeight: 'bold', marginRight: 24, fontSize: 16 }}>
          Roco PvP Helper
        </div>
        <Menu theme="dark" mode="horizontal" items={menuItems} style={{ flex: 1 }} />
      </Header>
      <Content style={{ padding: '16px 24px', background: '#f5f5f5' }}>
        <Routes>
          <Route path="/" element={<Navigate to="/battle" replace />} />
          <Route path="/battle" element={<BattleLive />} />
          <Route path="/skill-presets" element={<SkillPresets />} />
          <Route path="/history" element={<BattleHistory />} />
          <Route path="*" element={<Navigate to="/battle" replace />} />
        </Routes>
      </Content>
    </Layout>
  </BrowserRouter>
);

export default App;
