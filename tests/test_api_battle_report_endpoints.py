"""Battle report endpoint helper tests."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from src.analysis.battle_report import BattleReportError
from src.api.battle_report_endpoints import (
    download_battle_report_response,
    get_battle_report_payload,
    list_battle_reports_payload,
)


def test_list_battle_reports_payload_uses_report_and_diagnostic_shapes():
    summary = SimpleNamespace(report_id="session:1", complete=True)
    diagnostics = SimpleNamespace(report_count=1, has_battle_enter=True)

    payload = list_battle_reports_payload(
        scan_fn=lambda: [summary],
        diagnostics_fn=lambda reports=None: diagnostics,
    )

    assert payload == {
        "reports": [{"report_id": "session:1", "complete": True}],
        "diagnostics": {"report_count": 1, "has_battle_enter": True},
    }


def test_get_battle_report_payload_decodes_id_and_translates_not_found():
    seen = []

    payload = get_battle_report_payload(
        "session%3A1",
        summary_fn=lambda report_id: seen.append(report_id) or SimpleNamespace(report_id=report_id),
    )

    assert payload == {"report_id": "session:1"}
    assert seen == ["session:1"]

    def _raise(_report_id: str):
        raise BattleReportError("missing")

    with pytest.raises(HTTPException) as exc_info:
        get_battle_report_payload("missing%3A1", summary_fn=_raise)
    assert exc_info.value.status_code == 404


def test_download_battle_report_response_keeps_zip_headers_and_404_translation():
    response = download_battle_report_response(
        "session%3A1",
        package_fn=lambda report_id: (f"{report_id}.raco-report", b"zip"),
    )

    assert response.media_type == "application/zip"
    assert response.headers["x-report-filename"] == "session:1.raco-report"
    assert response.body == b"zip"

    def _raise(_report_id: str):
        raise BattleReportError("missing")

    with pytest.raises(HTTPException) as exc_info:
        download_battle_report_response("missing%3A1", package_fn=_raise)
    assert exc_info.value.status_code == 404
