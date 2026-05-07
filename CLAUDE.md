# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Roco PvP Helper (洛克王国 PvP 辅助工具) — a passive network-monitoring assistant for Roco Kingdom PvP battles. It captures game traffic on port 8195, decrypts the custom BE21 protocol, and provides real-time battle state tracking, team analysis, and type counter-pick suggestions. The tool is purely passive — it only reads traffic, never sends packets to the game.

## Tech Stack

- **Backend**: Python 3.11+, FastAPI, Scapy, PyCryptodome, uvicorn
- **Frontend**: React 19, TypeScript, Ant Design 6, Zustand, Vite 8, React Router 7
- **Protocol**: Custom BE21 binary framing with AES-128-CBC encryption, protobuf-like message payloads

## Commands

### Backend
```bash
python -m src.main              # Start FastAPI server on :8000 (with hot reload)
pytest                          # Run all tests
pytest tests/test_crypto.py     # Run a single test file
pytest -k "test_name"           # Run tests matching a name pattern
```

### Frontend (from `web/`)
```bash
npm run dev                     # Vite dev server on :5173
npm run build                   # TypeScript compile + Vite production build
npm run lint                    # ESLint
```

## Architecture

The system is a layered pipeline with clear boundaries between capture, parsing, analysis, and presentation:

```
Network Traffic (port 8195)
  │
  ▼
capture/sniffer.py ── Scapy AsyncSniffer, orchestrates the pipeline
  │
  ├── capture/key_capture.py ── Extract AES session key from ACK packets
  ├── capture/reassembly.py ── TCP stream reassembly into ordered flows
  ├── capture/frame.py ── BE21 frame parsing (header + body extraction)
  ├── capture/crypto.py ── AES-128-CBC decryption of encrypted bodies
  │
  ▼
protocol/
  ├── proto_core.py ── Protobuf-like record/field parsing primitives
  ├── opcodes.py ── Opcode registry and message dispatch
  ├── battle.py ── Battle-specific opcode handlers
  │
  ▼
analysis/
  ├── battle_state.py ── Real-time battle state machine (HP, energy, buffs, turn tracking)
  ├── coverage.py ── Offensive/defensive type coverage calculation
  ├── counter.py ── Counter-pick logic based on type matchups
  ├── threat.py ── Threat assessment for opponent pets
  ├── team_builder.py ── Team composition suggestions
  │
  ▼
api/ (FastAPI)
  ├── routes_battle.py ── WebSocket endpoint (/ws/battle) for live battle
  ├── routes_sniffer.py ── Packet capture control API
  ├── routes_teams.py ── Team analysis endpoints
  ├── routes_pets.py ── Pet data queries
  ├── routes_data.py ── Static game data serving
  │
  ▼
web/ (React SPA)
  ├── stores/ ── Zustand stores (battleStore, petsStore)
  ├── hooks/ ── useBattle (WebSocket), usePets (REST)
  ├── pages/ ── Dashboard, PetBrowser, TeamBuilder, TypeChart, BattleLive, BattleHistory
  ├── components/ ── PetCard, TeamSlot, TypeBadge, BattleTimeline, CoverageRadar
```

### Data Files

Static game data lives in `data/game/` as JSON files. Key files:
- `pet_map.json`, `skill_map.json`, `pet_skill_map.json` — pet/skill databases
- `type_chart.json` — 18-type effectiveness matrix
- `proto_schema.json`, `opcode_pb_map.json` — protocol schema definitions
- `monster_map.json` — in-game monster ID mapping

The `src/data/loader.py` module provides typed access to this data; `src/data/scraper.py` and `src/data/updater.py` handle scraping from game wikis.

### Key Design Patterns

- **Backend entry point**: `src/main.py` runs uvicorn with `src.api.app:app` (factory pattern via `create_app()`)
- **Route registration**: All routers are mounted in `app.py` with `/api` prefix (except battle WebSocket at root)
- **CORS**: Allowed origins are `localhost:5173` and `127.0.0.1:5173` (Vite dev server)
- **State management**: Zustand stores on frontend; WebSocket for battle state, REST for pet/team data
- **API client**: `web/src/utils/api.ts` centralizes Axios calls to the backend

## Testing

Tests live in `tests/` and mirror the module structure (`test_crypto.py` tests `capture/crypto.py`, etc.). Test fixtures are in `tests/fixtures/`. The test suite covers crypto, protocol parsing, game mechanics (type chart, stats, skill eval), battle state tracking, and API endpoints.

## Language Notes

The codebase uses Chinese for UI strings, comments, and docstrings. Game data files use Chinese field names. Preserve this convention when modifying UI or data-related code.
