"""战斗包提取工具 — 从抓包会话中识别战斗边界，提取战斗相关包到测试 fixtures。

用法:
    py -m scripts.extract_battle --session 2026-05-16_20-12-54_monitor          # 列出战斗
    py -m scripts.extract_battle --session battle_session_3                      # 也支持 fixture 名称
    py -m scripts.extract_battle --session <id> --extract 1                     # 提取第 1 场战斗
    py -m scripts.extract_battle --session <id> --extract all                   # 提取所有战斗
    py -m scripts.extract_battle --session <id> --extract 1 --verify            # 提取并验证
    py -m scripts.extract_battle --session <id> --extract 1 --pad-before 10     # 自定义前填充
"""
from __future__ import annotations

import argparse
import json
import shutil
import struct
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.analysis.constants import OPCODE_BATTLE_ENTER, OPCODE_BATTLE_FINISH

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_LOGS_PACKET_DIR = _PROJECT_ROOT / "logs" / "packets"
_FIXTURES_DIR = _PROJECT_ROOT / "tests" / "fixtures" / "packets"

# 只有 cmd=0x4013 的包才可能有战斗 opcode
_DATA_CMD_PATTERN = "*_0x4013_*.bin"


# ---------------------------------------------------------------------------
# Lightweight metadata reader (no proto_core/opcodes imports)
# ---------------------------------------------------------------------------

def _read_metadata(filepath: Path) -> Optional[Dict[str, Any]]:
    """Read the trailing JSON metadata from an RC01 .bin file.

    Must parse sequentially since decrypted_body length is variable.
    Files are small (~hundreds of bytes), so this is fast.
    """
    try:
        with open(filepath, "rb") as f:
            magic = f.read(4)
            if magic != b"RC01":
                return None
            f.read(2)   # cmd
            f.read(4)   # seq
            f.read(4)   # direction
            hdr_extra_len = struct.unpack(">I", f.read(4))[0]
            f.read(hdr_extra_len)
            body_len = struct.unpack(">I", f.read(4))[0]
            f.read(body_len)
            decrypted_len = struct.unpack(">I", f.read(4))[0]
            if decrypted_len > 0:
                f.read(decrypted_len)
            meta_len = struct.unpack(">I", f.read(4))[0]
            if meta_len == 0 or meta_len > 1_000_000:
                return None
            return json.loads(f.read(meta_len))
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Timestamp helpers
# ---------------------------------------------------------------------------

def _extract_timestamp(filename: str) -> str:
    """Extract 'HHMMSS.mmm' from filename."""
    parts = filename.rsplit("_", 1)
    if len(parts) == 2:
        return parts[1].replace(".bin", "")
    return ""


def _ts_to_seconds(ts: str) -> float:
    """Convert 'HHMMSS.mmm' to seconds since midnight."""
    ts = ts.strip()
    h = int(ts[0:2])
    m = int(ts[2:4])
    s = float(ts[4:])
    return h * 3600 + m * 60 + s


def _seconds_to_display(seconds: float) -> str:
    h = int(seconds) // 3600
    m = (int(seconds) % 3600) // 60
    s = int(seconds) % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


# ---------------------------------------------------------------------------
# Session resolution
# ---------------------------------------------------------------------------

