"""Debug: verify pet names by base_conf_id."""
import sys
sys.path.insert(0, "src")

from pathlib import Path
from tests.packet_reader import load_battle_packets, replay_battle
from src.analysis.battle_state import BattleStateTracker
from src.protocol.opcodes import summarize
from src.analysis.pet_identity import battle_uid
from src.data.loader import get_pet_name

# Check pet names by base_conf_id
conf_ids = [3177, 3412, 3063, 3510, 3743, 3737, 3489, 3709]
print("Pet names by base_conf_id:")
for cid in conf_ids:
    try:
        name = get_pet_name(cid)
        print(f"  base_conf_id={cid}: {name}")
    except:
        print(f"  base_conf_id={cid}: ?")

print()
# Now trace the session
SESSION_DIR = Path("tests/fixtures/packets/battle_session_8")
packets = load_battle_packets(SESSION_DIR)

tracker = BattleStateTracker()

# Get the battle_enter packet
for p in packets:
    if p["opcode"] == 0x1316:
        record = p["record"]
        inner = None
        kind, summary = summarize(record, inner)
        detail = summary.get("detail", summary)
        tracker.handle_event(0x1316, detail)
        print("=== After BATTLE ENTER ===")
        for pet in tracker.state["opp_pets"]:
            cid = pet.get("base_conf_id")
            name = get_pet_name(cid) if cid else "?"
            print(f"  pet_id={pet.get('pet_id')} slot={pet.get('slot')} battle_uid={pet.get('battle_uid')} base_conf_id={cid} name={name}")
        print(f"opp_active: pet_id={tracker.state['opp_active'].get('pet_id')} base_conf_id={tracker.state['opp_active'].get('base_conf_id')}")
        break

# Get the R1 change_pet packet
for p in packets:
    if p["opcode"] == 0x1324 and p["filename"] == "s2c_0x4013_15489_101843.825.bin":
        record = p["record"]
        inner = None
        kind, summary = summarize(record, inner)
        detail = summary.get("detail", summary)
        entries = detail.get("entries", [])
        for e in entries:
            if e.get("kind") == "change_pet":
                print(f"\n=== R1 change_pet ===")
                print(f"  rest={e.get('rest_pet_id')} bpid={e.get('battle_pet_id')} new_pet_id={e.get('new_pet_id')} new_base_conf_id={e.get('new_pet_base_conf_id')}")
                new_cid = e.get("new_pet_base_conf_id")
                print(f"  new_pet name: {get_pet_name(new_cid) if new_cid else '?'}")
        tracker.handle_event(0x1324, detail)
        print(f"\n=== After R1 change_pet ===")
        for pet in tracker.state["opp_pets"]:
            cid = pet.get("base_conf_id")
            name = get_pet_name(cid) if cid else "?"
            print(f"  pet_id={pet.get('pet_id')} slot={pet.get('slot')} battle_uid={pet.get('battle_uid')} base_conf_id={cid} name={name}")
        oa = tracker.state["opp_active"]
        oa_cid = oa.get("base_conf_id")
        print(f"opp_active: pet_id={oa.get('pet_id')} base_conf_id={oa_cid} name={get_pet_name(oa_cid) if oa_cid else '?'}")
        break

# Get the R2 round_start packet
for p in packets:
    if p["opcode"] == 0x131A and p["filename"] == "s2c_0x4013_15662_101854.467.bin":
        record = p["record"]
        inner = None
        kind, summary = summarize(record, inner)
        detail = summary.get("detail", summary)
        wrappers = detail.get("wrappers", [])
        print(f"\n=== R2 round_start wrappers ===")
        for w in wrappers:
            sid = w.get("side")
            if sid == 401:
                cid = w.get("base_conf_id")
                print(f"  side={sid} slot={w.get('slot')} pet_id={w.get('pet_id')} base_conf_id={cid} name={get_pet_name(cid) if cid else '?'}")
        tracker.handle_event(0x131A, detail)
        print(f"\n=== After R2 round_start ===")
        for pet in tracker.state["opp_pets"]:
            cid = pet.get("base_conf_id")
            name = get_pet_name(cid) if cid else "?"
            print(f"  pet_id={pet.get('pet_id')} slot={pet.get('slot')} battle_uid={pet.get('battle_uid')} base_conf_id={cid} name={name}")
        oa = tracker.state["opp_active"]
        oa_cid = oa.get("base_conf_id")
        print(f"opp_active: pet_id={oa.get('pet_id')} base_conf_id={oa_cid} name={get_pet_name(oa_cid) if oa_cid else '?'}")
        break