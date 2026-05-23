"""
激进版扫描 — 尝试读取所有内存区域，包括受保护页面
用法: py scan_aes_key_v3.py
"""
import ctypes
import sys
import math

kernel32 = ctypes.windll.kernel32
ntdll = ctypes.windll.ntdll

PROCESS_VM_READ = 0x10
PROCESS_QUERY_INFORMATION = 0x400
MEM_COMMIT = 0x1000

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
            ("dwSize", ctypes.c_ulong), ("cntUsage", ctypes.c_ulong),
            ("th32ProcessID", ctypes.c_ulong), ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
            ("th32ModuleID", ctypes.c_ulong), ("cntThreads", ctypes.c_ulong),
            ("th32ParentProcessID", ctypes.c_ulong), ("pcPriClassBase", ctypes.c_long),
            ("dwFlags", ctypes.c_ulong), ("szExeFile", ctypes.c_char * 260),
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

def scan_all_memory(pid: int):
    hProcess = kernel32.OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, False, pid)
    if not hProcess:
        print(f"无法打开进程 PID={pid}，请以管理员身份运行。")
        return []

    OLD_KEY = bytes.fromhex("7460373AD9DEE67C30155825F7254430FFC85AD117DD6E7FF3BEE0E60E1207B8")
    candidates = []
    addr = 0
    mbi = MEMORY_BASIC_INFORMATION()
    mbi_size = ctypes.sizeof(MEMORY_BASIC_INFORMATION)
    region_count = 0
    failed_regions = 0

    print(f"激进扫描 PID={pid} ...")
    print("注意：这次会尝试读取所有内存区域，包括受保护页面。\n")

    while kernel32.VirtualQueryEx(hProcess, ctypes.c_void_p(addr), ctypes.byref(mbi), mbi_size):
        if mbi.State == MEM_COMMIT:
            region_count += 1
            size = mbi.RegionSize
            if size > 100 * 1024 * 1024:
                addr += size
                continue
            if size == 0:
                break

            buf = (ctypes.c_ubyte * size)()
            bytesRead = ctypes.c_size_t(0)
            success = kernel32.ReadProcessMemory(hProcess, ctypes.c_void_p(addr), ctypes.byref(buf), size, ctypes.byref(bytesRead))

            if not success:
                failed_regions += 1
                addr += size
                continue

            data = bytes(buf[:bytesRead.value])

            # 搜索旧密钥
            idx = data.find(OLD_KEY)
            if idx != -1:
                print(f"  [!!!] 发现旧版 Closed Beta 密钥！地址: 0x{addr + idx:016X}")

            # 超宽松搜索：任何 32 字节高熵块
            for i in range(0, len(data) - 32, 8):
                chunk = data[i:i+32]
                if len(set(chunk)) < 10:
                    continue
                ent = entropy(chunk)
                if ent >= 6.5:
                    candidates.append((addr + i, chunk.hex().upper(), ent))

            if region_count % 1000 == 0:
                print(f"  已扫描 {region_count} 个区域，失败 {failed_regions} 个，找到 {len(candidates)} 个候选...")

        addr += mbi.RegionSize
        if addr > 0x7FFF00000000:
            break

    kernel32.CloseHandle(hProcess)
    print(f"\n总计: {region_count} 个区域, {failed_regions} 个读取失败")
    return candidates

def main():
    pid = find_process_pid("NRC-Win64-Shipping.exe")
    if pid is None:
        print("错误：找不到 NRC-Win64-Shipping.exe 进程。")
        sys.exit(1)

    print(f"找到进程: NRC-Win64-Shipping.exe (PID={pid})")
    candidates = scan_all_memory(pid)

    if not candidates:
        print("\n即使是激进扫描也没有找到任何候选。")
        print("这说明密钥可能：")
        print("1. 根本不存在于内存中（使用非内存解密方案）")
        print("2. 被反作弊完全隐藏（连读取都被阻止）")
        print("3. 密钥长度不是 32 字节")
        print("4. 游戏使用了完全自定义的 Pak 解密流程")
        return

    # 按熵值排序，去重
    seen = set()
    unique = []
    for addr, key, ent in sorted(candidates, key=lambda x: -x[2]):
        if key not in seen:
            seen.add(key)
            unique.append((addr, key, ent))

    print(f"\n{'='*80}")
    print(f"去重后 {len(unique)} 个唯一候选（按熵值排序，前 30 个）：")
    print(f"{'='*80}\n")
    for addr, key, ent in unique[:30]:
        print(f"地址: 0x{addr:016X}  熵值: {ent:.2f}")
        print(f"密钥: {key}")
        print(f"FModel: 0x{key}")
        print()

if __name__ == "__main__":
    main()
