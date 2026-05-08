"""Replay test fixture battle packets to the frontend via the replay API.

Usage:
    python -m scripts.replay_to_frontend [--delay 80] [--session battle_session_1]

Prerequisites:
    1. Backend running:  python -m src.main
    2. Frontend running: cd web && npm run dev
    3. Browser open at   http://localhost:5173/battle-live
    4. Click "连接战斗" in the frontend first
"""
from __future__ import annotations

import argparse
import sys
import urllib.request
import urllib.error
import json


API_BASE = "http://localhost:8000"


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay battle packets to frontend")
    parser.add_argument("--delay", type=int, default=80, help="Delay between packets in ms (default: 80)")
    parser.add_argument("--session", default="battle_session_1", help="Fixture session name")
    parser.add_argument("--host", default="localhost", help="Backend host")
    parser.add_argument("--port", type=int, default=8000, help="Backend port")
    args = parser.parse_args()

    url = f"http://{args.host}:{args.port}/api/battle/replay?delay_ms={args.delay}&session={args.session}"
    print(f"Replaying battle from '{args.session}' with {args.delay}ms delay...")
    print(f"POST {url}")

    try:
        req = urllib.request.Request(url, method="POST")
        with urllib.request.urlopen(req, timeout=300) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"ERROR: HTTP {e.code} — {body}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"ERROR: Cannot connect to backend — {e.reason}", file=sys.stderr)
        print("Make sure the backend is running: python -m src.main", file=sys.stderr)
        sys.exit(1)

    if data.get("status") != "ok":
        print(f"ERROR: {data.get('message', data)}", file=sys.stderr)
        sys.exit(1)

    print(f"\nReplay complete!")
    print(f"  Packets processed : {data['processed']}")
    print(f"  Formatted events  : {data.get('total_formatted_events', '?')}")
    print(f"  Battle result     : {data.get('result')}")
    print(f"  Rounds            : {data.get('rounds')}")
    print(f"  My pets           : {data.get('my_pets')}")
    print(f"  Opponent pets     : {data.get('opp_pets')}")


if __name__ == "__main__":
    main()
