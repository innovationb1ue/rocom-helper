"""架构边界回归测试。"""
from __future__ import annotations

import ast
from pathlib import Path

from scripts.check_architecture import (
    find_cycles,
    find_forbidden_edges,
    find_forbidden_external_imports,
    scan_imports,
)


def test_backend_import_graph_has_no_cycles():
    assert find_cycles(scan_imports()) == []


def test_backend_layers_do_not_import_upward():
    assert find_forbidden_edges(scan_imports()) == []


def test_message_builders_do_not_import_web_frameworks():
    assert find_forbidden_external_imports() == []


def test_proto_core_wire_and_schema_helpers_live_in_proto_modules():
    core_tree = ast.parse(Path("src/protocol/proto_core.py").read_text(encoding="utf-8"))
    constants_tree = ast.parse(Path("src/protocol/proto/constants.py").read_text(encoding="utf-8"))
    lookups_tree = ast.parse(Path("src/protocol/proto/lookups.py").read_text(encoding="utf-8"))
    creature_tree = ast.parse(Path("src/protocol/proto/creature.py").read_text(encoding="utf-8"))
    state_wrapper_tree = ast.parse(Path("src/protocol/proto/state_wrapper.py").read_text(encoding="utf-8"))
    wire_tree = ast.parse(Path("src/protocol/proto/wire.py").read_text(encoding="utf-8"))
    tree_tree = ast.parse(Path("src/protocol/proto/tree.py").read_text(encoding="utf-8"))
    schema_tree = ast.parse(Path("src/protocol/proto/schema.py").read_text(encoding="utf-8"))
    transport_tree = ast.parse(Path("src/protocol/proto/transport.py").read_text(encoding="utf-8"))

    core_defs = {node.name for node in core_tree.body if isinstance(node, ast.FunctionDef)}
    constants_names = {
        node.targets[0].id
        for node in constants_tree.body
        if isinstance(node, ast.Assign)
        and node.targets
        and isinstance(node.targets[0], ast.Name)
    } | {
        node.target.id
        for node in constants_tree.body
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
    }
    lookups_defs = {node.name for node in lookups_tree.body if isinstance(node, ast.FunctionDef)}
    creature_defs = {node.name for node in creature_tree.body if isinstance(node, ast.FunctionDef)}
    state_wrapper_defs = {node.name for node in state_wrapper_tree.body if isinstance(node, ast.FunctionDef)}
    wire_defs = {node.name for node in wire_tree.body if isinstance(node, ast.FunctionDef)}
    tree_defs = {node.name for node in tree_tree.body if isinstance(node, ast.FunctionDef)}
    schema_defs = {node.name for node in schema_tree.body if isinstance(node, ast.FunctionDef)}
    transport_defs = {node.name for node in transport_tree.body if isinstance(node, ast.FunctionDef)}

    wire_only = {
        "read_varint",
        "maybe_utf8",
        "strip_tsf4g_padding",
        "tsf4g_trailer_len",
        "normalize_c2s_opcode",
        "maybe_signed64",
        "parse_proto_message",
    }
    tree_only = {
        "walk_messages",
        "field_groups",
        "collect_varints",
        "first_text",
        "first_sub",
        "pick_first",
    }
    schema_only = {
        "load_proto_schema",
        "message_schema",
        "schema_fields",
        "decode_packed_numeric",
        "coerce_scalar",
        "decode_scalar_entry",
        "decode_proto_by_schema",
        "attach_schema_decode",
    }
    transport_only = {
        "tgcp_command_name",
        "parse_special_payload",
        "_parse_record_v14",
        "_parse_record_live_s2c",
        "_parse_record_live_c2s",
        "_parse_record_live_c2s_no_magic",
        "_parse_record_live_c2s_short_heartbeat",
        "parse_record",
        "parse_tgcp_control_packet",
    }
    constants_only = {
        "STAT_NAMES",
        "SIDE_NAMES",
        "_WILLPOWER_SKILL_ID",
        "_ENERGY_BOTTLE_MAX",
        "SPECIAL_ACTION_COMMANDS",
        "SPECIAL_ACTION_SHAPES",
        "SDT_TO_TYPE",
    }
    lookups_only = {
        "normalize_skill_id",
        "skill_name",
        "type_name",
        "pet_name_fn",
        "buff_name",
        "side_name",
        "_attach_buff_meta",
        "_attach_buffbase_meta",
        "_extract_actor_target",
    }
    creature_only = {
        "_attach_skill_meta",
        "extract_skills",
        "extract_skills_from_round_data",
        "extract_battle_buffs",
        "extract_simple_items",
        "extract_stats",
        "extract_creature",
    }
    state_wrapper_only = {
        "_side_from_path",
        "extract_state_wrapper",
        "extract_state_wrappers_from_record",
        "dedupe_state_wrappers",
    }

    assert core_defs == {"extract_inner_message"}
    assert wire_only.issubset(wire_defs)
    assert tree_only.issubset(tree_defs)
    assert schema_only.issubset(schema_defs)
    assert transport_only.issubset(transport_defs)
    assert constants_only.issubset(constants_names)
    assert lookups_only.issubset(lookups_defs)
    assert creature_only.issubset(creature_defs)
    assert state_wrapper_only.issubset(state_wrapper_defs)


def test_opcode_inner_message_parsers_live_in_inner_module():
    opcodes_text = Path("src/protocol/opcodes.py").read_text(encoding="utf-8")
    inner_tree = ast.parse(Path("src/protocol/inner_messages.py").read_text(encoding="utf-8"))
    inner_defs = {node.name for node in inner_tree.body if isinstance(node, ast.FunctionDef)}

    assert {
        "parse_inner1_detail",
        "parse_inner51_detail",
        "parse_inner200_detail",
        "parse_inner390_detail",
    }.issubset(inner_defs)
    assert "def _parse_inner" not in opcodes_text
    assert "collect_varints" not in opcodes_text
    assert "field_groups" not in opcodes_text


def test_opcode_registry_and_dispatch_live_in_focused_modules():
    opcodes_text = Path("src/protocol/opcodes.py").read_text(encoding="utf-8")
    registry_tree = ast.parse(Path("src/protocol/opcode_registry.py").read_text(encoding="utf-8"))
    dispatch_tree = ast.parse(Path("src/protocol/opcode_dispatch.py").read_text(encoding="utf-8"))

    registry_defs = {node.name for node in registry_tree.body if isinstance(node, ast.FunctionDef)}
    registry_names = {
        node.target.id
        for node in registry_tree.body
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
    }
    dispatch_defs = {node.name for node in dispatch_tree.body if isinstance(node, ast.FunctionDef)}

    assert {
        "make_detail_handler",
        "register_opcode",
        "register_inner",
    }.issubset(registry_defs)
    assert {"OPCODE_REGISTRY", "INNER_REGISTRY"}.issubset(registry_names)
    assert {"opcode_from_record", "inner_message_id", "summarize_record"}.issubset(dispatch_defs)
    assert "_OPCODE_REGISTRY: Dict" not in opcodes_text
    assert "_INNER_REGISTRY: Dict" not in opcodes_text
    assert "def _register_opcode" not in opcodes_text
    assert "def _register_inner" not in opcodes_text
    assert "from src.data.loader import get_opcode_pb_meta" not in opcodes_text


def test_sniffer_packet_flow_rules_live_in_capture_helper():
    sniffer_text = Path("src/capture/sniffer.py").read_text(encoding="utf-8")
    packet_flow_tree = ast.parse(Path("src/capture/packet_flow.py").read_text(encoding="utf-8"))
    packet_flow_defs = {node.name for node in packet_flow_tree.body if isinstance(node, ast.FunctionDef)}

    assert {
        "flow_key_from_packet",
        "packet_direction",
        "tcp_close_reason",
    }.issubset(packet_flow_defs)
    assert "flags & 0x01" not in sniffer_text
    assert "flags & 0x04" not in sniffer_text
    assert "dst_port == port" not in sniffer_text
    assert "src_port == port" not in sniffer_text


def test_battle_report_logic_lives_in_reporting_modules():
    report_tree = ast.parse(Path("src/analysis/battle_report.py").read_text(encoding="utf-8"))
    analysis_tree = ast.parse(Path("src/analysis/reporting/analysis.py").read_text(encoding="utf-8"))
    catalog_tree = ast.parse(Path("src/analysis/reporting/catalog.py").read_text(encoding="utf-8"))
    lookup_tree = ast.parse(Path("src/analysis/reporting/lookup.py").read_text(encoding="utf-8"))
    package_tree = ast.parse(Path("src/analysis/reporting/package.py").read_text(encoding="utf-8"))
    packet_tree = ast.parse(Path("src/analysis/reporting/packet_io.py").read_text(encoding="utf-8"))
    window_tree = ast.parse(Path("src/analysis/reporting/window.py").read_text(encoding="utf-8"))

    report_defs = {node.name for node in report_tree.body if isinstance(node, ast.FunctionDef)}
    analysis_defs = {node.name for node in analysis_tree.body if isinstance(node, ast.FunctionDef)}
    catalog_defs = {node.name for node in catalog_tree.body if isinstance(node, ast.FunctionDef)}
    lookup_defs = {node.name for node in lookup_tree.body if isinstance(node, ast.FunctionDef)}
    package_defs = {node.name for node in package_tree.body if isinstance(node, ast.FunctionDef)}
    packet_defs = {node.name for node in packet_tree.body if isinstance(node, ast.FunctionDef)}
    window_defs = {node.name for node in window_tree.body if isinstance(node, ast.FunctionDef)}

    analysis_only = {
        "build_report_analysis",
        "compact_messages",
        "_pet_ref",
    }
    catalog_only = {
        "scan_report_summaries",
        "build_report_diagnostics",
        "get_report_summary",
        "build_report_summary",
    }
    lookup_only = {
        "report_id",
        "parse_report_id",
        "resolve_report",
    }
    package_only = {
        "build_report_package",
        "report_filename",
        "report_archive_path",
        "find_archived_report",
        "get_report_package",
        "archive_report_package",
        "archive_latest_completed_battle",
        "build_manifest",
        "_report_readme",
    }
    packet_only = {
        "read_bin_packet",
        "read_metadata",
        "parse_opcode_hex",
        "extract_timestamp",
        "ts_to_seconds",
    }
    window_only = {
        "count_battle_packet_files",
        "scan_battles",
        "select_packet_files",
        "load_battle_packets_for_window",
    }

    assert report_defs == set()
    assert analysis_only.issubset(analysis_defs)
    assert catalog_only.issubset(catalog_defs)
    assert lookup_only.issubset(lookup_defs)
    assert package_only.issubset(package_defs)
    assert packet_only.issubset(packet_defs)
    assert window_only.issubset(window_defs)


