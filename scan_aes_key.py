"""
从运行中的 NRC-Win64-Shipping.exe 进程内存扫描 AES-256 密钥候选。
用法: py scan_aes_key.py
"""
import ctypes
import sys
import math
import struct

# Windows API
kernel32 = ctypes.windll.kernel32
OpenProcess = kernel32.OpenProcess
VirtualQueryEx = kernel32.VirtualQueryEx
ReadProcessMemory = kernel32.ReadProcessMemory
CloseHandle = kernel32.CloseHandle

PROCESS_VM_READ = 0x10
PROCESS_QUERY_INFORMATION = 0x400

MEM_COMMIT = 0x1000
PAGE_READWRITE = 0x04
PAGE_READONLY = 0x02
PAGE_EXECUTE_READ = 0x20
PAGE_EXECUTE_READWRITE = 0x40


class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_void_p),
        ("AllocationBase", ctypes.c_void_p),
        ("AllocationProtect", ctypes.c_ulong),
        ("RegionSize", ctypes.c_size_t),
        ("State", ctypes.c_ulong),
        ("Protect", ctypes.c_ulong),
        ("Type", ctypes.c_ulong),
    ]


def find_process_pid(process_name: str):
    """通过 CreateToolhelp32Snapshot 查找进程 PID。"""
    TH32CS_SNAPPROCESS = 0x2
    hSnapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if hSnapshot == -1:
        return None

    class PROCESSENTRY32(ctypes.Structure):
        _fields_ = [
            ("dwSize", ctypes.c_ulong),
            ("cntUsage", ctypes.c_ulong),
            ("th32ProcessID", ctypes.c_ulong),
            ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
            ("th32ModuleID", ctypes.c_ulong),
            ("cntThreads", ctypes.c_ulong),
            ("th32ParentProcessID", ctypes.c_ulong),
            ("pcPriClassBase", ctypes.c_long),
            ("dwFlags", ctypes.c_ulong),
            ("szExeFile", ctypes.c_char * 260),
        ]

    entry = PROCESSENTRY32()
    entry.dwSize = ctypes.sizeof(PROCESSENTRY32)
    if kernel32.Process32First(hSnapshot, ctypes.byref(entry)):
        while True:
            if entry.szExeFile.decode("mbcs", errors="ignore").lower() == process_name.lower():
                pid = entry.th32ProcessID
                kernel32.CloseHandle(hSnapshot)
                return pid
            if not kernel32.Process32Next(hSnapshot, ctypes.byref(entry)):
                break
    kernel32.CloseHandle(hSnapshot)
    return None


def entropy(data: bytes) -> float:
    """计算 Shannon 熵（0-8）。AES 密钥应该是接近 8 的随机数据。"""
    if not data:
        return 0.0
    counts = [0] * 256
    for b in data:
        counts[b] += 1
    ent = 0.0
    length = len(data)
    for c in counts:
        if c == 0:
            continue
        p = c / length
        ent -= p * math.log2(p)
    return ent


def looks_like_aes_key(data: bytes) -> bool:
    """判断 32 字节是否像 AES-256 密钥。"""
    if len(data) != 32:
        return False
    # 不允许全 0 或全 FF
    if data == b"\x00" * 32 or data == b"\xff" * 32:
        return False
    # 熵值要高（随机数据）
    ent = entropy(data)
    if ent < 7.2:
        return False
    # 不允许太多可打印 ASCII（密钥应该是二进制随机数据）
    printable = sum(1 for b in data if 0x20 <= b <= 0x7E)
    if printable > 20:
        return False
    return True


