# Roco PvP Helper — Web Frontend

React single-page application for the Roco PvP Helper real-time battle analysis tool.

## Tech Stack

- React 19 + TypeScript
- Ant Design 6 (UI components)
- Zustand (state management)
- React Router 7 (routing)
- Vite 8 (build tool)
- Axios (HTTP client)

## Development

```bash
npm install
npm run dev         # Start dev server on http://localhost:5173
npm run build       # TypeScript check + production build
npm run lint        # ESLint
```

The frontend expects the backend running on `http://localhost:8000`.

## Pages

| Route | Page | Description |
|-------|------|-------------|
| `/` | Dashboard | Overview with stats and quick links |
| `/pets` | PetBrowser | Browse and search pet database |
| `/teams` | TeamBuilder | Build and analyze team compositions |
| `/type-chart` | TypeChart | Interactive type effectiveness chart |
| `/battle-live` | BattleLive | Real-time battle monitor (WebSocket) |
| `/battle-history` | BattleHistory | Battle replay history |

## Key Components

| Component | Description |
|-----------|-------------|
| `DamagePredictionPanel` | Damage predictions for all equipped skills, including combo hit counts and KO calculations |
| `SkillPanel` | Detailed skill analysis with effectiveness breakdown |
| `HookAdvicePanel` | Tactical analysis advice from analysis hooks (opponent tracking, energy monitoring, switch recommendations) |
| `BattleTimeline` | Chronological battle event timeline |
| `BattleSummaryPanel` | End-of-battle summary statistics |
| `CoverageRadar` | Team type coverage visualization |

## State Management

Zustand stores in `src/stores/`:
- **battleStore** — Live battle state (pets, HP, energy, skills, damage predictions, hook advice, traits)
- **petsStore** — Pet database browsing
- **snifferStore** — Packet capture session status

## WebSocket Protocol

The `BattleLive` page connects to `ws://localhost:8000/ws/battle` and receives these message types:
- `state_update` — Full battle state snapshot
- `battle_event` / `battle_events` — Formatted battle events for timeline
- `skill_analysis` — Damage predictions for equipped skills (with traits)
- `hook_advice` — Analysis hook recommendations
- `suggestions` — Simple rule-based suggestions
- `battle_summary` — End-of-battle summary
