"""架构边界回归测试。"""
from __future__ import annotations

from scripts.check_architecture import find_cycles, find_forbidden_edges, scan_imports


def test_backend_import_graph_has_no_cycles():
    assert find_cycles(scan_imports()) == []


def test_backend_layers_do_not_import_upward():
    assert find_forbidden_edges(scan_imports()) == []
