# 端到端游戏数据更新指南

本文档说明在游戏版本更新后，如何从客户端提取最新配置数据并导入到本项目中。

## 概览

```
游戏客户端 PAK 文件 (AES 加密)
  │
  ├── Step 1: 解包 PAK → 提取 .bytes 文件
  │          quickBMS + unreal_tournament_4_0.4.27e_roco_kingdom_world.bms
  │
  ├── Step 2: 解码 .bytes → JSON (scripts/decode_bin.py)
  │
  └── Step 3: 导入 JSON → data/game/ (scripts/import_bin_data.py)
```

所有数据处理工具均在项目 `scripts/` 目录下，不依赖 `references/` 中的外部代码。

> **捷径**: 如果已有解码好的 JSON 文件（`RocoDataRows` 格式，如从他人分享或历史提取获取），直接跳到 [Step 3](#step-3-导入-json--项目数据文件)。

---

## Step 1: 从 PAK 提取 .bytes 二进制配置表

游戏数据存储在 UE4 `.pak` 封包中，文件使用 **AES 加密**，需专用 BMS 脚本解密后提取。

### 1.1 下载 quickBMS

quickBMS 是一个通用的游戏资源提取工具。

- **下载**: https://aluigi.altervista.org/quickbms.htm
- 下载 `quickbms.exe`（Windows 版）
- 放到任意目录，如 `D:\Tools\quickbms\`

### 1.2 获取 BMS 脚本

BMS 脚本告知 quickBMS 如何解析本游戏特有的 PAK 格式，脚本内嵌了解密所需的 **AES key**。

- **来源**: https://cs.rin.ru/forum/viewtopic.php?t=100672
- **脚本名**: `unreal_tournament_4_0.4.27e_roco_kingdom_world.bms`
- 放到 quickBMS 同目录下

> 论坛可能需要注册才能下载附件。AES key 内嵌在 BMS 脚本中，无需单独配置。

### 1.3 执行解包

游戏 PAK 文件位于游戏安装目录的 `Win64/NRC/Content/Paks/` 下。

```cmd
quickbms.exe ^
  unreal_tournament_4_0.4.27e_roco_kingdom_world.bms ^
  "D:\Program Files\洛克王国：世界(2002304)\Win64\NRC\Content\Paks\pakchunk0-WindowsNoEditor.pak" ^
  D:\GameExtract
```

解包多个 pak（所有 chunk）的批处理：

```bat
@echo off
set SCRIPT=D:\Tools\quickbms\unreal_tournament_4_0.4.27e_roco_kingdom_world.bms
set PAK_DIR=D:\Program Files\洛克王国：世界(2002304)\Win64\NRC\Content\Paks
set OUT_DIR=D:\GameExtract

for %%f in ("%PAK_DIR%\*.pak") do (
    echo 正在解包: %%f
    quickbms.exe "%SCRIPT%" "%%f" "%OUT_DIR%"
)
```

### 1.4 整理提取物

quickBMS 解包后，输出目录结构会镜像游戏内部的 Content 树。需要找到三个关键目录并复制到统一位置：

```
<解包根目录>/
  .../Raw/BinConf/              .non 格式的 schema 文件 (约 91 个)
  .../Raw/BinDataCompressed/    压缩二进制表 .bytes (约 400+ 个) — 大部分核心数据
  .../Raw/BinLocalize/          本地化字符串 (zh_CN/)
```

> 如果目录结构与上述不同，在解包根目录搜索 `*.bytes` 和 `*.non` 文件来定位实际路径。

整理到统一位置：

```cmd
mkdir D:\GameExtract\BinConf
mkdir D:\GameExtract\BinDataCompressed
mkdir D:\GameExtract\BinLocalize

xcopy /E <解包根目录>\...\Raw\BinConf\*           D:\GameExtract\BinConf\
xcopy /E <解包根目录>\...\Raw\BinDataCompressed\* D:\GameExtract\BinDataCompressed\
xcopy /E <解包根目录>\...\Raw\BinLocalize\*       D:\GameExtract\BinLocalize\
```

### 1.5 核心文件清单

必须确认提取到以下文件：

| 文件 | 用途 |
|------|------|
| `BinDataCompressed/PETBASE_CONF.bytes` | 宠物基础数据（种族值、属性、特性ID、进化ID） |
| `BinDataCompressed/SKILL_CONF.bytes` | 技能定义（威力、能量、效果链） |
| `BinDataCompressed/LEVEL_SKILL_CONF.bytes` | 技能学习表（升级/技能石/血脉技能） |
| `BinDataCompressed/TYPE_DICTIONARY.bytes` | 属性类型定义 + 克制关系 + 免疫 |
| `BinDataCompressed/NATURE_CONF.bytes` | 性格系统 |
| `BinDataCompressed/PET_EVOLUTION_CONF.bytes` | 进化链 |
| `BinDataCompressed/BATTLE_GLOBAL_CONFIG.bytes` | 战斗全局参数（克制倍率等） |
| `BinDataCompressed/WEATHER_CONF.bytes` | 天气系统 |
| `BinDataCompressed/BUFF_CONF.bytes` | Buff 定义 |
| `BinDataCompressed/BUFFBASE_CONF.bytes` | 基础 Buff 参数 |
| `BinConf/PETBASE_CONF.non` | 对应 schema |
| `BinConf/SKILL_CONF.non` | 对应 schema |
| `BinConf/LEVEL_SKILL_CONF.non` | 对应 schema |
| `BinConf/TYPE_DICTIONARY.non` | 对应 schema |
| `BinConf/NATURE_CONF.non` | 对应 schema |
| `BinConf/PET_EVOLUTION_CONF.non` | 对应 schema |
| `BinConf/BATTLE_GLOBAL_CONFIG.non` | 对应 schema |
| `BinConf/WEATHER_CONF.non` | 对应 schema |
| `BinConf/BUFF_CONF.non` | 对应 schema |
| `BinConf/BUFFBASE_CONF.non` | 对应 schema |
| `BinLocalize/zh_CN/PETBASE_CONF.bytes` | 宠物名中文本地化 |
| `BinLocalize/zh_CN/SKILL_CONF.bytes` | 技能名中文本地化 |

### 1.6 预期目录结构

整理后的 `D:\GameExtract\` 应如下：

```
D:\GameExtract\
  BinConf\
    PETBASE_CONF.non
    SKILL_CONF.non
    LEVEL_SKILL_CONF.non
    TYPE_DICTIONARY.non
    NATURE_CONF.non
    PET_EVOLUTION_CONF.non
    BATTLE_GLOBAL_CONFIG.non
    WEATHER_CONF.non
    BUFF_CONF.non
    BUFFBASE_CONF.non
    ... (共约 91 个 .non 文件)
  BinDataCompressed\
    PETBASE_CONF.bytes
    SKILL_CONF.bytes
    LEVEL_SKILL_CONF.bytes
    ... (共约 400+ 个 .bytes 文件)
  BinLocalize\
    zh_CN\
      PETBASE_CONF.bytes
      SKILL_CONF.bytes
      ...
```

---

## Step 2: 解码 .bytes → JSON

### 2.1 批量解码

```bash
# 解码 BinDataCompressed（主力数据源，带本地化）
py scripts/decode_bin.py D:\GameExtract\BinDataCompressed --batch ^
    --schema-dir D:\GameExtract\BinConf ^
    --loc-dir D:\GameExtract\BinLocalize\zh_CN ^
    --out-dir D:\GameExtract\decoded
```

### 2.2 验证解码结果

```bash
# 检查关键文件是否存在
ls D:\GameExtract\decoded\PETBASE_CONF.json
ls D:\GameExtract\decoded\SKILL_CONF.json
ls D:\GameExtract\decoded\LEVEL_SKILL_CONF.json

# 检查文件内容（应有 "RocoDataRows" 顶层 key）
py -c "import json; d=json.load(open('D:/GameExtract/decoded/PETBASE_CONF.json','r',encoding='utf-8')); print(len(d['RocoDataRows']))"
```

### 解码问题排查

| 现象 | 原因 | 解决 |
|------|------|------|
| `找不到 xxx 的 schema` | BinConf 中缺对应 .non | 确保提取了所有 BinConf/*.non |
| `Invalid magic: 0x...` | .bytes 文件格式不对或已损坏 | 重新提取，检查文件大小 |
| 中文字段全是乱码 | 未指定 --loc-dir | 添加 `--loc-dir <BinLocalize/zh_CN>` |
| `offset` 越界 | schema 与 .bytes 版本不匹配 | 确保 schema 和 bytes 同版本 |

---

## Step 3: 导入 JSON → 项目数据文件

```bash
# 导入所有数据（自动更新 data/game/ 下的 JSON）
py -m scripts.import_bin_data D:\GameExtract\decoded

# 预览模式（不写入，仅打印变更摘要）
py -m scripts.import_bin_data D:\GameExtract\decoded --dry-run
```

执行后会自动更新/创建以下文件：

| 文件 | 更新方式 | 来源表 |
|------|---------|--------|
| `pet_species.json` | 重写 | PETBASE_CONF |
| `pet_map.json` | 增强（添加 species_* 字段） | PETBASE_CONF + 现有 pet_map |
| `skill_map.json` | 重写 | SKILL_CONF |
| `pet_skill_map.json` | 重写 | LEVEL_SKILL_CONF + SKILL_CONF |
| `type_chart.json` | 增强（添加 type_immunity） | TYPE_DICTIONARY |
| `nature_map.json` | 新建 | NATURE_CONF |
| `evolution_map.json` | 新建 | PET_EVOLUTION_CONF |
| `battle_config.json` | 新建 | BATTLE_GLOBAL_CONFIG |
| `weather_map.json` | 新建 | WEATHER_CONF |
| `innate_skills.json` | 增强（填充 pets 映射） | PETBASE_CONF.pet_feature |

---

## Step 4: 验证

### 4.1 数据完整性

```bash
py -c "
from src.data.loader import *
invalidate_cache()
import json
species = json.load(open('data/game/pet_species.json','r',encoding='utf-8'))
psm = json.load(open('data/game/pet_skill_map.json','r',encoding='utf-8'))
print(f'物种: {len(species)}, 有技能: {len(psm)}')
"
```

### 4.2 功能测试

```bash
pytest tests/ -v --tb=short
py -m scripts.replay_headless --session battle_session_1
```

### 4.3 前后端联调（可选）

按照 CLAUDE.md 的"完整的前后端回放验证"流程，启动后端 + 前端，用 `replay_to_frontend` 推送回放数据，MCP Chrome DevTools 截图检查。

---

## 一键脚本

将所有步骤合并为批处理（保存为 `update_data.bat`）：

```bat
@echo off
set DECODED_DIR=D:\GameExtract\decoded

echo === Step 2: 解码 .bytes 文件 ===
py scripts/decode_bin.py D:\GameExtract\BinDataCompressed --batch --schema-dir D:\GameExtract\BinConf --loc-dir D:\GameExtract\BinLocalize\zh_CN --out-dir %DECODED_DIR%

echo === Step 3: 导入数据 ===
py -m scripts.import_bin_data %DECODED_DIR%

echo === Step 4: 运行验证 ===
pytest tests/test_loader.py tests/test_damage_calc.py -v --tb=short
py -m scripts.replay_headless --session battle_session_1

echo === 更新完成 ===
```

---

## 依赖清单

| 依赖 | 位置 | 说明 |
|------|------|------|
| quickBMS | 外部工具 | PAK 解包引擎，从 https://aluigi.altervista.org/quickbms.htm 下载 |
| BMS 脚本 | 外部文件 | `unreal_tournament_4_0.4.27e_roco_kingdom_world.bms`，从 cs.rin.ru 论坛获取（内嵌 AES key） |
| `scripts/decode_bin.py` | 项目内 | .bytes 二进制解码器，纯 Python 标准库 |
| `scripts/import_bin_data.py` | 项目内 | JSON → data/game/ 导入器 |

**不依赖 `references/` 目录。** 数据处理工具链完全在项目 `scripts/` 下。

### 关键外部链接

| 资源 | 链接 |
|------|------|
| quickBMS 下载 | https://aluigi.altervista.org/quickbms.htm |
| AES key / BMS 脚本 | https://cs.rin.ru/forum/viewtopic.php?t=100672 |
