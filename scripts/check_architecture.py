"""检查后端模块依赖边界。

当前允许的主线是 capture -> protocol -> analysis -> api，data/game/config
作为底层服务被上层读取。脚本用于重构后的结构守护：无模块级 import cycle，
并阻止协议/数据/游戏层反向依赖 API 或分析层。
"""
from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Set, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"

FORBIDDEN_PACKAGE_EDGES = {
    ("protocol", "analysis"),
    ("protocol", "api"),
    ("data", "analysis"),
    ("data", "api"),
    ("game", "analysis"),
    ("game", "api"),
}

FORBIDDEN_MODULE_PREFIX_EDGES = {
    ("src.analysis.state", "src.api"),
    ("src.analysis.replay_messages", "src.api"),
}

FORBIDDEN_EXTERNAL_IMPORTS = {
    "src.analysis.replay_messages": ("fastapi",),
    "src.api.battle_sniffer_bridge": ("fastapi",),
    "src.api.battle_ws_commands": ("fastapi",),
    "src.api.ws_hub": ("fastapi",),
}


def _module_name(path: Path) -> str:
    return ".".join(path.relative_to(PROJECT_ROOT).with_suffix("").parts)


def _package_name(module: str) -> str:
    parts = module.split(".")
    return parts[1] if len(parts) > 1 and parts[0] == "src" else parts[0]


def _resolve_relative(module: str, node: ast.ImportFrom) -> str | None:
    if not node.level:
        return node.module
    base_parts = module.split(".")[:-node.level]
    if node.module:
        base_parts += node.module.split(".")
    return ".".join(base_parts) if base_parts else None


def scan_imports() -> Dict[str, Set[str]]:
    graph: Dict[str, Set[str]] = defaultdict(set)
    modules = {_module_name(path): path for path in SRC_ROOT.rglob("*.py")}
    for module, path in modules.items():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            target: str | None = None
            if isinstance(node, ast.ImportFrom):
                target = _resolve_relative(module, node)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    target = alias.name
                    break
            if not target or not target.startswith("src."):
                continue
            resolved = _resolve_to_module(target, modules)
            if resolved and resolved != module:
                graph[module].add(resolved)
    return graph


def _resolve_to_module(target: str, modules: Dict[str, Path]) -> str | None:
    if target in modules:
        return target
    candidates = [module for module in modules if module.startswith(target + ".")]
    return sorted(candidates, key=len)[0] if candidates else None


def find_forbidden_edges(graph: Dict[str, Set[str]]) -> List[Tuple[str, str]]:
    bad = []
    for src, targets in graph.items():
        src_pkg = _package_name(src)
        for dst in targets:
            dst_pkg = _package_name(dst)
            if (src_pkg, dst_pkg) in FORBIDDEN_PACKAGE_EDGES:
                bad.append((src, dst))
            if any(
                src.startswith(src_prefix) and dst.startswith(dst_prefix)
                for src_prefix, dst_prefix in FORBIDDEN_MODULE_PREFIX_EDGES
            ):
                bad.append((src, dst))
    return sorted(bad)


def find_forbidden_external_imports() -> List[Tuple[str, str]]:
    bad: List[Tuple[str, str]] = []
    modules = {_module_name(path): path for path in SRC_ROOT.rglob("*.py")}
    for module, path in modules.items():
        forbidden = [
            package
            for prefix, packages in FORBIDDEN_EXTERNAL_IMPORTS.items()
            if module == prefix or module.startswith(prefix + ".")
            for package in packages
        ]
        if not forbidden:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            imported: str | None = None
            if isinstance(node, ast.ImportFrom):
                imported = node.module
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imported = alias.name
                    break
            if imported and any(imported == pkg or imported.startswith(pkg + ".") for pkg in forbidden):
                bad.append((module, imported))
    return sorted(bad)


def find_cycles(graph: Dict[str, Set[str]]) -> List[List[str]]:
    index = 0
    stack: List[str] = []
    on_stack: Set[str] = set()
    indexes: Dict[str, int] = {}
    lowlinks: Dict[str, int] = {}
    cycles: List[List[str]] = []

    def strongconnect(node: str) -> None:
        nonlocal index
        indexes[node] = index
        lowlinks[node] = index
        index += 1
        stack.append(node)
        on_stack.add(node)

        for child in graph.get(node, set()):
            if child not in indexes:
                strongconnect(child)
                lowlinks[node] = min(lowlinks[node], lowlinks[child])
            elif child in on_stack:
                lowlinks[node] = min(lowlinks[node], indexes[child])

        if lowlinks[node] == indexes[node]:
            component = []
            while True:
                child = stack.pop()
                on_stack.remove(child)
                component.append(child)
                if child == node:
                    break
            if len(component) > 1:
                cycles.append(sorted(component))

    for node in sorted(set(graph) | {dst for targets in graph.values() for dst in targets}):
        if node not in indexes:
            strongconnect(node)
    return cycles


def format_problems(items: Iterable[Iterable[str]]) -> str:
    return "\n".join(" -> ".join(item) for item in items)


def main() -> int:
    graph = scan_imports()
    forbidden = find_forbidden_edges(graph)
    forbidden_external = find_forbidden_external_imports()
    cycles = find_cycles(graph)
    if forbidden:
        print("Forbidden package edges:")
        print(format_problems(forbidden))
    if forbidden_external:
        print("Forbidden external imports:")
        print(format_problems(forbidden_external))
    if cycles:
        print("Import cycles:")
        print(format_problems(cycles))
    if forbidden or forbidden_external or cycles:
        return 1
    print("Architecture check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
