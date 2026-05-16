# Roco-Kingdom-World-Data

洛克王国游戏数据解包与解码工具集。

## 目录结构

- `Bin/` — 二进制配置数据及解码工具
  - `BinConf/` — Schema 文件 (.non 格式的 JSON)
  - `BinData/` — 普通配置数据 (已解码 JSON)
  - `BinDataCompressed/` — 压缩配置数据 (已解码 JSON)
  - `BinLocalize/` — 本地化字符串数据
  - `decode_bin.py` — .bytes 二进制配置解码器
- `PB/` — Protobuf 相关
  - `decode_pb.py` — .pb 文件还原为 .proto

## 使用方法

### 解码 .bytes 文件

```bash
# 单文件 (自动查找同名 schema)
python Bin/decode_bin.py ACTIVITY_CONF.bytes --schema-dir Bin/BinConf

# 指定类型和本地化
python Bin/decode_bin.py ACTIVITY_CONF.bytes -t BinDataCompressed -l BinLocalize/en_US/ACTIVITY_CONF.bytes

# 批量解码
python Bin/decode_bin.py ./raw/BinDataCompressed --batch --schema-dir Bin/BinConf --out-dir ./decoded
```

### 还原 .proto 文件

```bash
python PB/decode_pb.py all.pb proto_out
```

## 参考

- [FModel](https://github.com/4sval/FModel) 

