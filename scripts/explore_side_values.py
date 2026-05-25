"""Explore raw actor_side/target_side values in 0x1324 packets from both sessions.

This script deeply inspects the raw protocol data to understand what values
actor_side, target_side, and damage_target_side actually take, and whether
the current _is_mine() / side_name() logic correctly interprets them.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure UTF-8 output on Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.packet_reader import load_battle_packets, BATTLE_OPCODES
from src.protocol.proto_core import parse_record, field_groups, collect_varints, \
    walk_messages, pick_first, side_name as proto_side_name
from src.protocol.battle import _extract_1324_entry
from src.analysis.battle_state import BattleStateTracker


def raw_collect_varints_all(msg: Dict[str, Any], field_num: int) -> List[int]:
    """Collect ALL varints from field (including nested) - exhaustive version."""
    results = []
    groups = field_groups(msg)
    entries = groups.get(field_num, [])
    for e in entries:
        if e.get("type") == "varint":
            results.append(e["value"])
    return results


def explore_raw_msg(msg: Dict[str, Any], prefix: str = "") -> None:
    """Print the raw protobuf fields for deep inspection."""
    for k, v in sorted(msg.items()):
        if k == "sub":
            print(f"{prefix}  └── [submessage]")
            explore_raw_msg(v, prefix + "      ")
        elif k == "value":
            print(f"{prefix}  value = {v}")
        else:
            pass  # handled differently


def extract_raw_entries_from_1324(record: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract ALL 0x1324 entries, capturing raw field values as well as the normal extraction."""
    root = record.get("root", {})
    groups = field_groups(root)

    all_sub_msgs = []
    walk_messages(root, all_sub_msgs)
    all_sub_msgs = [m for m in all_sub_msgs if m != root]

    entries_raw = []
    entry_idx = 0
    for sub_msg in all_sub_msgs:
        sg = field_groups(sub_msg)
        entry_type = pick_first(collect_varints(sub_msg, 1))
        if entry_type is None:
            continue
        # Only extract if it looks like a 1324 entry (has entry_type AND actor/target fields)
        entry_idx += 1

        # Raw field values - collect ALL varints for fields 1 and 2
        raw_actor_vals = raw_collect_varints_all(sub_msg, 1)
        raw_target_vals = raw_collect_varints_all(sub_msg, 2)

        # The normal extracted entry
        extracted = _extract_1324_entry(sub_msg)

        entries_raw.append({
            "entry_idx": entry_idx,
            "entry_type": entry_type,
            "extracted": extracted,
            "raw_actor_vals": raw_actor_vals,
            "raw_target_vals": raw_target_vals,
            "sub_msg_keys": list(sg.keys()),
        })

    return entries_raw


def print_separator(title: str) -> None:
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}")


