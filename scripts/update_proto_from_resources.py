# -*- coding: utf-8 -*-
"""
从 resources/all.pb 提取并更新 protobuf schema 文件。

用法:
  py scripts/update_proto_from_resources.py [--resources-dir <path>]

输入:
  - resources/all.pb                           # FileDescriptorSet
  - resources/BinDataCompressed/PROTO_CMD_SEQ_CONF.json   # opcode 文本名称（61条）
  - references/Roco-Kingdom-World-Data/PB/proto.json     # opcode→消息名（1497条）

输出:
  - data/game/proto_schema.json   # 消息 schema（含字段定义）
  - data/game/opcode_pb_map.json  # opcode 映射表
"""

import json
import os
import sys
import argparse
from pathlib import Path
from google.protobuf import descriptor_pb2

# Ensure UTF-8 output on Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

RESOURCES_DIR = Path("resources")
REFERENCES_DIR = Path("references/Roco-Kingdom-World-Data/PB")
OUTPUT_DIR = Path("data/game")
PROTO_JSON_PATH = REFERENCES_DIR / "proto.json"
PROTO_CMD_SEQ_PATH = RESOURCES_DIR / "BinDataCompressed" / "PROTO_CMD_SEQ_CONF.json"
ALL_PB_PATH = RESOURCES_DIR / "all.pb"
PROTO_SCHEMA_PATH = OUTPUT_DIR / "proto_schema.json"
OPCODE_MAP_PATH = OUTPUT_DIR / "opcode_pb_map.json"


def load_proto_opcodes() -> dict:
    """加载 proto.json（opcode→消息名，1497条）"""
    if not PROTO_JSON_PATH.exists():
        print(f"[WARN] {PROTO_JSON_PATH} 不存在，跳过 opcode 映射更新")
        return {}
    with open(PROTO_JSON_PATH, encoding="utf-8") as f:
        return json.load(f)


def load_proto_cmd_seq() -> dict:
    """加载 PROTO_CMD_SEQ_CONF.json（id→prompt_text，61条）"""
    if not PROTO_CMD_SEQ_PATH.exists():
        print(f"[WARN] {PROTO_CMD_SEQ_PATH} 不存在")
        return {}
    with open(PROTO_CMD_SEQ_PATH, encoding="utf-8") as f:
        data = json.load(f)
        # 结构可能是 {"RocoDataRows": {id: {"id": N, "prompt_text": "..."}}} 或直接是数组
        if isinstance(data, dict) and "RocoDataRows" in data:
            rows = data["RocoDataRows"]
        elif isinstance(data, dict):
            rows = data
        else:
            rows = data
        # 构建 id → prompt_text 映射
        result = {}
        for id_key, item in rows.items():
            if isinstance(item, dict):
                prompt = item.get("prompt_text", "") or item.get("name", "")
                result[str(id_key)] = prompt
        return result


def build_proto_schema(fds: descriptor_pb2.FileDescriptorSet) -> tuple[dict, dict]:
    """从 FileDescriptorSet 构建 proto_schema.json
    Returns (schema_dict, message_to_proto_file_map)
    """
    FIELD_TYPE_MAP = {
        1: "double", 2: "float", 3: "int64", 4: "uint64", 5: "int32",
        6: "fixed64", 7: "fixed32", 8: "bool", 9: "string", 10: "group",
        11: "message", 12: "bytes", 13: "uint32", 14: "enum", 15: "sfixed32",
        16: "sfixed64", 17: "sint32", 18: "sint64",
    }
    FIELD_WIRE_TYPE = {
        1: 1, 2: 5, 3: 0, 4: 0, 5: 0, 6: 1, 7: 5, 8: 0,
        9: 2, 10: 3, 11: 2, 12: 2, 13: 0, 14: 0, 15: 5, 16: 1, 17: 0, 18: 0,
    }

    messages = {}
    msg_to_proto_file = {}  # message name -> proto_file

    for fd in fds.file:
        proto_file = fd.name

        def process_message(msg, package="", proto_file=proto_file):
            full_name = f".{package}.{msg.name}" if package else f".{msg.name}"
            entry = {
                "meta": {"parent": package.lstrip("."), "opcode": "-", "desc": ""},
                "fields": {}
            }
            msg_to_proto_file[msg.name] = proto_file

            for field in msg.field:
                ftype = field.type
                label = field.label
                is_repeated = (label == 3)
                is_message = (ftype == 11)

                field_info = {
                    "name": field.name,
                    "type": FIELD_TYPE_MAP.get(ftype, f"unknown_{ftype}"),
                    "wire": FIELD_WIRE_TYPE.get(ftype, 0),
                    "desc": ""
                }

                if is_message and field.type_name:
                    type_name = field.type_name.lstrip(".")
                    field_info["type"] = type_name.split(".")[-1]
                    field_info["message"] = True

                if is_repeated:
                    field_info["repeated"] = True
                if ftype == 14:
                    field_info["type"] = "enum"

                entry["fields"][str(field.number)] = field_info

            nested_msgs = []
            for nested in msg.nested_type:
                if nested.options and nested.options.map_entry:
                    continue
                nested_msgs.append(nested)

            messages[msg.name] = entry

            for nested in nested_msgs:
                nested_package = full_name.lstrip(".")
                process_message(nested, nested_package, proto_file)

        for msg in fd.message_type:
            package = fd.package or ""
            process_message(msg, package, proto_file)

    return {"messages": messages}, msg_to_proto_file