def scan_process_memory(pid: int):
    """扫描进程内存中的 32 字节 AES 密钥候选。"""
    hProcess = OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, False, pid)
    if not hProcess:
        print(f"无法打开进程 PID={pid}，请以管理员身份运行。")
        return []

    candidates = []
    addr = 0
    mbi = MEMORY_BASIC_INFORMATION()
    mbi_size = ctypes.sizeof(MEMORY_BASIC_INFORMATION)

    # 已知 closed beta key，用于对比和关联搜索
    OLD_KEY_BYTES = bytes.fromhex("7460373AD9DEE67C30155825F7254430FFC85AD117DD6E7FF3BEE0E60E1207B8")

    print(f"开始扫描 PID={pid} 的内存...")
    region_count = 0

    while VirtualQueryEx(hProcess, ctypes.c_void_p(addr), ctypes.byref(mbi), mbi_size):
        if mbi.State == MEM_COMMIT and mbi.Protect in (
            PAGE_READWRITE,
            PAGE_READONLY,
            PAGE_EXECUTE_READ,
            PAGE_EXECUTE_READWRITE,
        ):
            region_count += 1
            size = mbi.RegionSize
            if size > 100 * 1024 * 1024:  # 跳过超过 100MB 的大区域（通常是映射文件）
                addr += size
                continue
            if size == 0:
                break

            buf = (ctypes.c_ubyte * size)()
            bytesRead = ctypes.c_size_t(0)
            if ReadProcessMemory(hProcess, ctypes.c_void_p(addr), ctypes.byref(buf), size, ctypes.byref(bytesRead)):
                data = bytes(buf[:bytesRead.value])
                # 滑动窗口搜索 32 字节
                for i in range(len(data) - 32):
                    chunk = data[i:i + 32]
                    if looks_like_aes_key(chunk):
                        hex_str = chunk.hex().upper()
                        # 排除已知的旧密钥
                        if chunk == OLD_KEY_BYTES:
                            continue
                        # 排除全相同字节的误报
                        if len(set(chunk)) < 8:
                            continue
                        candidates.append((addr + i, hex_str))
            if region_count % 100 == 0:
                print(f"  已扫描 {region_count} 个内存区域，找到 {len(candidates)} 个候选...")

        addr += mbi.RegionSize
        if addr > 0x7FFF00000000:  # 64位进程用户空间上限
            break

    CloseHandle(hProcess)
    return candidates


def main():
    pid = find_process_pid("NRC-Win64-Shipping.exe")
    if pid is None:
        print("错误：找不到 NRC-Win64-Shipping.exe 进程。")
        print("请先启动游戏并进入登录后的主界面，再运行此脚本。")
        sys.exit(1)

    print(f"找到进程: NRC-Win64-Shipping.exe (PID={pid})")
    print("注意：请以管理员身份运行此脚本，否则可能无法读取进程内存。\n")

    candidates = scan_process_memory(pid)

    print(f"\n扫描完成。找到 {len(candidates)} 个候选密钥。\n")

    if not candidates:
        print("没有找到候选密钥。可能的原因：")
        print("1. 游戏尚未加载 Pak 解密模块（请进入主界面后再扫描）")
        print("2. 密钥不在可读内存区域中")
        print("3. 密钥经过了额外的变换/加密存储")
        return

    # 去重并按地址排序
    seen = set()
    unique = []
    for addr, key in sorted(candidates, key=lambda x: x[0]):
        if key not in seen:
            seen.add(key)
            unique.append((addr, key))

    print(f"去重后剩余 {len(unique)} 个唯一候选：\n")
    print("-" * 80)
    for addr, key in unique[:50]:  # 最多显示 50 个
        print(f"地址: 0x{addr:016X}")
        print(f"密钥: {key}")
        print(f"FModel格式: 0x{key}")
        print("-" * 80)

    if len(unique) > 50:
        print(f"... 还有 {len(unique) - 50} 个候选未显示")

    print("\n使用建议：")
    print("1. 优先尝试地址最接近模块基址（0x14XXXXXX 或 0x7FFXXXXX）的候选")
    print("2. 如果候选太多，可以在游戏启动前和启动后分别扫描，对比差异")
    print("3. 把密钥复制到 FModel 的 AES Keys 中逐个测试")


if __name__ == "__main__":
    main()
