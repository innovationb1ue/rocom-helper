import sys
sys.path.append('.')

from tests.packet_reader import read_bin_packet
from src.protocol.proto_core import parse_record
from src.protocol.battle import extract_1316_enter
from pathlib import Path

# Read the 0x1316 packet
pkt_path = Path('tests/fixtures/packets/battle_session_1/s2c_0x4013_1599_212333.620.bin')
pkt = read_bin_packet(pkt_path)

print(f"Packet: {pkt_path.name}")
print(f"Opcode: 0x{pkt['cmd']:04X}")

# Parse the record
record = parse_record(pkt)
print(f"Parsed successfully: {record is not None}")

if record:
    print(f"Record opcode: 0x{record.get('opcode', 0):04X}")
    
    # Extract battle enter data
    battle_data = extract_1316_enter(record)
    
    if battle_data:
        print(f"\n=== Battle Enter Data ===")
        print(f"Battle mode: {battle_data.get('battle_mode')}")
        print(f"Round: {battle_data.get('round')}")
        print(f"NPC ID: {battle_data.get('npc_id')}")
        
        wrappers = battle_data.get('wrappers', [])
        print(f"\nNumber of state wrappers: {len(wrappers)}")
        
        for i, wrapper in enumerate(wrappers):
            print(f"\n--- Pet {i+1} ---")
            print(f"Name: {wrapper.get('name', 'Unknown')}")
            print(f"Pet ID: {wrapper.get('pet_id', 'Unknown')}")
            print(f"Slot: {wrapper.get('slot', 'Unknown')}")
            print(f"Side: {wrapper.get('side', 'Unknown')}")
            print(f"Level: {wrapper.get('level', 'Unknown')}")
            print(f"HP: {wrapper.get('current_hp', 'Unknown')}/{wrapper.get('battle_max_hp', 'Unknown')}")
            print(f"Energy: {wrapper.get('energy', 'Unknown')}")
            print(f"Skill source: {wrapper.get('skill_source', 'Unknown')}")
            
            skills = wrapper.get('skills', [])
            equipped = wrapper.get('equipped_skills', [])
            
            print(f"Total skills: {len(skills)}")
            print(f"Equipped skills: {len(equipped)}")
            
            print("\nAll skills:")
            for skill in skills:
                print(f"  Slot {skill.get('equipped_slot', '?')}: ID {skill.get('skill_id', '?')} - {skill.get('skill_name', '?')} (PP: {skill.get('pp', '?')})")
            
            print("\nEquipped skills:")
            for skill in equipped:
                print(f"  Slot {skill.get('equipped_slot', '?')}: ID {skill.get('skill_id', '?')} - {skill.get('skill_name', '?')} (PP: {skill.get('pp', '?')})")
