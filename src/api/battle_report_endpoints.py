"""Battle report endpoint helpers.

Routes keep the URL wiring; this module owns report id decoding, report service
calls, HTTP error translation, and download response construction.
"""
from __future__ import annotations

import urllib.parse
from typing import Callable, Optional, Tuple

from fastapi import HTTPException
from fastapi.responses import Response

from src.analysis.battle_report import (
    BattleReportError,
    build_report_diagnostics,
    get_report_package,
    get_report_summary,
    scan_report_summaries,
)


def list_battle_reports_payload(
    *,
    scan_fn: Optional[Callable] = None,
    diagnostics_fn: Optional[Callable] = None,
) -> dict:
    scan_fn = scan_fn or scan_report_summaries
    diagnostics_fn = diagnostics_fn or build_report_diagnostics
    reports = scan_fn()
    diagnostics = diagnostics_fn(reports=reports)
    return {
        "reports": [report.__dict__ for report in reports],
        "diagnostics": diagnostics.__dict__,
    }


def get_battle_report_payload(
    report_id: str,
    *,
    summary_fn: Optional[Callable] = None,
) -> dict:
    summary_fn = summary_fn or get_report_summary
    try:
        return summary_fn(urllib.parse.unquote(report_id)).__dict__
    except BattleReportError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def download_battle_report_response(
    report_id: str,
    *,
    package_fn: Optional[Callable[[str], Tuple[str, bytes]]] = None,
) -> Response:
    package_fn = package_fn or get_report_package
    try:
        filename, payload = package_fn(urllib.parse.unquote(report_id))
    except BattleReportError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(
        content=payload,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Report-Filename": filename,
        },
    )
