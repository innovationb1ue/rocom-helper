"""
Extract proto field reference from battle-related .proto files.
Parses enum definitions and message field definitions, outputs as JSON.
"""
import json
import re
import sys
from pathlib import Path

PROTO_DIR = Path("references/Roco-Kingdom-World-Data/PB/proto_out")
OUTPUT_FILE = Path("data/game/proto_field_reference.json")

# Battle-critical proto files in priority order
BATTLE_PROTOS = [
    "battle_data.proto",
    "com_battle.proto",
    "com_battle_enum.proto",
    "com_pet.proto",
    "com_pet_skill.proto",
    "battle_buff_data.proto",
    "battle_proto.proto",
    "com_base_types.proto",
]


def parse_enum(text: str) -> dict:
    """Parse an enum block from proto text."""
    lines = text.strip().split("\n")
    values = {}
    for line in lines:
        line = line.strip().rstrip(",")
        if "=" not in line or line.startswith("//"):
            continue
        m = re.match(r"(\w+)\s*=\s*(-?\d+)", line)
        if m:
            name, val = m.group(1), int(m.group(2))
            # Skip explicit default assignments like "option allow_alias = true"
            if name.startswith("option"):
                continue
            values[name] = val
    return values


def parse_message_fields(text: str) -> dict:
    """Parse field definitions from a message block."""
    fields = {}
    for line in text.strip().split("\n"):
        line = line.strip()
        if not line or line.startswith("//") or line.startswith("message") or line.startswith("enum") or line == "}" or line == "{":
            continue
        # Match proto field: [repeated] type name = number [options];
        m = re.match(
            r"(?:(repeated|optional|required)\s+)?"
            r"(map\s*<[^>]+>\s+)?"
            r"([\w.]+)\s+(\w+)\s*=\s*(\d+)",
            line,
        )
        if m:
            modifier = m.group(1) or ""
            map_type = m.group(2) or ""
            field_type = m.group(3)
            field_name = m.group(4)
            field_number = int(m.group(5))
            fields[str(field_number)] = {
                "name": field_name,
                "type": field_type,
                "repeated": modifier == "repeated",
            }
            if map_type:
                fields[str(field_number)]["map"] = True
    return fields


def extract_blocks(content: str) -> list[tuple[str, str, str, str]]:
    """Extract top-level enum and message blocks with nesting awareness.

    Returns list of (kind, name, source_file, body_text).
    """
    results = []
    i = 0
    lines = content.split("\n")
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Detect top-level enum or message
        m = re.match(r"^(enum|message)\s+(\w+)", stripped)
        if m:
            kind = m.group(1)
            name = m.group(2)
            # Collect until matching closing brace
            brace_depth = 0
            body_lines = []
            j = i
            while j < len(lines):
                l = lines[j]
                brace_depth += l.count("{") - l.count("}")
                if j > i:
                    if brace_depth > 0:
                        body_lines.append(l)
                    elif brace_depth == 0:
                        # last line (closing brace)
                        break
                j += 1
            body = "\n".join(body_lines)
            results.append((kind, name, body))
            i = j + 1
        else:
            i += 1
    return results


def extract_all():
    """Extract enums and messages from all battle proto files."""
    all_enums = {}
    all_messages = {}
    file_stats = {}

    for proto_file in BATTLE_PROTOS:
        path = PROTO_DIR / proto_file
        if not path.exists():
            print(f"  SKIP: {proto_file} not found")
            continue

        content = path.read_text(encoding="utf-8")
        blocks = extract_blocks(content)

        enum_count = 0
        msg_count = 0
        for kind, name, body in blocks:
            if kind == "enum":
                values = parse_enum(body)
                if values:
                    all_enums[name] = {
                        "source": proto_file,
                        "values": values,
                    }
                    enum_count += 1
            elif kind == "message":
                fields = parse_message_fields(body)
                if fields:
                    all_messages[name] = {
                        "source": proto_file,
                        "fields": fields,
                    }
                    msg_count += 1

        file_stats[proto_file] = {
            "enums": enum_count,
            "messages": msg_count,
        }
        print(f"  {proto_file}: {enum_count} enums, {msg_count} messages")

    return all_enums, all_messages, file_stats


def build_cross_references(all_messages: dict) -> dict:
    """Build cross-reference map: which messages reference which types."""
    xrefs = {}
    all_type_names = set(all_messages.keys())

    for msg_name, msg_def in all_messages.items():
        refs = []
        for field_num, field in msg_def["fields"].items():
            ftype = field["type"]
            # Strip leading dots from fully qualified names
            clean_type = ftype.lstrip(".")
            if clean_type in all_type_names and clean_type != msg_name:
                refs.append({
                    "field": field["name"],
                    "field_number": field_num,
                    "type": clean_type,
                })
        if refs:
            xrefs[msg_name] = refs

    return xrefs


def main():
    print("Extracting proto definitions from battle-related files...")
    all_enums, all_messages, file_stats = extract_all()

    print(f"\nTotal: {len(all_enums)} enums, {len(all_messages)} messages")

    # Build cross-references
    xrefs = build_cross_references(all_messages)

    # Build output
    output = {
        "_meta": {
            "description": "Proto field reference for battle protocol - extracted from World-Data PB/proto_out/",
            "source_files": BATTLE_PROTOS,
            "file_stats": file_stats,
            "total_enums": len(all_enums),
            "total_messages": len(all_messages),
        },
        "enums": all_enums,
        "messages": all_messages,
        "cross_references": xrefs,
    }

    # Write JSON
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\nWritten to {OUTPUT_FILE}")
    print(f"Size: {OUTPUT_FILE.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    main()
