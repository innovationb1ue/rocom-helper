# Roco PvP Helper - Web Frontend

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
| `/` | Redirect | Redirects to `/battle` |
| `/battle` | BattleLive | Real-time battle monitor (WebSocket) |
| `/history` | BattleHistory | Battle report list and `.raco-report` downloads |
| `/skill-presets` | SkillPresets | Popular skill presets and pets by skill |

## Key Components

| Component | Description |
|-----------|-------------|
| `SkillPanel` | Detailed skill analysis with effectiveness breakdown |
| `OpponentSkillPanel` | Opponent skill prediction and known skill display |
| `HookAdvicePanel` | Tactical analysis advice from analysis hooks |
| `BattleTimeline` | Chronological battle event timeline |
| `BattleEventLog` | Compact battle event log |
| `BattleSummaryPanel` | End-of-battle summary statistics |
| `TeamRoster` | Active and bench pet state display |
| `TacticalPanel` | Action recommendation panel |

## State Management

Zustand stores in `src/stores/`:
- **battleStore** - Live battle state, events, suggestions, skill analysis, hook advice, traits, opponent skills, and tactical recommendations
- **snifferStore** - Packet capture session status

## WebSocket Protocol

The `BattleLive` page connects to `ws://localhost:8000/ws/battle` and receives these message types:
- `connected` - Initial connection confirmation
- `state_update` - Full battle state snapshot
- `battle_event` / `battle_events` - Formatted battle events for timeline
- `skill_analysis` - Damage predictions for equipped skills, with traits when available
- `opp_skill_analysis` - Opponent skill analysis when available
- `hook_advice` - Analysis hook recommendations
- `suggestions` - Simple rule-based suggestions
- `tactical_recommendations` - Recommended actions from tactical analysis
- `battle_summary` - End-of-battle summary

## Battle Report Downloads

The history page uses:
- `GET /api/battle/reports` to list reports
- `GET /api/battle/reports/{report_id}` to fetch report metadata
- `GET /api/battle/reports/{report_id}/download` to download `.raco-report`

`.raco-report` files contain original RC01 `.bin` packets and manifest metadata. Use `py -m scripts.unpack_battle_report <file> --verify` from the project root to import and replay them.