def _resolve_session(session_arg: str) -> Path:
    """Resolve session identifier to directory path.

    Tries: literal path → fixtures dir → logs dir.
    """
    # 1. Literal path
    p = Path(session_arg)
    if p.is_dir():
        return p

    # 2. Fixtures
    p = _FIXTURES_DIR / session_arg
    if p.is_dir():
        return p

    # 3. Logs
    p = _LOGS_PACKET_DIR / session_arg
    if p.is_dir():
        return p

    print(f"Session not found: {session_arg}", file=sys.stderr)
    print(f"  Tried: {session_arg}", file=sys.stderr)
    print(f"         {_FIXTURES_DIR / session_arg}", file=sys.stderr)
    print(f"         {_LOGS_PACKET_DIR / session_arg}", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Boundary detection
# ---------------------------------------------------------------------------

@dataclass
class BattleBoundary:
    index: int
    enter_file: str
    finish_file: str
    enter_ts: str          # HH:MM:SS.mmm
    finish_ts: str
    enter_seconds: float
    finish_seconds: float
    incomplete: bool = False

    @property
    def duration(self) -> float:
        return self.finish_seconds - self.enter_seconds


def _parse_opcode_hex(meta: Dict[str, Any]) -> Optional[int]:
    """Parse opcode_hex from metadata, return as int or None."""
    hex_str = meta.get("opcode_hex")
    if not hex_str:
        return None
    try:
        return int(hex_str, 16)
    except ValueError:
        return None


def scan_battles(session_dir: Path) -> List[BattleBoundary]:
    """Scan session for battle boundaries (0x1316 / 0x132C pairs)."""
    # Only 0x4013 packets can have battle opcodes
    candidates = sorted(
        session_dir.glob(_DATA_CMD_PATTERN),
        key=lambda p: _extract_timestamp(p.name),
    )

    # Read metadata, find enter/finish opcodes
    enters: List[tuple] = []   # (filename, ts_str, seconds, meta)
    finishes: List[tuple] = []

    for fpath in candidates:
        meta = _read_metadata(fpath)
        if not meta:
            continue
        opcode = _parse_opcode_hex(meta)
        if opcode is None:
            continue

        ts_raw = _extract_timestamp(fpath.name)
        ts_display = meta.get("ts", ts_raw)
        ts_seconds = _ts_to_seconds(ts_raw)

        if opcode == OPCODE_BATTLE_ENTER:
            enters.append((fpath.name, ts_display, ts_seconds, meta))
        elif opcode == OPCODE_BATTLE_FINISH:
            finishes.append((fpath.name, ts_display, ts_seconds, meta))

    # Pair them up
    boundaries: List[BattleBoundary] = []

    if not enters:
        return boundaries

    # Match first enter with first finish that comes after it, etc.
    finish_idx = 0
    for i, (enter_file, enter_ts, enter_sec, _) in enumerate(enters):
        # Find the next finish after this enter
        paired = False
        while finish_idx < len(finishes):
            fin_file, fin_ts, fin_sec, _ = finishes[finish_idx]
            if fin_sec >= enter_sec:
                boundaries.append(BattleBoundary(
                    index=i + 1,
                    enter_file=enter_file,
                    finish_file=fin_file,
                    enter_ts=enter_ts,
                    finish_ts=fin_ts,
                    enter_seconds=enter_sec,
                    finish_seconds=fin_sec,
                ))
                finish_idx += 1
                paired = True
                break
            finish_idx += 1

        if not paired:
            # Unpaired enter — use last packet time as end
            last_ts = _extract_timestamp(candidates[-1].name)
            last_meta = _read_metadata(candidates[-1])
            last_display = last_meta.get("ts", last_ts) if last_meta else last_ts
            boundaries.append(BattleBoundary(
                index=i + 1,
                enter_file=enter_file,
                finish_file=candidates[-1].name,
                enter_ts=enter_ts,
                finish_ts=last_display,
                enter_seconds=enter_sec,
                finish_seconds=_ts_to_seconds(last_ts),
                incomplete=True,
            ))

    return boundaries


# ---------------------------------------------------------------------------
# Listing
# ---------------------------------------------------------------------------

def list_battles(session_dir: Path, boundaries: List[BattleBoundary]) -> None:
    """Print battle boundaries found in a session."""
    total_bins = sum(1 for _ in session_dir.glob("*.bin"))
    session_meta_path = session_dir / "_session.json"
    session_id = session_dir.name
    if session_meta_path.exists():
        try:
            session_id = json.loads(session_meta_path.read_text("utf-8")).get("session_id", session_id)
        except Exception:
            pass

    print(f"Session: {session_id}")
    print(f"Path:    {session_dir}")
    print(f"Files:   {total_bins} .bin")
    print()

    if not boundaries:
        print("No battles found in this session.")
        return

    for b in boundaries:
        incomplete = " (INCOMPLETE — no battle_finish)" if b.incomplete else ""
        print(f"── Battle #{b.index} ──{incomplete}")
        print(f"  Enter:  {b.enter_ts}  ({b.enter_file})")
        print(f"  Finish: {b.finish_ts}  ({b.finish_file})")
        print(f"  Duration: ~{b.duration:.0f}s")
        print()
        print(f"  Extract:  py -m scripts.extract_battle --session {session_dir.name} --extract {b.index}")
        if len(boundaries) > 1:
            print(f"  Extract all: py -m scripts.extract_battle --session {session_dir.name} --extract all")


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------

def _next_session_number() -> int:
    """Find next available battle_session_N number."""
    if not _FIXTURES_DIR.exists():
        return 1
    max_n = 0
    for d in _FIXTURES_DIR.iterdir():
        if d.is_dir() and d.name.startswith("battle_session_"):
            try:
                n = int(d.name.split("_")[-1])
                max_n = max(max_n, n)
            except ValueError:
                pass
    return max_n + 1


def extract_battle(
    session_dir: Path,
    boundary: BattleBoundary,
    *,
    pad_before: float = 5.0,
    pad_after: float = 2.0,
    output_name: Optional[str] = None,
) -> Path:
    """Extract a single battle into test fixtures. Returns output directory."""
    window_start = boundary.enter_seconds - pad_before
    window_end = boundary.finish_seconds + pad_after

    # Select all .bin files in time window
    all_bins = sorted(session_dir.glob("*.bin"), key=lambda p: _extract_timestamp(p.name))
    selected: List[Path] = []
    for fpath in all_bins:
        ts = _ts_to_seconds(_extract_timestamp(fpath.name))
        if window_start <= ts <= window_end:
            selected.append(fpath)

    if not selected:
        print("ERROR: No files found in time window!", file=sys.stderr)
        sys.exit(1)

    # Create output directory
    if output_name:
        out_name = output_name
    else:
        out_name = f"battle_session_{_next_session_number()}"
    out_dir = _FIXTURES_DIR / out_name
    out_dir.mkdir(parents=True, exist_ok=True)

    # Copy files
    for fpath in selected:
        shutil.copy2(fpath, out_dir / fpath.name)

    # Write _session.json with enriched metadata
    meta = {
        "session_start": datetime.now().isoformat(),
        "session_id": out_name,
        "source_session": session_dir.name,
        "source_path": str(session_dir.relative_to(_PROJECT_ROOT)),
        "battle_index": boundary.index,
        "enter_file": boundary.enter_file,
        "finish_file": boundary.finish_file,
        "enter_ts": boundary.enter_ts,
        "finish_ts": boundary.finish_ts,
        "pad_before": pad_before,
        "pad_after": pad_after,
        "file_count": len(selected),
    }
    (out_dir / "_session.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return out_dir


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

def _filter_packets_by_window(
    packets: List[Dict[str, Any]],
    window_start: float,
    window_end: float,
) -> List[Dict[str, Any]]:
    """Filter loaded battle packets to those within a time window."""
    filtered = []
    for pkt in packets:
        ts = _ts_to_seconds(_extract_timestamp(pkt["filename"]))
        if window_start <= ts <= window_end:
            filtered.append(pkt)
    return filtered


def verify_extraction(
    source_dir: Path,
    extracted_dir: Path,
    boundary: BattleBoundary,
    pad_before: float,
    pad_after: float,
) -> bool:
    """Compare replay results between source (filtered) and extracted."""
    from tests.packet_reader import load_battle_packets
    from src.analysis.replay_runner import BattleReplayRunner

    window_start = boundary.enter_seconds - pad_before
    window_end = boundary.finish_seconds + pad_after

    print("Loading source packets...")
    source_packets = load_battle_packets(source_dir)
    source_filtered = _filter_packets_by_window(source_packets, window_start, window_end)
    print(f"  Source: {len(source_packets)} total, {len(source_filtered)} in window")

    print("Loading extracted packets...")
    extracted_packets = load_battle_packets(extracted_dir)
    print(f"  Extracted: {len(extracted_packets)} total")

    if len(source_filtered) != len(extracted_packets):
        print(f"\nFAIL: Packet count mismatch: source={len(source_filtered)}, extracted={len(extracted_packets)}")
        return False

    print("Running replay on source (filtered)...")
    runner = BattleReplayRunner()
    source_result = runner.run(source_filtered)

    print("Running replay on extracted...")
    runner2 = BattleReplayRunner()
    extracted_result = runner2.run(extracted_packets)

    # Compare
    checks = []

    def _check(name: str, a: Any, b: Any) -> None:
        ok = a == b
        status = "OK" if ok else "MISMATCH"
        print(f"  {name}: {status}" + (f"  (source={a}, extracted={b})" if not ok else f"  ({a})"))
        checks.append(ok)

    print("\nComparing replay results:")
    _check("total_packets", source_result.total_packets, extracted_result.total_packets)
    _check("rounds count", len(source_result.rounds), len(extracted_result.rounds))
    _check("final round", source_result.final_state.get("round"), extracted_result.final_state.get("round"))
    _check("final result", source_result.final_state.get("result"), extracted_result.final_state.get("result"))
    _check("battle_summary result", source_result.battle_summary.get("result"), extracted_result.battle_summary.get("result"))
    _check("my_pets count", len(source_result.final_state.get("my_pets", [])), len(extracted_result.final_state.get("my_pets", [])))
    _check("opp_pets count", len(source_result.final_state.get("opp_pets", [])), len(extracted_result.final_state.get("opp_pets", [])))

    all_ok = all(checks)
    print(f"\nResult: {'PASS' if all_ok else 'FAIL'}")
    return all_ok


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Extract battle packets from captured sessions into test fixtures",
    )
    parser.add_argument("--session", required=True,
        help="Session ID (e.g. '2026-05-16_20-12-54_monitor') or fixture name (e.g. 'battle_session_3')")
    parser.add_argument("--extract", nargs="?", const="list", default=None,
        help="Battle number (1-based) or 'all'. Omit to list battles only.")
    parser.add_argument("--verify", action="store_true",
        help="Verify extraction by comparing replay results")
    parser.add_argument("--pad-before", type=float, default=5.0,
        help="Seconds of padding before battle start (default: 5)")
    parser.add_argument("--pad-after", type=float, default=2.0,
        help="Seconds of padding after battle finish (default: 2)")
    parser.add_argument("--output", type=str, default=None,
        help="Output directory name (default: auto battle_session_N)")

    args = parser.parse_args()
    session_dir = _resolve_session(args.session)
    boundaries = scan_battles(session_dir)

    # --- LIST mode ---
    if args.extract is None:
        list_battles(session_dir, boundaries)
        return

    if not boundaries:
        print("No battles found to extract.", file=sys.stderr)
        sys.exit(1)

    # --- EXTRACT mode ---
    extract_indices: List[int] = []
    if args.extract == "all":
        extract_indices = [b.index for b in boundaries]
    else:
        try:
            n = int(args.extract)
            if n < 1 or n > len(boundaries):
                print(f"Invalid battle number: {n}. Found {len(boundaries)} battle(s).", file=sys.stderr)
                sys.exit(1)
            extract_indices = [n]
        except ValueError:
            print(f"Invalid --extract value: {args.extract!r}. Use a number or 'all'.", file=sys.stderr)
            sys.exit(1)

    for idx in extract_indices:
        boundary = boundaries[idx - 1]
        print(f"\nExtracting battle #{idx}...")
        print(f"  Window: {_seconds_to_display(boundary.enter_seconds - args.pad_before)}"
              f" — {_seconds_to_display(boundary.finish_seconds + args.pad_after)}"
              f" (pad: {args.pad_before}s before, {args.pad_after}s after)")

        out_name = args.output if args.output and len(extract_indices) == 1 else None
        out_dir = extract_battle(
            session_dir, boundary,
            pad_before=args.pad_before,
            pad_after=args.pad_after,
            output_name=out_name,
        )
        print(f"  Output: {out_dir}")

        if args.verify:
            print()
            ok = verify_extraction(
                session_dir, out_dir, boundary,
                pad_before=args.pad_before,
                pad_after=args.pad_after,
            )
            if not ok:
                sys.exit(1)

    print("\nDone.")


if __name__ == "__main__":
    main()