def test_battle_manager_transport_helpers_stay_split_from_manager():
    manager_text = Path("src/api/battle_manager.py").read_text(encoding="utf-8")
    route_text = Path("src/api/routes_battle.py").read_text(encoding="utf-8")
    hub_tree = ast.parse(Path("src/api/ws_hub.py").read_text(encoding="utf-8"))
    archive_tree = ast.parse(Path("src/api/battle_archive.py").read_text(encoding="utf-8"))
    bridge_tree = ast.parse(Path("src/api/battle_sniffer_bridge.py").read_text(encoding="utf-8"))
    commands_tree = ast.parse(Path("src/api/battle_ws_commands.py").read_text(encoding="utf-8"))
    route_actions_tree = ast.parse(Path("src/api/battle_route_actions.py").read_text(encoding="utf-8"))
    route_state_tree = ast.parse(Path("src/api/battle_route_state.py").read_text(encoding="utf-8"))
    ws_endpoint_tree = ast.parse(Path("src/api/battle_ws_endpoint.py").read_text(encoding="utf-8"))
    report_endpoint_tree = ast.parse(Path("src/api/battle_report_endpoints.py").read_text(encoding="utf-8"))
    replay_endpoint_tree = ast.parse(Path("src/api/battle_replay_endpoint.py").read_text(encoding="utf-8"))

    hub_defs = {node.name for node in hub_tree.body if isinstance(node, ast.ClassDef)}
    archive_defs = {
        node.name
        for node in archive_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    bridge_defs = {
        node.name
        for node in bridge_tree.body
        if isinstance(node, (ast.FunctionDef, ast.ClassDef))
    }
    commands_defs = {
        node.name
        for node in commands_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    route_state_defs = {node.name for node in route_state_tree.body if isinstance(node, ast.FunctionDef)}
    route_actions_defs = {
        node.name
        for node in route_actions_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    ws_endpoint_defs = {
        node.name
        for node in ws_endpoint_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    report_endpoint_defs = {node.name for node in report_endpoint_tree.body if isinstance(node, ast.FunctionDef)}
    replay_endpoint_defs = {
        node.name
        for node in replay_endpoint_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    assert "JsonWebSocketHub" in hub_defs
    assert {
        "archive_completed_battle",
        "packet_session_dir_from_sniffer",
        "schedule_completed_battle_archive",
        "should_archive_completed_battle",
    }.issubset(archive_defs)
    assert {
        "BattleSnifferBridge",
        "should_process_battle_record",
        "extract_battle_detail",
        "sniffer_manager_provider",
    }.issubset(bridge_defs)
    assert "handle_battle_ws_command" in commands_defs
    assert {
        "battle_state_payload",
        "battle_pets_route_payload",
        "battle_effects_route_payload",
        "replay_battle_route_payload",
    }.issubset(route_actions_defs)
    assert {"battle_pets_payload", "battle_effects_payload"}.issubset(route_state_defs)
    assert {
        "handle_battle_ws_connection",
        "handle_battle_ws_raw_message",
        "is_websocket_disconnect_error",
    }.issubset(ws_endpoint_defs)
    assert {
        "list_battle_reports_payload",
        "get_battle_report_payload",
        "download_battle_report_response",
    }.issubset(report_endpoint_defs)
    assert {"fixture_session_dir", "replay_battle_packets_payload"}.issubset(replay_endpoint_defs)
    assert "json.dumps" not in manager_text
    assert "send_text" not in manager_text
    assert "summary.get(\"detail\"" not in manager_text
    assert "register_record_callback" not in manager_text
    assert "get_sniffer_manager" not in manager_text
    assert "should_process_battle_record" not in manager_text
    assert "extract_battle_detail" not in manager_text
    assert "archive_latest_completed_battle" not in manager_text
    assert "get_packet_session_dir" not in manager_text
    assert "asyncio.to_thread" not in manager_text
    assert "自动归档战斗报告失败" not in manager_text
    assert "json.loads" not in route_text
    assert "Invalid JSON" not in route_text
    assert "receive_text" not in route_text
    assert "WebSocketDisconnect" not in route_text
    assert "mgr.get_state()" not in route_text
    assert "battle_pets_payload" not in route_text
    assert "battle_effects_payload" not in route_text
    assert "my_buffs = []" not in route_text
    assert "BattleReportError" not in route_text
    assert "get_report_package" not in route_text
    assert "Response(" not in route_text
    assert "replay_fixture_to_manager" not in route_text
    assert "replay_battle_packets_payload" not in route_text


def test_replay_runner_flow_helpers_stay_split_from_runner():
    runner_text = Path("src/analysis/replay_runner.py").read_text(encoding="utf-8")
    models_tree = ast.parse(Path("src/analysis/replay_models.py").read_text(encoding="utf-8"))
    flow_tree = ast.parse(Path("src/analysis/replay_flow.py").read_text(encoding="utf-8"))

    model_classes = {node.name for node in models_tree.body if isinstance(node, ast.ClassDef)}
    flow_defs = {node.name for node in flow_tree.body if isinstance(node, ast.FunctionDef)}

    assert {
        "ReplayEventSnapshot",
        "RoundSnapshot",
        "ReplayResult",
    }.issubset(model_classes)
    assert {
        "extract_replay_detail",
        "filter_process_result",
        "build_replay_messages",
        "make_event_snapshot",
        "update_round_snapshot",
        "should_stop_replay",
    }.issubset(flow_defs)
    assert "class ReplayEventSnapshot" not in runner_text
    assert "class RoundSnapshot" not in runner_text
    assert "class ReplayResult" not in runner_text
    assert "extract_inner_message" not in runner_text
    assert "summary.get(\"detail\"" not in runner_text
    assert "ProcessResult(" not in runner_text
    assert "build_battle_messages" not in runner_text
    assert "damage_predictions =" not in runner_text


def test_sniffer_manager_message_and_key_helpers_stay_split_from_manager():
    manager_text = Path("src/api/sniffer_manager.py").read_text(encoding="utf-8")
    route_text = Path("src/api/routes_sniffer.py").read_text(encoding="utf-8")
    messages_tree = ast.parse(Path("src/api/sniffer_messages.py").read_text(encoding="utf-8"))
    key_tree = ast.parse(Path("src/api/sniffer_key_store.py").read_text(encoding="utf-8"))
    events_tree = ast.parse(Path("src/api/sniffer_events.py").read_text(encoding="utf-8"))
    runtime_tree = ast.parse(Path("src/api/sniffer_runtime.py").read_text(encoding="utf-8"))
    lifecycle_tree = ast.parse(Path("src/api/sniffer_lifecycle.py").read_text(encoding="utf-8"))
    manager_flow_tree = ast.parse(Path("src/api/sniffer_manager_flow.py").read_text(encoding="utf-8"))
    startup_tree = ast.parse(Path("src/api/sniffer_startup.py").read_text(encoding="utf-8"))
    state_tree = ast.parse(Path("src/api/sniffer_state.py").read_text(encoding="utf-8"))
    manager_state_tree = ast.parse(Path("src/api/sniffer_manager_state.py").read_text(encoding="utf-8"))
    callbacks_tree = ast.parse(Path("src/api/sniffer_record_callbacks.py").read_text(encoding="utf-8"))
    monitor_tree = ast.parse(Path("src/api/sniffer_ws_monitor.py").read_text(encoding="utf-8"))
    route_actions_tree = ast.parse(Path("src/api/sniffer_route_actions.py").read_text(encoding="utf-8"))

    messages_defs = {node.name for node in messages_tree.body if isinstance(node, ast.FunctionDef)}
    key_defs = {node.name for node in key_tree.body if isinstance(node, ast.FunctionDef)}
    events_classes = {node.name for node in events_tree.body if isinstance(node, ast.ClassDef)}
    runtime_defs = {
        node.name
        for node in runtime_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    } | {
        node.targets[0].id
        for node in runtime_tree.body
        if isinstance(node, ast.Assign)
        and node.targets
        and isinstance(node.targets[0], ast.Name)
    }
    lifecycle_defs = {
        node.name
        for node in lifecycle_tree.body
        if isinstance(node, (ast.FunctionDef, ast.ClassDef))
    }
    manager_flow_defs = {
        node.name
        for node in manager_flow_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }
    startup_defs = {
        node.name
        for node in startup_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }
    state_defs = {
        node.name
        for node in state_tree.body
        if isinstance(node, (ast.FunctionDef, ast.ClassDef))
    }
    manager_state_defs = {
        node.name
        for node in manager_state_tree.body
        if isinstance(node, (ast.FunctionDef, ast.ClassDef))
    }
    callback_defs = {
        node.name
        for node in callbacks_tree.body
        if isinstance(node, (ast.FunctionDef, ast.ClassDef))
    }
    monitor_defs = {node.name for node in monitor_tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    route_action_defs = {
        node.name
        for node in route_actions_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    assert {
        "build_status_event",
        "build_status_payload",
        "slim_record",
    }.issubset(messages_defs)
    assert {"save_persistent_key"}.issubset(key_defs)
    assert {"SnifferEventHandler"}.issubset(events_classes)
    assert {"SnifferRuntime", "MonitorTick"}.issubset(runtime_defs)
    assert {
        "cleanup_failed_sniffer_start",
        "monitor_sniffer_flow_tick",
        "packet_session_dir_from_sniffer",
        "stop_sniffer_instance",
        "stop_sniffer_runtime",
    }.issubset(lifecycle_defs)
    assert {
        "evaluate_current_sniffer_state",
        "cleanup_failed_start_flow",
        "start_sniffer_manager_flow",
    }.issubset(manager_flow_defs)
    assert {
        "SnifferStartupResources",
        "monitor_session_id",
        "prepare_startup_resources",
        "create_sniffer",
        "start_sniffer_threaded",
        "wait_for_start_settle",
    }.issubset(startup_defs)
    assert {"SnifferStatusEvaluation", "evaluate_sniffer_status"}.issubset(state_defs)
    assert {"SnifferManagerState"}.issubset(manager_state_defs)
    assert {"SnifferRecordCallbacks"}.issubset(callback_defs)
    assert {
        "handle_monitor_connection",
        "status_event_from_manager",
        "send_monitor_status",
        "handle_monitor_message",
        "is_websocket_disconnect_error",
    }.issubset(monitor_defs)
    assert {
        "start_sniffer_payload",
        "stop_sniffer_payload",
        "sniffer_status_payload",
    }.issubset(route_action_defs)
    assert "def _slim_record" not in manager_text
    assert "bytes.fromhex" not in manager_text
    assert "write_key_file" not in manager_text
    assert "\"sniffer_running\"" not in manager_text
    assert "key_missing_suppressed" not in manager_text
    assert "decrypt_fail" not in manager_text
    assert "captured_at" not in manager_text
    assert "any_has_key" not in manager_text
    assert "status.get(\"flows\"" not in manager_text
    assert "json.dumps" not in manager_text
    assert "send_text" not in manager_text
    assert "threading.Lock" not in manager_text
    assert "build_status_event" not in manager_text
    assert "_ws_clients" not in manager_text
    assert "asyncio.Queue" not in manager_text
    assert "asyncio.create_task" not in manager_text
    assert "asyncio.wait_for" not in manager_text
    assert "asyncio.to_thread" not in manager_text
    assert "asyncio.sleep" not in manager_text
    assert "prepare_startup_resources" not in manager_text
    assert "create_sniffer(" not in manager_text
    assert "start_sniffer_threaded" not in manager_text
    assert "wait_for_start_settle" not in manager_text
    assert "cleanup_failed_sniffer_start" not in manager_text
    assert "evaluate_sniffer_status" not in manager_text
    assert "sniffer.stop()" not in manager_text
    assert "getattr(self._sniffer" not in manager_text
    assert "pkt_logger" not in manager_text
    assert "for _ in range" not in manager_text
    assert "current_count = self._sniffer.flow_count" not in manager_text
    assert "self._loop.call_soon_threadsafe" not in manager_text
    assert "call_soon_threadsafe(cb" not in manager_text
    assert "for cb in self._record_callbacks" not in manager_text
    assert "self._record_callbacks.append" not in manager_text
    assert "def _broadcast_loop" not in manager_text
    assert "def _monitor_loop" not in manager_text
    assert "PacketLogger" not in manager_text
    assert "setup_sniffer_logging" not in manager_text
    assert "load_key_from_file" not in manager_text
    assert "time.strftime" not in manager_text
    assert "json.dumps" not in route_text
    assert "json.loads" not in route_text
    assert "send_text" not in route_text
    assert "receive_text" not in route_text
    assert "WebSocketDisconnect" not in route_text
    assert "mgr.add_client" not in route_text
    assert "mgr.remove_client" not in route_text
    assert "HTTPException" not in route_text
    assert "already_running" not in route_text
    assert "mgr.start()" not in route_text
    assert "mgr.stop()" not in route_text


def test_capture_sniffer_event_helpers_stay_split_from_sniffer():
    sniffer_text = Path("src/capture/sniffer.py").read_text(encoding="utf-8")
    flow_registry_tree = ast.parse(Path("src/capture/flow_registry.py").read_text(encoding="utf-8"))
    control_events_tree = ast.parse(Path("src/capture/sniffer_control_events.py").read_text(encoding="utf-8"))
    data_events_tree = ast.parse(Path("src/capture/sniffer_data_events.py").read_text(encoding="utf-8"))
    events_tree = ast.parse(Path("src/capture/sniffer_events.py").read_text(encoding="utf-8"))
    key_events_tree = ast.parse(Path("src/capture/sniffer_key_events.py").read_text(encoding="utf-8"))

    flow_registry_classes = {node.name for node in flow_registry_tree.body if isinstance(node, ast.ClassDef)}
    control_event_defs = {node.name for node in control_events_tree.body if isinstance(node, ast.FunctionDef)}
    data_event_defs = {node.name for node in data_events_tree.body if isinstance(node, ast.FunctionDef)}
    event_defs = {node.name for node in events_tree.body if isinstance(node, ast.FunctionDef)}
    key_event_defs = {node.name for node in key_events_tree.body if isinstance(node, ast.FunctionDef)}

    assert {"FlowRegistry"}.issubset(flow_registry_classes)
    assert {"handle_control_frame"}.issubset(control_event_defs)
    assert {"handle_data_frame"}.issubset(data_event_defs)
    assert {
        "handle_missing_key_frame",
        "handle_parse_record_none",
    }.issubset(event_defs)
    assert {"handle_ack_key_frame"}.issubset(key_event_defs)
    assert "key_missing_reported = True" not in sniffer_text
    assert "stats[\"parse_fail\"] += 1" not in sniffer_text
    assert "extract_key_from_ack" not in sniffer_text
    assert "seen_acks.add" not in sniffer_text
    assert "log_key_extracted" not in sniffer_text
    assert "parse_tgcp_control_packet" not in sniffer_text
    assert "decrypt_4013_body" not in sniffer_text
    assert "parse_record" not in sniffer_text
    assert "summarize" not in sniffer_text
    assert "decrypted_body_hex" not in sniffer_text
    assert "已捕获到加密 DATA 帧但未捕获会话密钥" not in sniffer_text
    assert "threading.Lock" not in sniffer_text
    assert "write_key_file" not in sniffer_text
    assert "FlowState(" not in sniffer_text


def test_config_route_queries_live_in_config_service():
    route_text = Path("src/api/routes_config.py").read_text(encoding="utf-8")
    service_tree = ast.parse(Path("src/api/config_service.py").read_text(encoding="utf-8"))
    actions_tree = ast.parse(Path("src/api/config_route_actions.py").read_text(encoding="utf-8"))

    service_defs = {node.name for node in service_tree.body if isinstance(node, ast.FunctionDef)}
    action_defs = {node.name for node in actions_tree.body if isinstance(node, ast.FunctionDef)}

    assert {
        "resolve_popular_skill_name",
        "list_pets_with_learnable_skills",
        "build_learnable_skill_payload",
        "pet_learnable_skills_payload",
    }.issubset(service_defs)
    assert {
        "list_popular_skills_payload",
        "get_popular_skill_payload",
        "update_popular_skill_payload",
        "delete_popular_skill_payload",
        "pets_with_learnable_skills_payload",
        "pet_learnable_skills_or_404",
    }.issubset(action_defs)
    assert "get_bundle" not in route_text
    assert "get_pet_skill_meta" not in route_text
    assert "get_pet_meta" not in route_text
    assert "get_skill_meta" not in route_text
    assert "level_skills" not in route_text
    assert "editor_name" not in route_text
    assert "HTTPException" not in route_text
    assert "get_all_popular_skills" not in route_text
    assert "get_popular_skills" not in route_text
    assert "save_popular_skills" not in route_text
    assert "delete_popular_skills" not in route_text


def test_battle_processor_hook_dispatch_lives_in_processor_hooks_module():
    processor_text = Path("src/analysis/battle_processor.py").read_text(encoding="utf-8")
    hooks_tree = ast.parse(Path("src/analysis/processor_hooks.py").read_text(encoding="utf-8"))
    flow_tree = ast.parse(Path("src/analysis/processor_hook_flow.py").read_text(encoding="utf-8"))
    hooks_defs = {node.name for node in hooks_tree.body if isinstance(node, (ast.FunctionDef, ast.ClassDef))}
    flow_defs = {node.name for node in flow_tree.body if isinstance(node, (ast.FunctionDef, ast.ClassDef))}

    assert {
        "create_default_hook_registry",
        "opcode_to_triggers",
        "write_hook_signals",
        "run_hooks",
    }.issubset(hooks_defs)
    assert {
        "HookRegistryLike",
        "build_hook_context",
        "opcode_to_triggers",
        "write_hook_signals",
        "serialize_hook_advice",
        "run_hook_flow",
    }.issubset(flow_defs)
    assert "HookContext(" not in processor_text
    assert "create_default_hooks" not in processor_text
    assert "collect_signals" not in processor_text
    assert "notify_battle_enter" not in processor_text
    assert "notify_battle_finish" not in processor_text
    hooks_text = Path("src/analysis/processor_hooks.py").read_text(encoding="utf-8")
    assert "HookContext(" not in hooks_text
    assert "registry.dispatch(trigger" not in hooks_text
    assert "registry.collect_signals" not in hooks_text
    assert "[advice.to_dict()" not in hooks_text


def test_hook_registry_dispatch_loops_live_in_hook_dispatch_module():
    registry_text = Path("src/analysis/hook_registry.py").read_text(encoding="utf-8")
    dispatch_tree = ast.parse(Path("src/analysis/hook_dispatch.py").read_text(encoding="utf-8"))
    dispatch_defs = {node.name for node in dispatch_tree.body if isinstance(node, ast.FunctionDef)}

    assert {
        "dispatch_hooks",
        "notify_hooks_enter",
        "notify_hooks_finish",
        "collect_hook_signals",
        "reset_hooks",
    }.issubset(dispatch_defs)
    assert "logger.exception" not in registry_text
    assert "hook.process(ctx)" not in registry_text
    assert "hook.emit_signals(ctx)" not in registry_text
    assert "hook.on_battle_enter(ctx)" not in registry_text
    assert "hook.on_battle_finish(ctx)" not in registry_text


def test_battle_processor_analysis_helpers_live_in_processor_analysis_module():
    processor_text = Path("src/analysis/battle_processor.py").read_text(encoding="utf-8")
    analysis_tree = ast.parse(Path("src/analysis/processor_analysis.py").read_text(encoding="utf-8"))
    analysis_defs = {
        node.name
        for node in analysis_tree.body
        if isinstance(node, (ast.FunctionDef, ast.ClassDef))
    }

    assert {
        "BattleAdviceLike",
        "AdvisorLike",
        "TacticalRecommendationLike",
        "TacticalEngineLike",
        "compute_damage_analysis",
        "has_usable_damage_predictions",
        "compute_damage_analysis_for_event",
        "compute_tactical",
        "compute_tactical_with_reliability",
    }.issubset(analysis_defs)
    assert "project_state_after_entries" not in processor_text
    assert "build_prediction_reliability" not in processor_text
    assert ".analyze(state)" not in processor_text
    assert ".recommend(state)" not in processor_text


def test_state_projector_entry_handlers_live_in_projection_modules():
    projector_text = Path("src/analysis/state_projector.py").read_text(encoding="utf-8")
    core_tree = ast.parse(Path("src/analysis/projection/core.py").read_text(encoding="utf-8"))
    effects_tree = ast.parse(Path("src/analysis/projection/effects.py").read_text(encoding="utf-8"))
    resources_tree = ast.parse(Path("src/analysis/projection/resources.py").read_text(encoding="utf-8"))
    pets_tree = ast.parse(Path("src/analysis/projection/pets.py").read_text(encoding="utf-8"))
    field_tree = ast.parse(Path("src/analysis/projection/field.py").read_text(encoding="utf-8"))

    core_defs = {node.name for node in core_tree.body if isinstance(node, ast.FunctionDef)}
    effects_defs = {node.name for node in effects_tree.body if isinstance(node, ast.FunctionDef)}
    resources_defs = {node.name for node in resources_tree.body if isinstance(node, ast.FunctionDef)}
    pets_defs = {node.name for node in pets_tree.body if isinstance(node, ast.FunctionDef)}
    field_defs = {node.name for node in field_tree.body if isinstance(node, ast.FunctionDef)}

    assert {"active_for_side"}.issubset(core_defs)
    assert {"project_effect_apply", "project_effect_stage"}.issubset(effects_defs)
    assert {
        "project_energy",
        "project_combo_skill_cast",
        "project_skill_cast",
    }.issubset(resources_defs)
    assert {"project_change_pet"}.issubset(pets_defs)
    assert {"project_weather_change"}.issubset(field_defs)
    assert "def _project_effect_apply" not in projector_text
    assert "def _project_effect_stage" not in projector_text
    assert "def _project_energy" not in projector_text
    assert "def _project_change_pet" not in projector_text
    assert "def _project_skill_cast" not in projector_text
    assert "def _project_weather_change" not in projector_text
    assert "enrich_buff_modifiers" not in projector_text
    assert "refresh_battle_uid" not in projector_text


def test_switch_advisor_logic_lives_in_switch_advice_module():
    advisor_text = Path("src/analysis/hooks/switch_advisor.py").read_text(encoding="utf-8")
    advice_tree = ast.parse(Path("src/analysis/hooks/switch_advice.py").read_text(encoding="utf-8"))
    advice_defs = {node.name for node in advice_tree.body if isinstance(node, ast.FunctionDef)}

    assert {
        "best_effectiveness",
        "is_opponent_switch",
        "find_best_counter",
        "build_switch_messages",
        "prefer_switch_target",
    }.issubset(advice_defs)
    assert "for entry in ctx.entries" not in advisor_text
    assert "find_counters" not in advisor_text
    assert "same_battle_pet" not in advisor_text
    assert "bad_matchup" not in advisor_text
    assert "counter_switch" not in advisor_text


def test_energy_monitor_logic_lives_in_energy_advice_module():
    monitor_text = Path("src/analysis/hooks/energy_monitor.py").read_text(encoding="utf-8")
    advice_tree = ast.parse(Path("src/analysis/hooks/energy_advice.py").read_text(encoding="utf-8"))
    advice_defs = {node.name for node in advice_tree.body if isinstance(node, ast.FunctionDef)}

    assert {
        "min_attack_cost",
        "equipped_or_used_skills",
        "build_my_energy_messages",
        "build_opp_energy_messages",
        "energy_advice_priority",
        "should_avoid_skill",
    }.issubset(advice_defs)
    assert "skill_damage_type" not in monitor_text
    assert "energy_starved" not in monitor_text
    assert "opp_energy_low" not in monitor_text
    assert "prev_energy" not in monitor_text
    assert "cost_energy" not in monitor_text


def test_opponent_tracker_logic_lives_in_opponent_behavior_module():
    tracker_text = Path("src/analysis/hooks/opponent_tracker.py").read_text(encoding="utf-8")
    behavior_tree = ast.parse(Path("src/analysis/hooks/opponent_behavior.py").read_text(encoding="utf-8"))
    behavior_defs = {node.name for node in behavior_tree.body if isinstance(node, ast.FunctionDef)}

    assert {
        "is_my_side",
        "record_skill_casts",
        "skill_preference_messages",
        "append_switch_logs",
        "switch_pattern_messages",
        "build_behavior_messages",
        "build_behavior_data",
    }.issubset(behavior_defs)
    assert "for entry in ctx.entries" not in tracker_text
    assert "skill_preference" not in tracker_text
    assert "switch_pattern" not in tracker_text
    assert "prev_hp_pct" not in tracker_text
    assert "most_common" not in tracker_text


def test_battle_processor_output_helpers_live_in_processor_outputs_module():
    processor_text = Path("src/analysis/battle_processor.py").read_text(encoding="utf-8")
    outputs_tree = ast.parse(Path("src/analysis/processor_outputs.py").read_text(encoding="utf-8"))
    outputs_defs = {
        node.name
        for node in outputs_tree.body
        if isinstance(node, (ast.FunctionDef, ast.ClassDef))
    }

    assert {
        "build_formatted_events",
        "build_suggestions",
        "build_process_result",
    }.issubset(outputs_defs)
    assert "format_battle_event" not in processor_text
    assert "build_state_suggestions" not in processor_text
    assert "ProcessResult(" not in processor_text


def test_battle_processor_single_event_flow_lives_in_processor_event_flow_module():
    processor_text = Path("src/analysis/battle_processor.py").read_text(encoding="utf-8")
    flow_tree = ast.parse(Path("src/analysis/processor_event_flow.py").read_text(encoding="utf-8"))
    flow_defs = {
        node.name
        for node in flow_tree.body
        if isinstance(node, (ast.FunctionDef, ast.ClassDef))
    }

    assert {
        "TrackerLike",
        "process_battle_event",
    }.issubset(flow_defs)
    assert "should_snapshot_state_before" not in processor_text
    assert "should_compute_damage_analysis" not in processor_text
    assert "should_compute_tactical" not in processor_text
    assert "build_formatted_events(" not in processor_text
    assert "build_suggestions(" not in processor_text
    assert "build_process_result(" not in processor_text
    assert "compute_damage_analysis_for_event(" not in processor_text
    assert "compute_tactical_with_reliability(" not in processor_text


def test_battle_advisor_helpers_live_in_advisor_modules():
    advisor_text = Path("src/analysis/battle_advisor.py").read_text(encoding="utf-8")
    skill_tree = ast.parse(Path("src/analysis/advisor/skill_analysis.py").read_text(encoding="utf-8"))
    suggestions_tree = ast.parse(Path("src/analysis/advisor/suggestions.py").read_text(encoding="utf-8"))
    traits_tree = ast.parse(Path("src/analysis/advisor/traits.py").read_text(encoding="utf-8"))

    skill_defs = {node.name for node in skill_tree.body if isinstance(node, ast.FunctionDef)}
    suggestions_defs = {node.name for node in suggestions_tree.body if isinstance(node, ast.FunctionDef)}
    traits_defs = {node.name for node in traits_tree.body if isinstance(node, ast.FunctionDef)}

    assert {"build_skill_analysis", "skill_from_equipped", "eval_skill_dict"}.issubset(skill_defs)
    assert {"build_advisor_suggestions"}.issubset(suggestions_defs)
    assert {"extract_traits"}.issubset(traits_defs)
    assert "DamagePredictionService" in advisor_text
    assert "get_skill_meta" not in advisor_text
    assert "score_skill" not in advisor_text
    assert "CounterPicker" not in advisor_text
    assert "same_battle_pet" not in advisor_text
    assert "get_innate_skill" not in advisor_text
    assert "get_pet_innate_trait" not in advisor_text


def test_damage_calculator_runtime_and_stat_helpers_live_in_damage_modules():
    damage_text = Path("src/analysis/damage_calc.py").read_text(encoding="utf-8")
    stats_tree = ast.parse(Path("src/analysis/damage/combat_stats.py").read_text(encoding="utf-8"))
    runtime_tree = ast.parse(Path("src/analysis/damage/server_runtime.py").read_text(encoding="utf-8"))
    calculation_tree = ast.parse(Path("src/analysis/damage/calculation.py").read_text(encoding="utf-8"))
    hook_tree = ast.parse(Path("src/analysis/damage/hook_pipeline.py").read_text(encoding="utf-8"))
    finalize_tree = ast.parse(Path("src/analysis/damage/finalize.py").read_text(encoding="utf-8"))
    formula_tree = ast.parse(Path("src/analysis/damage/formula.py").read_text(encoding="utf-8"))
    multiplier_tree = ast.parse(Path("src/analysis/damage/multipliers.py").read_text(encoding="utf-8"))
    batch_tree = ast.parse(Path("src/analysis/damage/batch.py").read_text(encoding="utf-8"))
    skill_tree = ast.parse(Path("src/analysis/damage/skill_resolution.py").read_text(encoding="utf-8"))
    config_tree = ast.parse(Path("src/analysis/damage/calculator_config.py").read_text(encoding="utf-8"))
    phase_tree = ast.parse(Path("src/analysis/damage/calculator_phases.py").read_text(encoding="utf-8"))
    compat_tree = ast.parse(Path("src/analysis/damage/calculator_compat.py").read_text(encoding="utf-8"))

    stats_defs = {node.name for node in stats_tree.body if isinstance(node, ast.FunctionDef)}
    runtime_defs = {node.name for node in runtime_tree.body if isinstance(node, ast.FunctionDef)}
    calculation_defs = {node.name for node in calculation_tree.body if isinstance(node, ast.FunctionDef)}
    hook_defs = {
        node.name
        for node in hook_tree.body
        if isinstance(node, (ast.FunctionDef, ast.ClassDef))
    }
    finalize_defs = {
        node.name
        for node in finalize_tree.body
        if isinstance(node, (ast.FunctionDef, ast.ClassDef))
    }
    formula_defs = {node.name for node in formula_tree.body if isinstance(node, ast.FunctionDef)}
    multiplier_defs = {
        node.name
        for node in multiplier_tree.body
        if isinstance(node, (ast.FunctionDef, ast.ClassDef))
    }
    batch_defs = {
        node.name
        for node in batch_tree.body
        if isinstance(node, (ast.FunctionDef, ast.ClassDef))
    }
    skill_defs = {node.name for node in skill_tree.body if isinstance(node, ast.FunctionDef)}
    config_defs = {node.name for node in config_tree.body if isinstance(node, ast.FunctionDef)}
    phase_defs = {
        node.name
        for node in ast.walk(phase_tree)
        if isinstance(node, (ast.FunctionDef, ast.ClassDef))
    }
    compat_defs = {
        node.name
        for node in ast.walk(compat_tree)
        if isinstance(node, (ast.FunctionDef, ast.ClassDef))
    }

    assert {
        "get_stat_with_source",
        "get_stat",
        "get_pvp_template_stat",
        "resolve_stat_buff_modifiers",
        "resolve_combat_stats",
    }.issubset(stats_defs)
    assert {"resolve_server_runtime", "apply_server_power_rule"}.issubset(runtime_defs)
    assert {"calculate_damage"}.issubset(calculation_defs)
    assert "DamageHookPipeline" in hook_defs
    assert {
        "DamageFinalizeInput",
        "finalize_damage_result",
        "build_damage_breakdown",
        "reflect_buff_applied",
    }.issubset(finalize_defs)
    assert {"base_damage"}.issubset(formula_defs)
    assert {
        "DamageMultiplierInput",
        "DamageMultiplierResult",
        "apply_damage_multipliers",
        "_formula_effectiveness",
    }.issubset(multiplier_defs)
    assert {"SkillDamageCalculator", "calculate_all_skills"}.issubset(batch_defs)
    assert {
        "resolve_damage_type",
        "resolve_skill_element",
        "is_attack_skill",
        "apply_buff_power_modifiers",
    }.issubset(skill_defs)
    assert {"normalize_server_power_rules"}.issubset(config_defs)
    assert {
        "DamageCalculationPhasesMixin",
        "_apply_server_power_rule",
        "_resolve_power",
        "_resolve_combat_stats",
        "_compute_base_damage",
        "_apply_multipliers",
        "_finalize_damage",
    }.issubset(phase_defs)
    assert {
        "DamageCalculatorCompatMixin",
        "_base_damage",
        "_get_power",
        "_get_runtime_skill",
        "_resolve_server_runtime",
        "_get_stat",
        "_get_pvp_template_stat",
        "_get_base_hit_count",
    }.issubset(compat_defs)
    assert "get_buff_stat_modifiers" not in damage_text
    assert "get_buff_hit_count_modifiers" not in damage_text
    assert "get_buff_derived_stat_modifiers" not in damage_text
    assert "get_buff_power_modifiers" not in damage_text
    assert "get_skill_meta" not in damage_text
    assert "get_weather_damage_mult" not in damage_text
    assert "(atk / def_) * power * 0.9" not in damage_text
    assert "SDT_TO_TYPE" not in damage_text
    assert "_STAB_MULTIPLIER" not in damage_text
    assert "get_pet_species_stats" not in damage_text
    assert "get_nature_stat_modifiers" not in damage_text
    assert "server_power_skip_reason\" = \"ratio_exceeded" not in damage_text
    assert "self._hooks[stage].append" not in damage_text
    assert "DamageResult(" not in damage_text
    assert "resolve_damage_type" not in damage_text
    assert "resolve_skill_element" not in damage_text
    assert "apply_buff_power_modifiers" not in damage_text
    assert "formula_power_source" not in damage_text
    assert "rules.get(\"skills\", rules)" not in damage_text
    assert "def _resolve_power" not in damage_text
    assert "def _apply_multipliers" not in damage_text
    assert "def _finalize_damage" not in damage_text
    assert "def _base_damage" not in damage_text
    assert "def _get_stat" not in damage_text


def test_buff_modifier_domains_live_in_focused_data_modules():
    modifier_text = Path("src/data/buff_modifiers.py").read_text(encoding="utf-8")
    tables_tree = ast.parse(Path("src/data/buff_tables.py").read_text(encoding="utf-8"))
    effects_tree = ast.parse(Path("src/data/buff_effects.py").read_text(encoding="utf-8"))
    skill_tree = ast.parse(Path("src/data/buff_skill_modifiers.py").read_text(encoding="utf-8"))
    stat_tree = ast.parse(Path("src/data/buff_stat_modifiers.py").read_text(encoding="utf-8"))
    presentation_tree = ast.parse(Path("src/data/buff_presentation.py").read_text(encoding="utf-8"))
    resource_tree = ast.parse(Path("src/data/buff_resource_modifiers.py").read_text(encoding="utf-8"))
    tables_defs = {node.name for node in tables_tree.body if isinstance(node, ast.FunctionDef)}
    effects_defs = {node.name for node in effects_tree.body if isinstance(node, ast.FunctionDef)}
    skill_defs = {node.name for node in skill_tree.body if isinstance(node, ast.FunctionDef)}
    stat_defs = {node.name for node in stat_tree.body if isinstance(node, ast.FunctionDef)}
    presentation_defs = {node.name for node in presentation_tree.body if isinstance(node, ast.FunctionDef)}
    resource_defs = {node.name for node in resource_tree.body if isinstance(node, ast.FunctionDef)}

    assert {
        "get_buff_stat_table",
        "get_buff_child_table",
        "get_speed_buff_table",
        "get_buff_damage_reduction_table",
        "reset_buff_tables",
    }.issubset(tables_defs)
    assert {
        "coerce_buff_id",
        "buff_stage",
        "iter_derived_buffs",
        "collect_buff_ids",
        "collect_effective_buff_ids",
        "iter_effective_buff_ids",
    }.issubset(effects_defs)
    assert {
        "get_buff_power_modifiers",
        "get_buff_hit_count_modifiers",
    }.issubset(skill_defs)
    assert {
        "_merge_modifiers",
        "_resolve_buff_modifiers",
        "get_buff_derived_stat_modifiers",
        "get_buff_stat_modifiers",
    }.issubset(stat_defs)
    assert {
        "format_buff_modifier_summary",
        "enrich_buff_modifiers",
    }.issubset(presentation_defs)
    assert {
        "get_speed_buff_modifiers",
        "get_buff_damage_reduction",
    }.issubset(resource_defs)
    assert "_build_buff_stat_table" not in modifier_text
    assert "_build_buff_child_table" not in modifier_text
    assert "_build_speed_buff_table" not in modifier_text
    assert "_build_buff_damage_reduction_table" not in modifier_text
    assert "get_bundle" not in modifier_text
    assert "def _iter_effective_buff_ids" not in modifier_text
    assert "def get_buff_power_modifiers" not in modifier_text
    assert "def get_buff_hit_count_modifiers" not in modifier_text
    assert "def get_buff_stat_modifiers" not in modifier_text
    assert "def get_buff_derived_stat_modifiers" not in modifier_text
    assert "def enrich_buff_modifiers" not in modifier_text
    assert "def get_speed_buff_modifiers" not in modifier_text
    assert "def get_buff_damage_reduction" not in modifier_text
    assert "_POWER_FLAT_BUFF_IDS" not in modifier_text
    assert "_HIT_FLAT_BUFF_IDS" not in modifier_text
    assert "_BUFF_MODIFIER_LABELS" not in modifier_text


def test_species_data_queries_live_in_focused_data_modules():
    species_text = Path("src/data/species.py").read_text(encoding="utf-8")
    pet_tree = ast.parse(Path("src/data/pet_species.py").read_text(encoding="utf-8"))
    nature_tree = ast.parse(Path("src/data/nature.py").read_text(encoding="utf-8"))
    evolution_tree = ast.parse(Path("src/data/evolution.py").read_text(encoding="utf-8"))
    config_tree = ast.parse(Path("src/data/battle_config.py").read_text(encoding="utf-8"))
    weather_tree = ast.parse(Path("src/data/weather.py").read_text(encoding="utf-8"))

    pet_defs = {node.name for node in pet_tree.body if isinstance(node, ast.FunctionDef)}
    nature_defs = {node.name for node in nature_tree.body if isinstance(node, ast.FunctionDef)}
    evolution_defs = {node.name for node in evolution_tree.body if isinstance(node, ast.FunctionDef)}
    config_defs = {node.name for node in config_tree.body if isinstance(node, ast.FunctionDef)}
    weather_defs = {node.name for node in weather_tree.body if isinstance(node, ast.FunctionDef)}

    assert {
        "_load_pet_species",
        "get_pet_species",
        "get_pet_species_stats",
        "get_pet_species_types",
        "get_pet_implemented",
        "get_base_id_by_name",
        "get_species_by_name",
        "get_pet_types_from_species",
        "reset_pet_species_caches",
    }.issubset(pet_defs)
    assert {
        "get_nature",
        "get_nature_by_name",
        "get_nature_stat_modifiers",
        "reset_nature_caches",
    }.issubset(nature_defs)
    assert {
        "get_evolution_chain",
        "get_evolution_pvp_mute_group",
        "reset_evolution_caches",
    }.issubset(evolution_defs)
    assert {
        "get_battle_config",
        "get_restraint_multipliers",
        "reset_battle_config_caches",
    }.issubset(config_defs)
    assert {
        "get_weather",
        "get_weather_by_name",
        "get_weather_damage_mult",
        "reset_weather_caches",
    }.issubset(weather_defs)
    assert "def get_pet_species(" not in species_text
    assert "def get_nature(" not in species_text
    assert "def get_evolution_chain(" not in species_text
    assert "def get_battle_config(" not in species_text
    assert "def get_weather(" not in species_text
    assert "DATA_DIR" not in species_text
    assert "get_bundle" not in species_text


def test_catalog_io_cache_and_lookup_live_in_focused_data_modules():
    catalog_text = Path("src/data/catalog.py").read_text(encoding="utf-8")
    files_tree = ast.parse(Path("src/data/catalog_files.py").read_text(encoding="utf-8"))
    bundle_tree = ast.parse(Path("src/data/catalog_bundle.py").read_text(encoding="utf-8"))
    lookup_tree = ast.parse(Path("src/data/catalog_lookup.py").read_text(encoding="utf-8"))

    catalog_defs = {node.name for node in ast.parse(catalog_text).body if isinstance(node, ast.FunctionDef)}
    files_defs = {node.name for node in files_tree.body if isinstance(node, ast.FunctionDef)}
    bundle_defs = {node.name for node in bundle_tree.body if isinstance(node, ast.FunctionDef)}
    lookup_defs = {node.name for node in lookup_tree.body if isinstance(node, ast.FunctionDef)}

    assert {"_safe_int", "_read_json_dict"}.issubset(files_defs)
    assert {
        "_int_keyed_meta",
        "_name_map_from_meta",
        "_load_json_bundle",
        "get_bundle",
        "_load_all_maps",
        "get_maps",
        "invalidate_catalog_cache",
    }.issubset(bundle_defs)
    assert {
        "_normalize_skill_id",
        "_normalize_lookup_value",
        "_get_bundle_meta",
        "_get_name_from_meta_or_map",
        "get_attr_meta",
        "get_attr_name",
        "get_skill_meta",
        "get_skill_name",
        "get_buff_meta",
        "get_buffbase_meta",
        "get_pet_meta",
        "get_pet_name",
        "get_opcode_pb_meta",
        "get_pb_message_meta",
    }.issubset(lookup_defs)
    assert catalog_defs == set()
    assert "json.load" not in catalog_text
    assert "threading.RLock" not in catalog_text
    assert "def get_skill_name" not in catalog_text


def test_loader_domain_queries_live_in_focused_data_modules():
    loader_text = Path("src/data/loader.py").read_text(encoding="utf-8")
    pet_skills_tree = ast.parse(Path("src/data/pet_skills.py").read_text(encoding="utf-8"))
    wiki_tree = ast.parse(Path("src/data/wiki_compat.py").read_text(encoding="utf-8"))
    innate_tree = ast.parse(Path("src/data/innate.py").read_text(encoding="utf-8"))

    loader_defs = {node.name for node in ast.parse(loader_text).body if isinstance(node, ast.FunctionDef)}
    pet_skills_defs = {node.name for node in pet_skills_tree.body if isinstance(node, ast.FunctionDef)}
    wiki_defs = {node.name for node in wiki_tree.body if isinstance(node, ast.FunctionDef)}
    innate_defs = {node.name for node in innate_tree.body if isinstance(node, ast.FunctionDef)}

    assert {"get_pet_skill_meta"}.issubset(pet_skills_defs)
    assert {
        "get_wiki_pet",
        "get_wiki_skill",
        "get_wiki_pet_types",
        "get_wiki_pet_stats",
    }.issubset(wiki_defs)
    assert {
        "_load_innate_skills",
        "get_innate_skill",
        "_load_pet_traits",
        "get_pet_innate_trait",
        "get_innate_skills_for_pet",
        "reset_innate_caches",
    }.issubset(innate_defs)
    assert loader_defs == {"invalidate_cache"}
    assert "json.load" not in loader_text
    assert "def get_pet_skill_meta" not in loader_text
    assert "def get_wiki_pet" not in loader_text
    assert "def get_innate_skill" not in loader_text
    assert "_innate_skills_cache" not in loader_text
    assert "_pet_trait_cache" not in loader_text


def test_damage_prediction_config_and_output_helpers_live_in_damage_modules():
    prediction_text = Path("src/analysis/damage_prediction.py").read_text(encoding="utf-8")
    calc_text = Path("src/analysis/damage_calc.py").read_text(encoding="utf-8")
    output_text = Path("src/analysis/damage/prediction_output.py").read_text(encoding="utf-8")
    adjustments_tree = ast.parse(Path("src/analysis/damage/prediction_adjustments.py").read_text(encoding="utf-8"))
    config_tree = ast.parse(Path("src/analysis/damage/prediction_config.py").read_text(encoding="utf-8"))
    explain_tree = ast.parse(Path("src/analysis/damage/prediction_explain.py").read_text(encoding="utf-8"))
    output_tree = ast.parse(Path("src/analysis/damage/prediction_output.py").read_text(encoding="utf-8"))
    payload_tree = ast.parse(Path("src/analysis/damage/prediction_payload.py").read_text(encoding="utf-8"))
    quality_tree = ast.parse(Path("src/analysis/damage/prediction_quality.py").read_text(encoding="utf-8"))
    secondary_tree = ast.parse(Path("src/analysis/damage/prediction_secondary.py").read_text(encoding="utf-8"))
    result_tree = ast.parse(Path("src/analysis/damage/result.py").read_text(encoding="utf-8"))

    config_defs = {
        node.name
        for node in config_tree.body
        if isinstance(node, (ast.FunctionDef, ast.ClassDef))
    }
    adjustment_defs = {node.name for node in adjustments_tree.body if isinstance(node, ast.FunctionDef)}
    explain_defs = {node.name for node in explain_tree.body if isinstance(node, ast.FunctionDef)}
    output_defs = {node.name for node in output_tree.body if isinstance(node, ast.FunctionDef)}
    payload_defs = {node.name for node in payload_tree.body if isinstance(node, ast.FunctionDef)}
    quality_defs = {node.name for node in quality_tree.body if isinstance(node, ast.FunctionDef)}
    secondary_defs = {node.name for node in secondary_tree.body if isinstance(node, ast.FunctionDef)}
    secondary_names = {
        node.target.id
        for node in secondary_tree.body
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
    } | {
        node.targets[0].id
        for node in secondary_tree.body
        if isinstance(node, ast.Assign)
        and node.targets
        and isinstance(node.targets[0], ast.Name)
    }
    result_defs = {
        node.name
        for node in result_tree.body
        if isinstance(node, (ast.FunctionDef, ast.ClassDef))
    }

    assert {
        "DamageCalibration",
        "DamageCalibrationStore",
        "SpecialDamageRule",
        "SpecialDamageRuleStore",
        "ServerPowerRuleStore",
    }.issubset(config_defs)
    assert {
        "apply_special_rule",
        "apply_calibration",
        "accuracy_flags",
        "prediction_confidence",
        "validation_hint",
        "secondary_effects",
        "explain_prediction",
        "build_prediction_payload",
    }.issubset(output_defs)
    assert {"apply_special_rule", "apply_calibration"}.issubset(adjustment_defs)
    assert {"explain_prediction", "audit_key"}.issubset(explain_defs)
    assert {"build_prediction_payload"}.issubset(payload_defs)
    assert {"accuracy_flags", "prediction_confidence", "validation_hint"}.issubset(quality_defs)
    assert {"secondary_effects"}.issubset(secondary_defs)
    assert {"POISON_CAPSULE_SKILL_ID", "POISON_ELEMENT_ID", "POISON_TICK_RATIO"}.issubset(secondary_names)
    assert {
        "DamageResult",
        "damage_result_from_dict",
        "collect_derived_buffs",
        "base_hit_count",
        "skill_power",
    }.issubset(result_defs)
    assert "json.load" not in prediction_text
    assert "POISON_CAPSULE" not in prediction_text
    assert "POISON_CAPSULE" not in output_text
    assert "runtime_effect_unmodeled" not in output_text
    assert "攻防属性来自估算" not in output_text
    assert "ATK / DEF" not in output_text
    assert "battle_uid" not in output_text
    assert "damage_result_from_dict" not in output_text
    assert "raw_expected_damage" not in output_text
    assert "predicted_hp_after_with_secondary" not in output_text
    assert "predicted_hp_after_with_secondary" not in prediction_text
    assert "DamageResult(**" not in prediction_text
    assert "from src.analysis.damage_calc import DamageResult" not in output_text
    assert "@dataclass" not in calc_text
    assert "DamageResult(**" not in calc_text


def test_damage_audit_summary_and_calibration_live_in_damage_modules():
    audit_text = Path("src/analysis/damage_audit.py").read_text(encoding="utf-8")
    summary_tree = ast.parse(Path("src/analysis/damage/audit_summary.py").read_text(encoding="utf-8"))
    calibration_tree = ast.parse(Path("src/analysis/damage/audit_calibration.py").read_text(encoding="utf-8"))
    mechanism_text = Path("src/analysis/damage/audit_mechanism.py").read_text(encoding="utf-8")
    mechanism_tree = ast.parse(Path("src/analysis/damage/audit_mechanism.py").read_text(encoding="utf-8"))
    recommendation_tree = ast.parse(
        Path("src/analysis/damage/audit_mechanism_recommendation.py").read_text(encoding="utf-8")
    )
    mechanism_stats_tree = ast.parse(
        Path("src/analysis/damage/audit_mechanism_stats.py").read_text(encoding="utf-8")
    )
    direct_samples_tree = ast.parse(Path("src/analysis/damage/audit_direct_samples.py").read_text(encoding="utf-8"))
    mechanism_samples_tree = ast.parse(Path("src/analysis/damage/audit_mechanism_samples.py").read_text(encoding="utf-8"))
    samples_tree = ast.parse(Path("src/analysis/damage/audit_samples.py").read_text(encoding="utf-8"))
    models_tree = ast.parse(Path("src/analysis/damage/audit_models.py").read_text(encoding="utf-8"))
    ledger_tree = ast.parse(Path("src/analysis/damage/audit_ledger.py").read_text(encoding="utf-8"))
    runtime_tree = ast.parse(Path("src/analysis/damage/audit_runtime.py").read_text(encoding="utf-8"))
    utils_tree = ast.parse(Path("src/analysis/damage/audit_utils.py").read_text(encoding="utf-8"))

    summary_defs = {node.name for node in summary_tree.body if isinstance(node, ast.FunctionDef)}
    calibration_defs = {node.name for node in calibration_tree.body if isinstance(node, ast.FunctionDef)}
    mechanism_defs = {node.name for node in mechanism_tree.body if isinstance(node, ast.FunctionDef)}
    recommendation_defs = {node.name for node in recommendation_tree.body if isinstance(node, ast.FunctionDef)}
    mechanism_stats_defs = {node.name for node in mechanism_stats_tree.body if isinstance(node, ast.FunctionDef)}
    direct_samples_defs = {
        node.name
        for node in direct_samples_tree.body
        if isinstance(node, (ast.FunctionDef, ast.ClassDef))
    }
    mechanism_samples_defs = {
        node.name
        for node in mechanism_samples_tree.body
        if isinstance(node, (ast.FunctionDef, ast.ClassDef))
    }
    samples_defs = {
        node.name
        for node in samples_tree.body
        if isinstance(node, (ast.FunctionDef, ast.ClassDef))
    }
    models_defs = {
        node.name
        for node in models_tree.body
        if isinstance(node, (ast.FunctionDef, ast.ClassDef))
    }
    ledger_defs = {node.name for node in ledger_tree.body if isinstance(node, ast.FunctionDef)}
    runtime_defs = {node.name for node in runtime_tree.body if isinstance(node, ast.FunctionDef)}
    utils_defs = {node.name for node in utils_tree.body if isinstance(node, ast.FunctionDef)}

    assert {
        "summarize_damage_samples",
        "summarize_multi_session_damage_audit",
        "source_counts",
        "candidate_strategy_summary",
        "group_samples",
    }.issubset(summary_defs)
    assert {"build_damage_calibration", "build_special_damage_rules"}.issubset(calibration_defs)
    assert {
        "build_mechanism_report",
        "build_multi_session_mechanism_report",
        "candidate_totals",
        "mechanism_strategy_totals",
        "decomposition_check",
        "mechanism_group_by_skill",
        "field_presence",
        "mechanism_recommendation",
    }.issubset(mechanism_defs)
    assert {"mechanism_recommendation"}.issubset(recommendation_defs)
    assert {
        "mechanism_strategy_summary",
        "decomposition_summary",
        "field_presence",
    }.issubset(mechanism_stats_defs)
    assert {"iter_damage_audit_samples"}.issubset(direct_samples_defs)
    assert {"iter_damage_mechanism_samples"}.issubset(mechanism_samples_defs)
    assert {"iter_damage_audit_samples", "iter_damage_mechanism_samples"}.issubset(samples_defs)
    assert {"DamageAuditSample", "DamageMechanismSample"}.issubset(models_defs)
    assert {"ledger_records_for_damage", "ledger_actual_damage", "find_prediction"}.issubset(ledger_defs)
    assert {"runtime_skill_for_sample", "attacker_pet_candidates", "matched_runtime_value"}.issubset(runtime_defs)
    assert {
        "first_present",
        "optional_int",
        "has_value",
        "resolve_runtime_cost",
        "restraint_to_multiplier",
    }.issubset(utils_defs)
    assert "Counter(" not in audit_text
    assert "baseline_mape=" not in audit_text
    assert "catastrophic_high_confidence" not in audit_text
    assert "matched direct damage samples below 3" not in audit_text
    assert "damage_param_as_effective_power" not in audit_text
    assert "confirmed light special damage" not in mechanism_text
    assert "candidate_for_whitelist" not in mechanism_text
    assert "mean(" not in mechanism_text
    assert "has_value(" not in mechanism_text
    assert "@dataclass" not in audit_text
    samples_text = Path("src/analysis/damage/audit_samples.py").read_text(encoding="utf-8")
    assert "@dataclass" not in samples_text
    assert "def ledger_records_for_damage" not in samples_text
    assert "def runtime_skill_for_sample" not in samples_text
    assert "ledger_total = sum" not in samples_text
    assert "actual_source = \"formatted_event\"" not in samples_text
    assert "buff_modifiers={" not in samples_text
    assert "mechanism_strategy_totals(" not in samples_text
    assert "decomposition_check(" not in samples_text
    assert "matched_runtime_value(" not in samples_text
    assert "runtime_skill.get(\"damage_params_by_pet\")" not in samples_text
    assert "def _runtime_skill_for_sample" not in audit_text
    assert "def _matched_runtime_value" not in audit_text


def test_battle_state_entry_dispatch_targets_existing_handlers():
    from src.analysis.battle_state import BattleStateTracker
    from src.analysis.state.action_entries import ENTRY_HANDLERS

    missing = [
        handler_name
        for handler_name in ENTRY_HANDLERS.values()
        if not hasattr(BattleStateTracker, handler_name)
    ]

    assert missing == []


def test_battle_state_lifecycle_handlers_live_in_state_modules():
    state_tree = ast.parse(Path("src/analysis/battle_state.py").read_text(encoding="utf-8"))
    action_tree = ast.parse(Path("src/analysis/state/action_resolve.py").read_text(encoding="utf-8"))
    dispatch_tree = ast.parse(Path("src/analysis/state/event_dispatch.py").read_text(encoding="utf-8"))
    lifecycle_tree = ast.parse(Path("src/analysis/state/lifecycle_events.py").read_text(encoding="utf-8"))
    snapshot_tree = ast.parse(Path("src/analysis/state/snapshot.py").read_text(encoding="utf-8"))
    wrapper_tree = ast.parse(Path("src/analysis/state/wrapper_sync.py").read_text(encoding="utf-8"))
    state_text = Path("src/analysis/battle_state.py").read_text(encoding="utf-8")
    tracker_class = next(
        node for node in state_tree.body
        if isinstance(node, ast.ClassDef) and node.name == "BattleStateTracker"
    )
    state_defs = {node.name for node in tracker_class.body if isinstance(node, ast.FunctionDef)}
    action_defs = {node.name for node in action_tree.body if isinstance(node, ast.FunctionDef)}
    dispatch_defs = {
        node.name
        for node in dispatch_tree.body
        if isinstance(node, ast.FunctionDef)
    }
    lifecycle_defs = {node.name for node in lifecycle_tree.body if isinstance(node, ast.FunctionDef)}
    snapshot_defs = {node.name for node in snapshot_tree.body if isinstance(node, ast.FunctionDef)}
    wrapper_defs = {node.name for node in wrapper_tree.body if isinstance(node, ast.FunctionDef)}

    lifecycle_only = {
        "handle_battle_enter",
        "handle_round_start",
        "handle_action_ack",
        "handle_battle_finish",
        "handle_skill_select",
        "handle_special_refresh",
        "handle_skill_declare",
        "handle_round_flow",
    }
    wrapper_only = {"update_pets_from_wrappers", "pet_matches"}

    assert "handle_action_resolve" in action_defs
    assert {
        "append_protocol_event",
        "current_event_context",
        "dispatch_protocol_event",
        "apply_protocol_event",
    }.issubset(dispatch_defs)
    assert {
        "build_state_snapshot",
        "clone_state_mapping",
        "clone_event_history",
        "clone_state_value",
        "compute_effective_speed",
    }.issubset(snapshot_defs)
    assert "_handle_action_resolve" not in state_defs
    assert "for entry in detail.get(\"entries\"" not in state_text
    assert "ENTRY_HANDLERS.get" not in state_text
    assert "if opcode == OPCODE_" not in state_text
    assert "elif opcode == OPCODE_" not in state_text
    assert "self.state[\"events\"].append" not in state_text
    assert "self._ctx.current_opcode = opcode" not in state_text
    assert "copy.deepcopy" not in state_text
    assert "get_speed_buff_modifiers" not in state_text
    assert "clone_state_with_effective_speed" not in state_text
    assert state_defs.isdisjoint(lifecycle_only)
    assert lifecycle_only.issubset(lifecycle_defs)
    assert state_defs.isdisjoint(wrapper_only)
    assert wrapper_only.issubset(wrapper_defs)


def test_perform_sync_extractors_live_in_sync_module():
    action_tree = ast.parse(Path("src/protocol/battle_parts/action_resolve.py").read_text(encoding="utf-8"))
    sync_text = Path("src/protocol/battle_parts/sync.py").read_text(encoding="utf-8")
    sync_tree = ast.parse(Path("src/protocol/battle_parts/sync.py").read_text(encoding="utf-8"))
    common_tree = ast.parse(Path("src/protocol/battle_parts/sync_common.py").read_text(encoding="utf-8"))
    items_tree = ast.parse(Path("src/protocol/battle_parts/sync_items.py").read_text(encoding="utf-8"))
    skill_tree = ast.parse(Path("src/protocol/battle_parts/sync_skill.py").read_text(encoding="utf-8"))
    action_defs = {node.name for node in action_tree.body if isinstance(node, ast.FunctionDef)}
    sync_defs = {node.name for node in sync_tree.body if isinstance(node, ast.FunctionDef)}
    common_defs = {node.name for node in common_tree.body if isinstance(node, ast.FunctionDef)}
    item_defs = {node.name for node in items_tree.body if isinstance(node, ast.FunctionDef)}
    item_names = {
        node.targets[0].id
        for node in items_tree.body
        if isinstance(node, ast.Assign)
        and node.targets
        and isinstance(node.targets[0], ast.Name)
    }
    skill_defs = {node.name for node in skill_tree.body if isinstance(node, ast.FunctionDef)}

    sync_only = {
        "_extract_skill_change_sync",
        "_extract_pet_info_sync",
        "_extract_pet_skill_updates",
        "_extract_sync_data",
    }
    common_only = {
        "_pick_sync_value",
        "_pick_fixed32_float",
        "_extract_buffdata_93_skill",
        "_extract_simple_subitems",
    }
    items_only = {
        "_extract_sync_items",
        "_extract_task_infos",
    }
    item_tables = {
        "_PET_SYNC_FIELDS",
        "_SKILL_SYNC_FIELDS",
        "_ROLE_SYNC_FIELDS",
        "_COMM_SYNC_FIELDS",
        "_ITEM_SYNC_FIELDS",
    }
    skill_only = {
        "_extract_pet_skill_round_data",
        "_extract_damage_params",
        "_extract_restraint_types",
        "_extract_skill_buff_info",
        "_extract_set_cost_info",
    }

    assert action_defs.isdisjoint(sync_only | common_only | skill_only)
    assert sync_only.issubset(sync_defs)
    assert common_only.issubset(common_defs)
    assert items_only.issubset(item_defs)
    assert item_tables.issubset(item_names)
    assert skill_only.issubset(skill_defs)
    assert "def _extract_sync_items" not in sync_text
    assert "def _extract_task_infos" not in sync_text
    assert "_PET_SYNC_FIELDS = {" not in sync_text


def test_perform_dispatch_lives_in_dedicated_module():
    action_text = Path("src/protocol/battle_parts/action_resolve.py").read_text(encoding="utf-8")
    action_tree = ast.parse(action_text)
    dispatch_tree = ast.parse(Path("src/protocol/battle_parts/perform_dispatch.py").read_text(encoding="utf-8"))
    action_defs = {node.name for node in action_tree.body if isinstance(node, ast.FunctionDef)}
    dispatch_defs = {node.name for node in dispatch_tree.body if isinstance(node, ast.FunctionDef)}

    dispatch_only = {
        "_attach_perform_meta",
        "_extract_1324_entry",
        "_extract_perform_cmd",
    }

    assert action_defs.isdisjoint(dispatch_only)
    assert dispatch_only.issubset(dispatch_defs)
    assert "apply_skill_cast_entry" not in action_text
    assert "apply_effect_apply_entry" not in action_text
    assert "apply_change_pet_entry" not in action_text
    assert "apply_data_update_entry" not in action_text
    assert "perform_generic" not in action_text
    assert "_extract_sync_data" not in action_text
    assert "buff_name" not in action_text


def test_battle_lifecycle_extractors_live_in_focused_modules():
    lifecycle_tree = ast.parse(Path("src/protocol/battle_parts/lifecycle.py").read_text(encoding="utf-8"))
    core_tree = ast.parse(Path("src/protocol/battle_parts/lifecycle_core.py").read_text(encoding="utf-8"))
    flow_tree = ast.parse(Path("src/protocol/battle_parts/lifecycle_flow.py").read_text(encoding="utf-8"))
    lifecycle_defs = {node.name for node in lifecycle_tree.body if isinstance(node, ast.FunctionDef)}
    core_defs = {node.name for node in core_tree.body if isinstance(node, ast.FunctionDef)}
    flow_defs = {node.name for node in flow_tree.body if isinstance(node, ast.FunctionDef)}
    core_names = {
        node.targets[0].id
        for node in core_tree.body
        if isinstance(node, ast.Assign)
        and node.targets
        and isinstance(node.targets[0], ast.Name)
    } | {
        node.target.id
        for node in core_tree.body
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
    }

    core_only = {
        "extract_1316_enter",
        "extract_131a_round_start",
        "extract_132c_finish",
    }
    flow_only = {
        "extract_1312_round_flow",
        "extract_1313_round_confirm",
        "extract_1314_round_confirm_rsp",
    }

    assert lifecycle_defs == set()
    assert "BATTLE_RESULT_MAP" in core_names
    assert core_only.issubset(core_defs)
    assert flow_only.issubset(flow_defs)


def test_battle_command_extractors_live_in_focused_modules():
    commands_tree = ast.parse(Path("src/protocol/battle_parts/commands.py").read_text(encoding="utf-8"))
    skills_tree = ast.parse(Path("src/protocol/battle_parts/command_skills.py").read_text(encoding="utf-8"))
    results_tree = ast.parse(Path("src/protocol/battle_parts/command_results.py").read_text(encoding="utf-8"))
    refresh_tree = ast.parse(Path("src/protocol/battle_parts/command_refresh.py").read_text(encoding="utf-8"))

    commands_defs = {node.name for node in commands_tree.body if isinstance(node, ast.FunctionDef)}
    skills_defs = {node.name for node in skills_tree.body if isinstance(node, ast.FunctionDef)}
    results_defs = {node.name for node in results_tree.body if isinstance(node, ast.FunctionDef)}
    refresh_defs = {node.name for node in refresh_tree.body if isinstance(node, ast.FunctionDef)}

    assert commands_defs == set()
    assert {"extract_130b_skill_select", "extract_1322_skill_declare"}.issubset(skills_defs)
    assert {"extract_130c_result", "infer_action_from_wrappers"}.issubset(results_defs)
    assert {
        "extract_13f4_refresh",
        "_extract_skill_options",
        "_extract_energy_refresh",
    }.issubset(refresh_defs)


def test_battle_auxiliary_extractors_live_in_focused_modules():
    auxiliary_text = Path("src/protocol/battle_parts/auxiliary.py").read_text(encoding="utf-8")
    auxiliary_tree = ast.parse(auxiliary_text)
    creatures_tree = ast.parse(Path("src/protocol/battle_parts/auxiliary_creatures.py").read_text(encoding="utf-8"))
    actions_tree = ast.parse(Path("src/protocol/battle_parts/auxiliary_actions.py").read_text(encoding="utf-8"))
    simple_tree = ast.parse(Path("src/protocol/battle_parts/auxiliary_simple.py").read_text(encoding="utf-8"))

    auxiliary_defs = {node.name for node in auxiliary_tree.body if isinstance(node, ast.FunctionDef)}
    creature_defs = {node.name for node in creatures_tree.body if isinstance(node, ast.FunctionDef)}
    action_defs = {node.name for node in actions_tree.body if isinstance(node, ast.FunctionDef)}
    simple_names = {
        node.targets[0].id
        for node in simple_tree.body
        if isinstance(node, ast.Assign)
        and node.targets
        and isinstance(node.targets[0], ast.Name)
    } | {
        node.target.id
        for node in simple_tree.body
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
    }

    assert auxiliary_defs == set()
    assert {"extract_0102_creatures", "extract_0102_metadata"}.issubset(creature_defs)
    assert {"extract_0220_handle", "extract_01a9_action"}.issubset(action_defs)
    assert {
        "extract_1305_load_finish_req",
        "extract_1306_load_finish_rsp",
        "extract_1309_supply_pet_req",
        "extract_130a_supply_pet_rsp",
        "extract_1326_auto_cmd",
        "extract_132a_role_leave",
        "extract_132d_force_finish",
        "extract_132e_player_runaway_req",
        "extract_132f_player_runaway_rsp",
        "extract_1334_emoji",
        "extract_1335_round_op_query_req",
        "extract_1336_round_op_query_rsp",
        "extract_133c_catch_rsp",
        "extract_13f6_ai_skill",
        "extract_13f9_pk_again",
    }.issubset(simple_names)
    assert "bytes.fromhex" not in auxiliary_text
    assert "candidate_ids" not in auxiliary_text
    assert "_make_simple_extractor" not in auxiliary_text


def test_core_perform_entry_handlers_live_in_core_module():
    action_tree = ast.parse(Path("src/protocol/battle_parts/action_resolve.py").read_text(encoding="utf-8"))
    core_tree = ast.parse(Path("src/protocol/battle_parts/perform_entries_core.py").read_text(encoding="utf-8"))
    action_defs = {node.name for node in action_tree.body if isinstance(node, ast.FunctionDef)}
    core_defs = {node.name for node in core_tree.body if isinstance(node, ast.FunctionDef)}

    core_only = {
        "apply_skill_cast_entry",
        "apply_damage_entry",
        "apply_heal_entry",
        "apply_energy_entry",
    }

    assert action_defs.isdisjoint(core_only)
    assert core_only.issubset(core_defs)


def test_effect_perform_entry_handlers_live_in_effects_module():
    action_tree = ast.parse(Path("src/protocol/battle_parts/action_resolve.py").read_text(encoding="utf-8"))
    effects_tree = ast.parse(Path("src/protocol/battle_parts/perform_entries_effects.py").read_text(encoding="utf-8"))
    action_defs = {node.name for node in action_tree.body if isinstance(node, ast.FunctionDef)}
    effects_defs = {node.name for node in effects_tree.body if isinstance(node, ast.FunctionDef)}

    effects_only = {
        "apply_effect_apply_entry",
        "apply_buff_trigger_entry",
        "apply_effect_link_entry",
        "apply_effect_trigger_entry",
    }

    assert action_defs.isdisjoint(effects_only)
    assert effects_only.issubset(effects_defs)


def test_pet_perform_entry_handlers_live_in_pet_module():
    action_tree = ast.parse(Path("src/protocol/battle_parts/action_resolve.py").read_text(encoding="utf-8"))
    pet_tree = ast.parse(Path("src/protocol/battle_parts/perform_entries_pet.py").read_text(encoding="utf-8"))
    action_defs = {node.name for node in action_tree.body if isinstance(node, ast.FunctionDef)}
    pet_defs = {node.name for node in pet_tree.body if isinstance(node, ast.FunctionDef)}

    pet_only = {
        "apply_defeat_entry",
        "apply_revive_entry",
        "apply_change_pet_entry",
        "apply_change_model_entry",
        "apply_supply_pet_entry",
    }

    assert action_defs.isdisjoint(pet_only)
    assert pet_only.issubset(pet_defs)


def test_resource_perform_entry_handlers_live_in_resource_module():
    action_tree = ast.parse(Path("src/protocol/battle_parts/action_resolve.py").read_text(encoding="utf-8"))
    resource_tree = ast.parse(Path("src/protocol/battle_parts/perform_entries_resource.py").read_text(encoding="utf-8"))
    action_defs = {node.name for node in action_tree.body if isinstance(node, ast.FunctionDef)}
    resource_defs = {node.name for node in resource_tree.body if isinstance(node, ast.FunctionDef)}

    resource_only = {
        "apply_sp_energy_change_entry",
        "apply_sp_energy_trigger_entry",
    }

    assert action_defs.isdisjoint(resource_only)
    assert resource_only.issubset(resource_defs)


def test_field_perform_entry_handlers_live_in_field_module():
    action_tree = ast.parse(Path("src/protocol/battle_parts/action_resolve.py").read_text(encoding="utf-8"))
    field_tree = ast.parse(Path("src/protocol/battle_parts/perform_entries_field.py").read_text(encoding="utf-8"))
    action_defs = {node.name for node in action_tree.body if isinstance(node, ast.FunctionDef)}
    field_defs = {node.name for node in field_tree.body if isinstance(node, ast.FunctionDef)}

    field_only = {
        "apply_idle_entry",
        "apply_skill_state_entry",
        "apply_weather_change_entry",
        "apply_notify_perform_entry",
        "apply_ai_action_entry",
        "apply_pvp_perform_marker_entry",
        "apply_data_update_entry",
    }

    assert action_defs.isdisjoint(field_only)
    assert field_only.issubset(field_defs)


def test_skill_perform_entry_handlers_live_in_skill_module():
    action_tree = ast.parse(Path("src/protocol/battle_parts/action_resolve.py").read_text(encoding="utf-8"))
    skill_tree = ast.parse(Path("src/protocol/battle_parts/perform_entries_skill.py").read_text(encoding="utf-8"))
    action_defs = {node.name for node in action_tree.body if isinstance(node, ast.FunctionDef)}
    skill_defs = {node.name for node in skill_tree.body if isinstance(node, ast.FunctionDef)}

    skill_only = {
        "apply_role_skill_cast_entry",
        "apply_combo_skill_cast_entry",
        "apply_skill_pos_change_entry",
        "apply_special_move_entry",
    }

    assert action_defs.isdisjoint(skill_only)
    assert skill_only.issubset(skill_defs)


def test_tactical_action_space_and_opponent_model_live_in_tactical_modules():
    engine_tree = ast.parse(Path("src/analysis/tactical_engine.py").read_text(encoding="utf-8"))
    action_tree = ast.parse(Path("src/analysis/tactical/action_space.py").read_text(encoding="utf-8"))
    damage_tree = ast.parse(Path("src/analysis/tactical/damage.py").read_text(encoding="utf-8"))
    opponent_tree = ast.parse(Path("src/analysis/tactical/opponent_model.py").read_text(encoding="utf-8"))
    runtime_tree = ast.parse(Path("src/analysis/tactical/runtime.py").read_text(encoding="utf-8"))
    scoring_tree = ast.parse(Path("src/analysis/tactical/action_scoring.py").read_text(encoding="utf-8"))
    detail_builder_tree = ast.parse(Path("src/analysis/tactical/action_detail_builder.py").read_text(encoding="utf-8"))
    outcome_scoring_tree = ast.parse(Path("src/analysis/tactical/action_outcome_scoring.py").read_text(encoding="utf-8"))
    non_damage_tree = ast.parse(Path("src/analysis/tactical/non_damage_scoring.py").read_text(encoding="utf-8"))
    hook_signal_tree = ast.parse(Path("src/analysis/tactical/hook_signal_scoring.py").read_text(encoding="utf-8"))
    details_tree = ast.parse(Path("src/analysis/tactical/action_details.py").read_text(encoding="utf-8"))
    reason_tree = ast.parse(Path("src/analysis/tactical/action_reason.py").read_text(encoding="utf-8"))
    metrics_tree = ast.parse(Path("src/analysis/tactical/action_metrics.py").read_text(encoding="utf-8"))
    outcomes_tree = ast.parse(Path("src/analysis/tactical/outcomes.py").read_text(encoding="utf-8"))
    switch_tree = ast.parse(Path("src/analysis/tactical/switch_targets.py").read_text(encoding="utf-8"))
    threats_tree = ast.parse(Path("src/analysis/tactical/threats.py").read_text(encoding="utf-8"))
    recommendations_tree = ast.parse(Path("src/analysis/tactical/recommendations.py").read_text(encoding="utf-8"))
    recommendation_builder_tree = ast.parse(Path("src/analysis/tactical/recommendation_builder.py").read_text(encoding="utf-8"))
    confidence_tree = ast.parse(Path("src/analysis/tactical/recommendation_confidence.py").read_text(encoding="utf-8"))
    score_factory_tree = ast.parse(Path("src/analysis/tactical/action_score_factory.py").read_text(encoding="utf-8"))
    action_presentation_tree = ast.parse(Path("src/analysis/tactical/action_presentation.py").read_text(encoding="utf-8"))
    recommendation_presentation_tree = ast.parse(Path("src/analysis/tactical/recommendation_presentation.py").read_text(encoding="utf-8"))
    engine_action_tree = ast.parse(Path("src/analysis/tactical/engine_actions.py").read_text(encoding="utf-8"))
    engine_opponent_tree = ast.parse(Path("src/analysis/tactical/engine_opponent.py").read_text(encoding="utf-8"))
    engine_outcomes_tree = ast.parse(Path("src/analysis/tactical/engine_outcomes.py").read_text(encoding="utf-8"))
    engine_scoring_tree = ast.parse(Path("src/analysis/tactical/engine_scoring.py").read_text(encoding="utf-8"))
    engine_presentation_tree = ast.parse(Path("src/analysis/tactical/engine_presentation.py").read_text(encoding="utf-8"))
    engine_runtime_tree = ast.parse(Path("src/analysis/tactical/engine_runtime.py").read_text(encoding="utf-8"))
    engine_flow_tree = ast.parse(Path("src/analysis/tactical/engine_recommendation_flow.py").read_text(encoding="utf-8"))

    engine_class = next(
        node for node in engine_tree.body
        if isinstance(node, ast.ClassDef) and node.name == "TacticalEngine"
    )
    engine_source = Path("src/analysis/tactical_engine.py").read_text(encoding="utf-8")
    scoring_source = Path("src/analysis/tactical/action_scoring.py").read_text(encoding="utf-8")
    action_defs = {node.name for node in action_tree.body if isinstance(node, ast.FunctionDef)}
    damage_defs = {
        node.name
        for node in damage_tree.body
        if isinstance(node, (ast.FunctionDef, ast.ClassDef))
    }
    opponent_defs = {node.name for node in opponent_tree.body if isinstance(node, ast.FunctionDef)}
    runtime_defs = {node.name for node in runtime_tree.body if isinstance(node, ast.FunctionDef)}
    scoring_defs = {node.name for node in scoring_tree.body if isinstance(node, ast.FunctionDef)}
    detail_builder_defs = {
        node.name
        for node in detail_builder_tree.body
        if isinstance(node, ast.FunctionDef)
    }
    outcome_scoring_defs = {
        node.name
        for node in outcome_scoring_tree.body
        if isinstance(node, (ast.FunctionDef, ast.ClassDef))
    }
    non_damage_defs = {node.name for node in non_damage_tree.body if isinstance(node, ast.FunctionDef)}
    hook_signal_defs = {node.name for node in hook_signal_tree.body if isinstance(node, ast.FunctionDef)}
    details_defs = {node.name for node in details_tree.body if isinstance(node, ast.FunctionDef)}
    reason_defs = {node.name for node in reason_tree.body if isinstance(node, ast.FunctionDef)}
    metrics_defs = {node.name for node in metrics_tree.body if isinstance(node, ast.FunctionDef)}
    outcomes_defs = {node.name for node in outcomes_tree.body if isinstance(node, ast.FunctionDef)}
    switch_defs = {
        node.name
        for node in switch_tree.body
        if isinstance(node, (ast.FunctionDef, ast.ClassDef))
    }
    threats_defs = {
        node.name
        for node in threats_tree.body
        if isinstance(node, (ast.FunctionDef, ast.ClassDef))
    }
    recommendations_defs = {
        node.name
        for node in recommendations_tree.body
        if isinstance(node, (ast.FunctionDef, ast.ClassDef))
    }
    recommendation_builder_defs = {
        node.name
        for node in recommendation_builder_tree.body
        if isinstance(node, (ast.FunctionDef, ast.ClassDef))
    }
    confidence_defs = {node.name for node in confidence_tree.body if isinstance(node, ast.FunctionDef)}
    score_factory_defs = {node.name for node in score_factory_tree.body if isinstance(node, ast.FunctionDef)}
    action_presentation_defs = {
        node.name
        for node in action_presentation_tree.body
        if isinstance(node, ast.FunctionDef)
    }
    recommendation_presentation_defs = {
        node.name
        for node in recommendation_presentation_tree.body
        if isinstance(node, ast.FunctionDef)
    }
    engine_methods = {node.name for node in engine_class.body if isinstance(node, ast.FunctionDef)}
    engine_bases = {
        base.id
        for base in engine_class.bases
        if isinstance(base, ast.Name)
    }

    def class_methods(tree: ast.AST, class_name: str) -> set[str]:
        klass = next(
            node for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == class_name
        )
        return {node.name for node in klass.body if isinstance(node, ast.FunctionDef)}

    action_mixin_methods = class_methods(engine_action_tree, "TacticalActionMixin")
    opponent_mixin_methods = class_methods(engine_opponent_tree, "TacticalOpponentMixin")
    outcome_mixin_methods = class_methods(engine_outcomes_tree, "TacticalOutcomeMixin")
    scoring_mixin_methods = class_methods(engine_scoring_tree, "TacticalScoringMixin")
    presentation_mixin_methods = class_methods(engine_presentation_tree, "TacticalPresentationMixin")
    runtime_mixin_methods = class_methods(engine_runtime_tree, "TacticalRuntimeMixin")
    engine_flow_defs = {node.name for node in engine_flow_tree.body if isinstance(node, ast.FunctionDef)}
    engine_imports = {
        alias.name
        for node in engine_tree.body
        if isinstance(node, ast.ImportFrom) and node.module == "src.analysis.tactical"
        for alias in node.names
    }

    assert {"enumerate_our_actions", "skills_from_pool"}.issubset(action_defs)
    assert {"TacticalDamageToolkit"}.issubset(damage_defs)
    assert {
        "predict_opponent_actions",
        "compute_skill_probabilities",
        "estimate_switch_probability",
        "annotate_opp_threat",
    }.issubset(opponent_defs)
    assert {
        "skill_runtime",
        "skill_cd_round",
        "resolve_action_energy_cost",
        "skill_priority_layer",
    }.issubset(runtime_defs)
    assert {
        "score_action",
        "score_non_damage_skill",
        "apply_hook_signal_modifiers",
        "generate_reason",
        "action_metrics",
        "battle_metrics",
    }.issubset(scoring_defs)
    assert {"build_action_detail", "display_damage"}.issubset(detail_builder_defs)
    assert {"ActionOutcomeScore", "score_expected_outcomes", "preview_damage"}.issubset(outcome_scoring_defs)
    assert {"score_non_damage_skill"}.issubset(non_damage_defs)
    assert {"apply_hook_signal_modifiers"}.issubset(hook_signal_defs)
    assert {"generate_reason", "action_metrics", "battle_metrics"}.issubset(details_defs)
    assert {"generate_reason", "switch_reason", "skill_reason", "is_high_damage"}.issubset(reason_defs)
    assert {"action_metrics", "battle_metrics", "active_speed", "speed_order"}.issubset(metrics_defs)
    details_source = Path("src/analysis/tactical/action_details.py").read_text(encoding="utf-8")
    assert "opp_max_hp_approx" not in details_source
    assert "speed_order =" not in details_source
    assert "living_my =" not in details_source
    assert "opp_max_hp_approx" not in scoring_source
    assert "for opp_act in opp_predicted" not in scoring_source
    assert "display_damage_dealt = calc_damage" not in scoring_source
    assert "top_threat_name and opp_active" not in scoring_source
    assert "\"expected_gain\"" not in scoring_source
    assert "\"unknowns\"" not in scoring_source
    assert "presentation.action_category" not in scoring_source
    assert "classify_skill_effect" not in scoring_source
    assert "signal_type\") == \"prefer_switch\"" not in scoring_source
    assert "energy_cost >= 3" not in scoring_source
    assert "\"stat_up\" in tags" not in scoring_source
    assert "hp_pct < 0.3" not in scoring_source
    assert "negative_buffs" not in scoring_source
    assert {
        "resolve_outcome",
        "resolve_skill_vs_skill",
        "resolve_switch_outcome",
        "resolve_opp_switch_outcome",
    }.issubset(outcomes_defs)
    assert {"normalize_pet_for_analysis", "SwitchTargetResolver"}.issubset(switch_defs)
    assert {"TargetOrderAssessor", "top_threat_name"}.issubset(threats_defs)
    assert {
        "assess_confidence",
        "action_score_from_detail",
        "score_action_candidates",
        "build_recommendation",
    }.issubset(recommendations_defs)
    assert {"build_recommendation"}.issubset(recommendation_builder_defs)
    assert {"assess_confidence"}.issubset(confidence_defs)
    assert {"action_score_from_detail", "score_action_candidates"}.issubset(score_factory_defs)
    recommendations_source = Path("src/analysis/tactical/recommendations.py").read_text(encoding="utf-8")
    assert "ActionScore(" not in recommendations_source
    assert "TacticalRecommendation(" not in recommendations_source
    assert "len(used) >= 3" not in recommendations_source
    assert "scored.sort" not in recommendations_source
    assert "presentation.primary_plan" not in recommendations_source
    assert {"recommend_from_state"}.issubset(engine_flow_defs)
    assert {
        "action_category",
        "expected_gain",
        "risk_summary",
        "action_unknowns",
        "has_visible_combat_stats",
        "action_confidence",
    }.issubset(action_presentation_defs)
    assert {
        "primary_plan",
        "build_warnings",
        "opponent_profile",
        "opp_action_reason",
    }.issubset(recommendation_presentation_defs)
    presentation_source = Path("src/analysis/tactical/presentation.py").read_text(encoding="utf-8")
    assert "damage_taken >= my_active" not in presentation_source
    assert "warnings.append" not in presentation_source
    assert "switch_prob = sum" not in presentation_source

    assert {
        "TacticalActionMixin",
        "TacticalOpponentMixin",
        "TacticalOutcomeMixin",
        "TacticalScoringMixin",
        "TacticalPresentationMixin",
        "TacticalRuntimeMixin",
    }.issubset(engine_bases)
    assert {"_enumerate_our_actions", "_skills_from_pool"}.issubset(action_mixin_methods)
    assert {
        "_predict_opp_actions",
        "_resolve_opp_skills",
        "_compute_skill_probabilities",
        "_estimate_switch_probability",
        "_opp_skill_source",
        "_annotate_opp_threat",
    }.issubset(opponent_mixin_methods)
    assert {
        "_resolve_outcome",
        "_resolve_skill_vs_skill",
        "_resolve_switch_outcome",
        "_resolve_opp_switch_outcome",
    }.issubset(outcome_mixin_methods)
    assert {
        "_score_action",
        "_evaluate_outcome",
        "_score_non_damage_skill",
        "_generate_reason",
        "_action_metrics",
        "_battle_metrics",
    }.issubset(scoring_mixin_methods)
    assert {
        "_action_category",
        "_expected_gain",
        "_risk_summary",
        "_action_unknowns",
        "_action_confidence",
        "_primary_plan",
        "_build_warnings",
        "_opponent_profile",
        "_opp_action_reason",
    }.issubset(presentation_mixin_methods)
    assert {
        "_calc_damage",
        "_skill_runtime",
        "_skill_cd_round",
        "_resolve_action_energy_cost",
        "_skill_priority_layer",
        "_type_matchup_score",
        "_normalize_pet_for_analysis",
        "_most_likely_switch_target",
        "_assess_confidence",
    }.issubset(runtime_mixin_methods)
    assert engine_methods.isdisjoint(
        action_mixin_methods
        | opponent_mixin_methods
        | outcome_mixin_methods
        | scoring_mixin_methods
        | presentation_mixin_methods
        | runtime_mixin_methods
    )
    assert "used_skills: Dict[int, int]" not in engine_source
    assert "def _compute_skill_probabilities(" not in engine_source
    assert "def _skill_priority_layer(" not in engine_source
    assert "re.search" not in engine_source
    assert "for opp_act in opp_predicted" not in engine_source
    assert "signal_type\") == \"prefer_switch\"" not in engine_source
    assert "if our_priority != opp_priority" not in engine_source
    assert "opp_hp -= our_damage" not in engine_source
    assert "CounterPicker" not in engine_source
    assert "same_battle_pet" not in engine_source
    assert "ThreatAssessor" not in engine_source
    assert "ActionScore(" not in engine_source
    assert "TacticalRecommendation(" not in engine_source
    assert "recommendations" not in engine_imports
    assert "recommendations.score_action_candidates(" not in engine_source
    assert "recommendations.build_recommendation(" not in engine_source
    assert "DamageCalculator" not in engine_source
    assert "DamagePredictionService" not in engine_source
    assert "register_innate_hooks" not in engine_source
    assert "tactical_total" not in engine_source


def test_event_formatter_lifecycle_and_merge_live_in_formatting_modules():
    formatter_tree = ast.parse(Path("src/analysis/event_formatter.py").read_text(encoding="utf-8"))
    lifecycle_tree = ast.parse(Path("src/analysis/formatting/lifecycle.py").read_text(encoding="utf-8"))
    merge_tree = ast.parse(Path("src/analysis/formatting/merge.py").read_text(encoding="utf-8"))
    core_tree = ast.parse(Path("src/analysis/formatting/core.py").read_text(encoding="utf-8"))
    dispatch_tree = ast.parse(Path("src/analysis/formatting/entry_dispatch.py").read_text(encoding="utf-8"))

    formatter_defs = {node.name for node in formatter_tree.body if isinstance(node, ast.FunctionDef)}
    lifecycle_defs = {node.name for node in lifecycle_tree.body if isinstance(node, ast.FunctionDef)}
    merge_defs = {node.name for node in merge_tree.body if isinstance(node, ast.FunctionDef)}
    core_defs = {
        node.name
        for node in core_tree.body
        if isinstance(node, (ast.FunctionDef, ast.ClassDef))
    }

    lifecycle_only = {
        "format_battle_enter",
        "format_round_start",
        "format_battle_finish",
        "format_skill_select",
        "format_skill_declare",
        "format_action_ack",
        "format_special_refresh",
        "format_round_flow",
    }
    dispatch_defs = {node.name for node in dispatch_tree.body if isinstance(node, ast.FunctionDef)}

    assert formatter_defs.isdisjoint(lifecycle_only)
    assert lifecycle_only.issubset(lifecycle_defs)
    assert "format_action_entry" not in formatter_defs
    assert "format_action_entry" in dispatch_defs
    assert "merge_damage_events" in merge_defs
    assert {"FormattedEvent", "side_label", "is_mine", "resolve_pet_name"}.issubset(core_defs)


def test_action_entry_formatters_live_in_formatting_entry_modules():
    formatter_tree = ast.parse(Path("src/analysis/event_formatter.py").read_text(encoding="utf-8"))
    formatter_defs = {node.name for node in formatter_tree.body if isinstance(node, ast.FunctionDef)}
    assert not any(name.startswith("_fmt_") for name in formatter_defs)

    module_expectations = {
        "entries_combat.py": {"format_skill_cast", "format_damage", "format_defeat"},
        "entries_effects.py": {
            "format_effect_apply",
            "format_effect_stage",
            "format_effect_link",
            "format_effect_trigger",
            "format_buff_trigger",
        },
        "entries_resources.py": {
            "format_heal",
            "format_energy",
            "format_sp_energy_change",
            "format_sp_energy_trigger",
            "format_use_item",
        },
        "entries_pet.py": {"format_change_pet", "format_revive", "format_supply_pet", "format_change_model"},
        "entries_misc.py": {
            "format_ai_action",
            "format_pvp_perform_marker",
            "format_weather_change",
            "format_skill_state",
            "format_role_skill_cast",
            "format_special_move",
            "format_skill_pos_change",
            "format_idle",
            "format_notify_perform",
            "format_cmd_failed",
            "format_runaway",
        },
    }

    for filename, expected_defs in module_expectations.items():
        tree = ast.parse(Path("src/analysis/formatting", filename).read_text(encoding="utf-8"))
        module_defs = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
        assert expected_defs.issubset(module_defs)