def main():
    base = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "packets"

    for session_name in ["battle_session_1", "battle_session_2"]:
        session_dir = base / session_name
        print_separator(f"SESSION: {session_name}")

        packets = load_battle_packets(session_dir)
        print(f"Loaded {len(packets)} battle packets")

        # First, track battle state to know round numbers and pet names
        tracker = BattleStateTracker()
        for item in packets:
            record = item["record"]
            opcode = item["opcode"]
            inner = None
            if opcode == 0x0414:
                from src.protocol.opcodes import extract_inner_message
                inner = extract_inner_message(record.get("root", {}))
            from src.protocol.opcodes import summarize
            _, summary = summarize(record, inner)
            detail = summary.get("detail", summary)
            if detail is None:
                detail = {}
            tracker.handle_event(opcode, detail)

        # Now, only process 0x1324 packets
        op1324_packets = [item for item in packets if item["opcode"] == 0x1324]
        print(f"Found {len(op1324_packets)} 0x1324 packets")

        # Group analysis by entry kind
        kind_pairs = defaultdict(set)  # kind -> set of (actor_side, target_side) tuples
        entry_count_by_kind = defaultdict(int)
        all_actor_values = defaultdict(int)  # value -> count
        all_target_values = defaultdict(int)
        all_damage_target_values = defaultdict(int)
        all_battle_pet_id_values = defaultdict(int)

        change_pet_entries = []  # Ground truth: (battle_pet_id, new_pet_name, actor_side, target_side)

        for pkt_idx, item in enumerate(op1324_packets):
            record = item["record"]
            state = tracker.get_state()
            round_num = state.get("round", "?")

            # Parse the record via summarize
            from src.protocol.opcodes import summarize
            _, summary = summarize(record, None)
            detail = summary.get("detail", summary) if summary else {}
            entries = detail.get("entries", [])

            if not entries:
                continue

            for entry in entries:
                kind = entry.get("kind", f"type_{entry.get('type', '?')}")
                entry_count_by_kind[kind] += 1

                actor_side = entry.get("actor_side")
                target_side = entry.get("target_side")
                damage_target_side = entry.get("damage_target_side")
                battle_pet_id = entry.get("battle_pet_id")

                if actor_side is not None:
                    all_actor_values[actor_side] += 1
                    kind_pairs[kind].add((actor_side, target_side))

                if target_side is not None:
                    all_target_values[target_side] += 1

                if damage_target_side is not None:
                    all_damage_target_values[damage_target_side] += 1

                if battle_pet_id is not None:
                    all_battle_pet_id_values[battle_pet_id] += 1

                # Collect change_pet as ground truth
                if kind == "change_pet":
                    change_pet_entries.append({
                        "round": round_num,
                        "battle_pet_id": battle_pet_id,
                        "actor_side": actor_side,
                        "target_side": target_side,
                        "new_pet_name": entry.get("new_pet_name"),
                        "new_pet_id": entry.get("new_pet_id"),
                        "rest_pet_id": entry.get("rest_pet_id"),
                        "is_cmd": entry.get("is_cmd"),
                        "actor_side_name": entry.get("actor_side_name"),
                        "target_side_name": entry.get("target_side_name"),
                    })

        # --- REPORT ---

        print(f"\n--- Entry counts by kind ---")
        for kind, count in sorted(entry_count_by_kind.items(), key=lambda x: -x[1]):
            print(f"  {kind}: {count} occurrences")
            pairs = kind_pairs.get(kind, set())
            if pairs:
                print(f"       unique (actor_side, target_side) pairs: {sorted(pairs, key=lambda x: (x[0] or 0, x[1] or 0))}")

        print(f"\n--- All unique actor_side values (across all entry kinds) ---")
        for val, count in sorted(all_actor_values.items(), key=lambda x: -x[1]):
            side_label = proto_side_name(val)
            is_mine = BattleStateTracker._is_mine(val)
            print(f"  actor_side={val} ({side_label}), is_mine={is_mine}, count={count}")

        print(f"\n--- All unique target_side values (across all entry kinds) ---")
        for val, count in sorted(all_target_values.items(), key=lambda x: -x[1]):
            side_label = proto_side_name(val)
            is_mine = BattleStateTracker._is_mine(val)
            print(f"  target_side={val} ({side_label}), is_mine={is_mine}, count={count}")

        print(f"\n--- All unique damage_target_side values ---")
        for val, count in sorted(all_damage_target_values.items(), key=lambda x: -x[1]):
            side_label = proto_side_name(val)
            is_mine = BattleStateTracker._is_mine(val)
            print(f"  damage_target_side={val} ({side_label}), is_mine={is_mine}, count={count}")

        print(f"\n--- All unique battle_pet_id values (from change_pet) ---")
        for val, count in sorted(all_battle_pet_id_values.items(), key=lambda x: -x[1]):
            side_label = proto_side_name(val)
            is_mine = BattleStateTracker._is_mine(val)
            print(f"  battle_pet_id={val} ({side_label}), is_mine={is_mine}, count={count}")

        print(f"\n--- Change pet entries (GROUND TRUTH) ---")
        for cp in change_pet_entries:
            is_opp = cp["battle_pet_id"] is not None and cp["battle_pet_id"] >= 401
            print(f"  Round {cp['round']}: "
                  f"battle_pet_id={cp['battle_pet_id']}, "
                  f"actor_side={cp['actor_side']} ({cp.get('actor_side_name', '?')}), "
                  f"target_side={cp['target_side']} ({cp.get('target_side_name', '?')}), "
                  f"new_pet={cp.get('new_pet_name', '?')} (id={cp.get('new_pet_id', '?')}), "
                  f"is_opp={is_opp}")

        # --- Now print per-round details for the first few packets ---
        print(f"\n--- Per-round entry details (first N packets) ---")
        for pkt_idx, item in enumerate(op1324_packets[:5]):
            record = item["record"]
            from src.protocol.opcodes import summarize
            _, summary = summarize(record, None)
            detail = summary.get("detail", summary) if summary else {}
            entries = detail.get("entries", [])
            round_num = detail.get("round", "?")
            print(f"\n  Packet #{pkt_idx}, Round {round_num}, {len(entries)} entries:")
            for ei, entry in enumerate(entries):
                kind = entry.get("kind", f"type_{entry.get('type', '?')}")
                actor = entry.get("actor_side", "N/A")
                target = entry.get("target_side", "N/A")
                dmg_target = entry.get("damage_target_side", "N/A")
                bp_id = entry.get("battle_pet_id", "N/A")
                print(f"    [{ei}] {kind}: actor={actor} ({entry.get('actor_side_name', '?')}), "
                      f"target={target} ({entry.get('target_side_name', '?')})"
                      + (f", dmg_target={dmg_target} ({entry.get('damage_target_side_name', '?')})" if dmg_target != "N/A" else "")
                      + (f", battle_pet_id={bp_id}" if bp_id != "N/A" else "")
                      + (f", skill={entry.get('skill_name', '')}" if entry.get('skill_name') else ""))

        # --- CHECK: Would routing be wrong? ---
        print(f"\n--- ROUTING CHECK (would _is_mine() give wrong answer?) ---")
        errors_found = False
        for pkt_idx, item in enumerate(op1324_packets):
            record = item["record"]
            from src.protocol.opcodes import summarize
            _, summary = summarize(record, None)
            detail = summary.get("detail", summary) if summary else {}
            entries = detail.get("entries", [])
            for entry in entries:
                kind = entry.get("kind", "")

                if kind == "change_pet":
                    bp_id = entry.get("battle_pet_id")
                    actor = entry.get("actor_side")
                    if bp_id is not None and actor is not None:
                        bp_is_mine = not (bp_id >= 401)  # battle_pet_id convention
                        actor_is_mine = BattleStateTracker._is_mine(actor)
                        if bp_is_mine != actor_is_mine:
                            errors_found = True
                            print(f"  *** MISMATCH: Round {detail.get('round', '?')}: "
                                  f"change_pet battle_pet_id={bp_id} (is_opp={bp_id >= 401}) "
                                  f"has actor_side={actor} (_is_mine={actor_is_mine})! "
                                  f"Pet={entry.get('new_pet_name', '?')}")

                if kind == "damage":
                    dmg_target = entry.get("damage_target_side")
                    actor = entry.get("actor_side")
                    # For damage: actor is the attacker, target is defender
                    # damage_target_side should match target_side from the skill_ref
                    skill_target = entry.get("target_side")
                    if dmg_target is not None and skill_target is not None:
                        dmg_is_mine = BattleStateTracker._is_mine(dmg_target)
                        skill_is_mine = BattleStateTracker._is_mine(skill_target)
                        if dmg_is_mine != skill_is_mine:
                            errors_found = True
                            print(f"  *** MISMATCH: Round {detail.get('round', '?')}: "
                                  f"damage: actor_side={actor}, target_side={skill_target} (is_mine={skill_is_mine}), "
                                  f"damage_target_side={dmg_target} (is_mine={dmg_is_mine})")

        if not errors_found:
            print("  No routing mismatches found!")

        # --- Dump raw field values from the first few 1324 packets for deep inspection ---
        print(f"\n--- Raw protobuf field inspection (first 2 packets) ---")
        for pkt_idx, item in enumerate(op1324_packets[:2]):
            record = item["record"]
            root = record.get("root", {})
            groups = field_groups(root)
            print(f"\n  Packet #{pkt_idx}: root has fields: {sorted(groups.keys())}")

            # Walk sub-messages to find entries
            all_subs = []
            walk_messages(root, all_subs)
            all_subs = [m for m in all_subs if m != root]

            for si, sub in enumerate(all_subs):
                sg = field_groups(sub)
                f1_vals = raw_collect_varints_all(sub, 1)
                f2_vals = raw_collect_varints_all(sub, 2)
                if f1_vals or f2_vals:
                    print(f"    Sub #{si}: fields={sorted(sg.keys())}, field1={f1_vals}, field2={f2_vals}")

    print("\n\nDone.")


if __name__ == "__main__":
    main()
