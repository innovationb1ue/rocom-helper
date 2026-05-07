import React from 'react';
import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom';
import { Layout, Menu } from 'antd';
import {
  DashboardOutlined,
  SearchOutlined,
  TeamOutlined,
  ThunderboltOutlined,
  AimOutlined,
  HistoryOutlined,
} from '@ant-design/icons';

import Dashboard from './pages/Dashboard';
import PetBrowser from './pages/PetBrowser';
import TeamBuilder from './pages/TeamBuilder';
import TypeChartPage from './pages/TypeChart';
import BattleLive from './pages/BattleLive';
import BattleHistory from './pages/BattleHistory';

const { Header, Content } = Layout;

const menuItems = [
  { key: '/', icon: <DashboardOutlined />, label: <NavLink to="/">仪表盘</NavLink> },
  { key: '/pets', icon: <SearchOutlined />, label: <NavLink to="/pets">精灵</NavLink> },
  { key: '/teams', icon: <TeamOutlined />, label: <NavLink to="/teams">队伍</NavLink> },
  { key: '/types', icon: <ThunderboltOutlined />, label: <NavLink to="/types">克制表</NavLink> },
  { key: '/battle', icon: <AimOutlined />, label: <NavLink to="/battle">实时战斗</NavLink> },
  { key: '/history', icon: <HistoryOutlined />, label: <NavLink to="/history">历史</NavLink> },
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
          <Route path="/" element={<Dashboard />} />
          <Route path="/pets" element={<PetBrowser />} />
          <Route path="/teams" element={<TeamBuilder />} />
          <Route path="/types" element={<TypeChartPage />} />
          <Route path="/battle" element={<BattleLive />} />
          <Route path="/history" element={<BattleHistory />} />
        </Routes>
      </Content>
    </Layout>
  </BrowserRouter>
);

export default App;
