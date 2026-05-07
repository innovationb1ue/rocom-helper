# Phase 4 报告：FastAPI 后端 + React 前端

## 概述

Phase 4 完成了 FastAPI 后端（4 个路由模块 + WebSocket）和 React 前端（6 个页面 + 5 个组件）。

## 后端 API

### 应用入口

- `src/main.py` — uvicorn 启动入口
- `src/api/app.py` — FastAPI 应用工厂，CORS 配置

### 路由模块

#### routes_pets.py — 精灵/技能/属性

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/pets` | GET | 精灵列表（name/type_id 过滤，分页） |
| `/api/pets/{id}` | GET | 精灵详情 |
| `/api/skills` | GET | 技能列表（type_id 过滤，分页） |
| `/api/skills/{id}` | GET | 技能详情 |
| `/api/types` | GET | 21 种属性列表 |
| `/api/types/{id}/matchups` | GET | 属性克制/抗性/免疫 |

#### routes_teams.py — 队伍分析

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/teams/analyze` | POST | 队伍综合分析（评分+覆盖+角色+建议） |
| `/api/teams/counter` | POST | 反制推荐 |
| `/api/teams/suggest` | POST | 队友推荐 |
| `/api/teams/coverage` | POST | 属性覆盖度报告 |

#### routes_battle.py — 实时战斗

| 端点 | 方法 | 说明 |
|------|------|------|
| `/ws/battle` | WebSocket | 实时战斗事件流 |

消息类型:
- 客户端→服务端: `event`(opcode+detail), `get_state`, `reset`, `request_counter_pick`
- 服务端→客户端: `state_update`, `suggestions`, `state`, `counter_pick`, `reset`, `connected`

#### routes_data.py — 数据管理

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/data/status` | GET | 数据版本和统计 |
| `/api/data/refresh` | POST | 重新加载数据 |

## React 前端

### 技术栈
- React 19 + TypeScript + Vite 8
- Ant Design 5 + @ant-design/icons
- Zustand 状态管理
- React Router 7
- Axios HTTP 客户端

### 页面

| 页面 | 文件 | 功能 |
|------|------|------|
| 仪表盘 | `Dashboard.tsx` | 数据统计概览 |
| 精灵浏览器 | `PetBrowser.tsx` | 搜索/浏览精灵，查看详情 |
| 队伍构建 | `TeamBuilder.tsx` | 6 格队伍选择+分析+反制推荐 |
| 克制表 | `TypeChart.tsx` | 21×21 属性克制矩阵表格 |
| 实时战斗 | `BattleLive.tsx` | WebSocket 实时战斗追踪 |
| 战斗历史 | `BattleHistory.tsx` | 历史战斗记录 |

### 组件

| 组件 | 说明 |
|------|------|
| `TypeBadge` | 属性标签（颜色+名称） |
| `PetCard` | 精灵卡片 |
| `TeamSlot` | 队伍格子（选择/移除精灵） |
| `BattleTimeline` | 战斗事件时间线 |
| `CoverageRadar` | 属性覆盖度可视化 |

### 状态管理

| Store | 说明 |
|-------|------|
| `petsStore` | 精灵列表、搜索、分页 |
| `battleStore` | 战斗状态（HP/能量/事件） |

### 前端构建

```
dist/index.html              0.45 kB
dist/assets/index.css        1.78 kB
dist/assets/index.js      1,058 kB (339 kB gzipped)
```

## 测试结果

### API 测试 (test_api.py)

```
16 passed in 1.46s
```

| 测试类 | 测试数 | 说明 |
|--------|--------|------|
| TestHealth | 1 | 健康检查 |
| TestPets | 4 | 精灵列表、分页、详情、404 |
| TestSkills | 2 | 技能列表、分页 |
| TestTypes | 3 | 属性列表、克制关系、404 |
| TestTeams | 3 | 队伍分析、覆盖度、反制推荐 |
| TestDataRoutes | 2 | 数据状态、刷新 |
| TestWebSocket | 1 | WebSocket 连接+事件+重置 |

### 全部测试

```
193 passed in 9.42s
```

## 启动方式

```bash
# 后端
cd D:\raco-helper
python -m src.main
# 或
uvicorn src.api.app:app --reload --port 8000

# 前端
cd D:\raco-helper\web
npm run dev
```

前端访问 http://localhost:5173，API 文档 http://localhost:8000/docs
