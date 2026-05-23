"""
改进版 AES 密钥扫描器 — 放宽条件 + 多策略搜索
用法: py scan_aes_key_v2.py
"""
import ctypes
import sys
import math

kernel32 = ctypes.windll.kernel32

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


def is_random_enough(data: bytes, min_entropy: float) -> bool:
    if len(set(data)) < 8:
        return False
    return entropy(data) >= min_entropy


def scan_process_memory(pid: int):
    hProcess = kernel32.OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, False, pid)
    if not hProcess:
        print(f"无法打开进程 PID={pid}，请以管理员身份运行。")
        return []

    OLD_KEY = bytes.fromhex("7460373AD9DEE67C30155825F7254430FFC85AD117DD6E7FF3BEE0E60E1207B8")
    OLD_KEY_PART = OLD_KEY[:8]  # 前8字节，用于关联搜索

    candidates = []
    addr = 0
    mbi = MEMORY_BASIC_INFORMATION()
    mbi_size = ctypes.sizeof(MEMORY_BASIC_INFORMATION)
    region_count = 0

    print(f"开始扫描 PID={pid} ...")

    while kernel32.VirtualQueryEx(hProcess, ctypes.c_void_p(addr), ctypes.byref(mbi), mbi_size):
        if mbi.State == MEM_COMMIT and mbi.Protect in (
            PAGE_READWRITE, PAGE_READONLY, PAGE_EXECUTE_READ, PAGE_EXECUTE_READWRITE
        ):
            region_count += 1
            size = mbi.RegionSize
            if size > 50 * 1024 * 1024:  # 跳过 >50MB
                addr += size
                continue
            if size == 0:
                break

            buf = (ctypes.c_ubyte * size)()
            bytesRead = ctypes.c_size_t(0)
            if kernel32.ReadProcessMemory(hProcess, ctypes.c_void_p(addr), ctypes.byref(buf), size, ctypes.byref(bytesRead)):
                data = bytes(buf[:bytesRead.value])

                # 策略1: 搜索旧密钥的完整字节（确认是否在内存中）
                idx = data.find(OLD_KEY)
                if idx != -1:
                    print(f"  [!!!] 发现旧版 Closed Beta 密钥！地址: 0x{addr + idx:016X}")
                    # 旧密钥附近 256 字节可能有新版密钥
                    nearby_start = max(0, idx - 256)
                    nearby_end = min(len(data), idx + 288)
                    nearby = data[nearby_start:nearby_end]
                    for j in range(len(nearby) - 32):
                        chunk = nearby[j:j+32]
                        if chunk != OLD_KEY and is_random_enough(chunk, 6.5):
                            candidates.append((addr + nearby_start + j, chunk.hex().upper(), "near_old_key"))

                # 策略2: 搜索旧密钥的前8字节（关联区域）
                part_idx = 0
                while True:
                    part_idx = data.find(OLD_KEY_PART, part_idx)
                    if part_idx == -1:
                        break
                    # 检查前后 512 字节的高熵块
                    window_start = max(0, part_idx - 512)
                    window_end = min(len(data), part_idx + 520)
                    for j in range(window_start, window_end - 32):
                        chunk = data[j:j+32]
                        if chunk == OLD_KEY:
                            continue
                        if is_random_enough(chunk, 6.8):
                            candidates.append((addr + j, chunk.hex().upper(), "old_key_part_nearby"))
                    part_idx += 1

                # 策略3: 宽松熵值搜索 32 字节块
                for i in range(0, len(data) - 32, 4):  # 步长4，加速
                    chunk = data[i:i+32]
                    if is_random_enough(chunk, 7.0):
                        candidates.append((addr + i, chunk.hex().upper(), "entropy_32"))

                # 策略4: 搜索 16 字节高熵块（AES-128 可能）
                for i in range(0, len(data) - 16, 4):
                    chunk = data[i:i+16]
                    if is_random_enough(chunk, 6.5):
                        candidates.append((addr + i, chunk.hex().upper(), "entropy_16"))

            if region_count % 500 == 0:
                print(f"  已扫描 {region_count} 个区域...")

        addr += mbi.RegionSize
        if addr > 0x7FFF00000000:
            break

    kernel32.CloseHandle(hProcess)
    return candidates


def main():
    # 同时扫描 NRC 主进程和 WeGame 进程
    targets = ["NRC-Win64-Shipping.exe", "tgp_daemon.exe", "WeGame.exe"]
    all_candidates = []

    for proc_name in targets:
        pid = find_process_pid(proc_name)
        if pid:
            print(f"\n找到进程: {proc_name} (PID={pid})")
            candidates = scan_process_memory(pid)
            all_candidates.extend([(proc_name, addr, key, tag) for addr, key, tag in candidates])
        else:
            print(f"未找到进程: {proc_name}")

    if not all_candidates:
        print("\n所有策略均未找到候选密钥。")
        print("可能原因：")
        print("1. 游戏使用了非标准加密（UE 'customized encryption'）")
        print("2. 密钥不在常规内存布局中")
        print("3. 密钥长度不是 16/32 字节")
        print("4. 密钥经过了变换（XOR/移位）存储")
        return

    # 去重并统计
    seen = set()
    unique = []
    for proc_name, addr, key, tag in sorted(all_candidates, key=lambda x: x[2]):
        if key not in seen:
            seen.add(key)
            unique.append((proc_name, addr, key, tag))

    print(f"\n{'='*80}")
    print(f"去重后找到 {len(unique)} 个唯一候选")
    print(f"{'='*80}\n")

    # 按标签分组显示
    for tag in ["near_old_key", "old_key_part_nearby", "entropy_32", "entropy_16"]:
        group = [x for x in unique if x[3] == tag]
        if not group:
            continue
        print(f"\n--- [{tag}] ({len(group)} 个) ---")
        for proc_name, addr, key, _ in group[:20]:
            print(f"  进程: {proc_name:<25} 地址: 0x{addr:016X}")
            print(f"  密钥: {key}")
            if len(key) == 64:
                print(f"  FModel: 0x{key}")
            print()

    print("\n建议优先尝试 'near_old_key' 和 'old_key_part_nearby' 标签的候选。")


if __name__ == "__main__":
    main()