def build_opcode_map(proto_opcodes: dict, cmd_seq: dict,
                      msg_to_proto_file: dict) -> dict:
    """构建 opcode_pb_map.json"""
    result = {}

    for opcode_str, full_name in proto_opcodes.items():
        try:
            opcode = int(opcode_str)
        except (ValueError, TypeError):
            continue

        # 解析 full_name: .Package.MessageName
        parts = full_name.lstrip(".").split(".")
        if len(parts) < 2:
            package = parts[0] if len(parts) == 1 else ""
            message = full_name
        else:
            package = parts[0]
            message = parts[-1]

        # 从 message name 查找 proto_file
        proto_file = msg_to_proto_file.get(message, "")
        if not proto_file:
            # 回退：根据 package 推断
            if "." in package:
                proto_file = package.split(".")[-1].lower() + ".proto"
            else:
                proto_file = package.lower() + ".proto"

        # 推断 type
        msg_type = "Req"
        if message.endswith("Rsp"):
            msg_type = "Rsp"
        elif message.endswith("Nty") or message.endswith("Ntf"):
            msg_type = "Notify"

        # 查找 prompt_text
        prompt_text = cmd_seq.get(opcode_str, "")

        result[opcode_str] = {
            "full_name": full_name,
            "message": message,
            "opcode": opcode,
            "package": package,
            "proto_file": proto_file,
            "type": msg_type,
            "prompt_text": prompt_text
        }

    return result


def main():
    parser = argparse.ArgumentParser(description="从 resources/all.pb 更新 protobuf schema")
    parser.add_argument("--resources-dir", default="resources",
                        help="resources 目录路径（默认: resources）")
    parser.add_argument("--output-dir", default="data/game",
                        help="输出目录（默认: data/game）")
    args = parser.parse_args()

    resources_dir = Path(args.resources_dir)
    output_dir = Path(args.output_dir)
    all_pb = resources_dir / "all.pb"
    proto_schema_out = output_dir / "proto_schema.json"
    opcode_map_out = output_dir / "opcode_pb_map.json"

    # 检查输入文件
    if not all_pb.exists():
        print(f"[ERROR] {all_pb} 不存在")
        sys.exit(1)

    # 解析 all.pb
    print(f"[*] 读取 {all_pb}")
    fds = descriptor_pb2.FileDescriptorSet()
    with open(all_pb, "rb") as f:
        fds.ParseFromString(f.read())
    print(f"[*] FileDescriptorSet 包含 {len(fds.file)} 个文件")

    # 生成 proto_schema.json
    print("[*] 生成 proto_schema.json...")
    schema, msg_to_proto_file = build_proto_schema(fds)
    print(f"[*] 共 {len(schema['messages'])} 个消息定义")

    # 生成 opcode_pb_map.json
    print("[*] 加载 opcode 数据源...")
    proto_opcodes = load_proto_opcodes()
    cmd_seq = load_proto_cmd_seq()
    print(f"    proto.json: {len(proto_opcodes)} 条 opcode 映射")
    print(f"    PROTO_CMD_SEQ_CONF: {len(cmd_seq)} 条文本名称")

    opcode_map = build_opcode_map(proto_opcodes, cmd_seq, msg_to_proto_file)
    print(f"[*] 共 {len(opcode_map)} 个 opcode 条目")

    # 写入文件
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"[*] 写入 {proto_schema_out}")
    with open(proto_schema_out, "w", encoding="utf-8") as f:
        json.dump(schema, f, ensure_ascii=False, indent=2)

    print(f"[*] 写入 {opcode_map_out}")
    with open(opcode_map_out, "w", encoding="utf-8") as f:
        json.dump(opcode_map, f, ensure_ascii=False, indent=2)

    print("\n[OK] protobuf 更新完成!")
    print(f"  proto_schema.json: {proto_schema_out} ({os.path.getsize(proto_schema_out):,} bytes)")
    print(f"  opcode_pb_map.json: {opcode_map_out} ({os.path.getsize(opcode_map_out):,} bytes)")


if __name__ == "__main__":
    main()