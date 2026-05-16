"""
从 all.pb (FileDescriptorSet) 还原出标准 .proto 文件
用法: python decode_pb.py [input.pb] [output_dir]
默认: python decode_pb.py all.pb proto_out
"""

import os
import sys
from google.protobuf.descriptor_pb2 import FileDescriptorSet

FIELD_TYPE_MAP = {
    1: 'double', 2: 'float', 3: 'int64', 4: 'uint64', 5: 'int32',
    6: 'fixed64', 7: 'fixed32', 8: 'bool', 9: 'string', 10: 'group',
    11: 'message', 12: 'bytes', 13: 'uint32', 14: 'enum', 15: 'sfixed32',
    16: 'sfixed64', 17: 'sint32', 18: 'sint64',
}

FIELD_LABEL_MAP = {1: '', 2: 'required ', 3: 'repeated '}


def field_type_str(field):
    if field.type in (11, 14):
        return field.type_name.lstrip('.')
    return FIELD_TYPE_MAP.get(field.type, f'unknown_{field.type}')


def gen_enum(enum, indent=''):
    lines = [f'{indent}enum {enum.name} {{']
    for v in enum.value:
        lines.append(f'{indent}  {v.name} = {v.number};')
    lines.append(f'{indent}}}')
    return '\n'.join(lines)


def gen_message(msg, indent=''):
    lines = [f'{indent}message {msg.name} {{']
    for e in msg.enum_type:
        lines.append(gen_enum(e, indent + '  '))
    for nested in msg.nested_type:
        if not nested.options.map_entry:
            lines.append(gen_message(nested, indent + '  '))
    for field in msg.field:
        label = FIELD_LABEL_MAP.get(field.label, '')
        ftype = field_type_str(field)
        # map 字段检测
        if field.type == 11 and field.label == 3:
            for nested in msg.nested_type:
                if nested.options.map_entry and nested.name == field.type_name.split('.')[-1]:
                    kt = field_type_str(nested.field[0])
                    vt = field_type_str(nested.field[1])
                    lines.append(f'{indent}  map<{kt}, {vt}> {field.name} = {field.number};')
                    break
            else:
                lines.append(f'{indent}  {label}{ftype} {field.name} = {field.number};')
        else:
            lines.append(f'{indent}  {label}{ftype} {field.name} = {field.number};')
    lines.append(f'{indent}}}')
    return '\n'.join(lines)


def gen_service(svc):
    lines = [f'service {svc.name} {{']
    for m in svc.method:
        inp = m.input_type.lstrip('.')
        out = m.output_type.lstrip('.')
        lines.append(f'  rpc {m.name} ({inp}) returns ({out});')
    lines.append('}')
    return '\n'.join(lines)


def gen_proto(fd):
    lines = []
    if fd.syntax:
        lines.append(f'syntax = "{fd.syntax}";')
    if fd.package:
        lines.append(f'package {fd.package};')
    lines.append('')
    for dep in fd.dependency:
        lines.append(f'import "{dep}";')
    if fd.dependency:
        lines.append('')
    for e in fd.enum_type:
        lines.append(gen_enum(e))
        lines.append('')
    for msg in fd.message_type:
        lines.append(gen_message(msg))
        lines.append('')
    for svc in fd.service:
        lines.append(gen_service(svc))
        lines.append('')
    return '\n'.join(lines)


def main():
    pb_path = sys.argv[1] if len(sys.argv) > 1 else 'all.pb'
    out_dir = sys.argv[2] if len(sys.argv) > 2 else 'proto_out'

    if not os.path.isfile(pb_path):
        print(f'文件不存在: {pb_path}')
        sys.exit(1)

    fds = FileDescriptorSet()
    with open(pb_path, 'rb') as f:
        fds.ParseFromString(f.read())

    os.makedirs(out_dir, exist_ok=True)

    for fd in fds.file:
        content = gen_proto(fd)
        out_path = os.path.join(out_dir, fd.name)
        os.makedirs(os.path.dirname(out_path) or out_dir, exist_ok=True)
        with open(out_path, 'w', encoding='utf-8') as wf:
            wf.write(content)
        print(f'  -> {fd.name}')

    print(f'\n完成! 共 {len(fds.file)} 个 .proto 文件 -> {out_dir}/')


if __name__ == '__main__':
    main()
