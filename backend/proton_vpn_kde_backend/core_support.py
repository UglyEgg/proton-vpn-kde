# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Official Proton support and survey API workflows used by the adapter."""

from __future__ import annotations

import asyncio
from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from . import __version__
from .controller import NpsSurveyResponse, SupportReport
from .errors import UserVisibleRuntimeError
from .support import collect_support_logs


async def submit_support_report(api: Any, report: SupportReport) -> None:
    from proton.vpn.session.dataclasses import BugReportForm

    with TemporaryDirectory(prefix="proton-vpn-kde-support-") as directory:
        log_paths = (
            await asyncio.to_thread(collect_support_logs, Path(directory))
            if report.include_logs
            else []
        )
        with ExitStack() as attachments:
            report_form = BugReportForm(
                username=report.username,
                email=report.email,
                title="Report from KDE Plasma app",
                description=report.description,
                client_version=__version__,
                client="KDE Plasma GUI",
                attachments=[
                    attachments.enter_context(path.open("rb")) for path in log_paths
                ],
            )
            try:
                await api.submit_bug_report(report_form)
            except Exception:
                raise UserVisibleRuntimeError(
                    "Proton could not submit the issue report"
                ) from None


async def take_pending_nps_survey(api: Any) -> bool:
    try:
        notifications = list(
            api.refresher.notifications.get_nps_survey_notifications()
        )
    except AttributeError:
        return False
    while notifications:
        survey = notifications.pop()
        if not survey.seen and survey.is_active:
            await asyncio.to_thread(api.set_notification_seen, survey.survey_id)
            return True
    return False


async def submit_nps_survey(api: Any, response: NpsSurveyResponse) -> None:
    from proton.vpn.session.dataclasses import NPSSurveyResponse

    response_type = (
        NPSSurveyResponse.ResponseType.DISMISS
        if response.dismissed
        else NPSSurveyResponse.ResponseType.SUBMIT
    )
    try:
        await api.submit_nps_response(
            NPSSurveyResponse(
                user_score=response.score,
                user_comments=response.comments,
                response_type=response_type,
            )
        )
    except Exception:
        raise UserVisibleRuntimeError(
            "Proton could not submit the survey response"
        ) from None
