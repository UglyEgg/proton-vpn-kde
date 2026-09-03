# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Official Proton support and survey API workflows used by the adapter."""

from __future__ import annotations

from contextlib import ExitStack
from functools import partial
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from . import __version__
from .async_utils import await_owned, run_in_daemon_thread
from .controller import NpsSurveyResponse, SupportReport
from .errors import (
    NpsCompletionUnknownError,
    UserVisibleRuntimeError,
    is_proton_authentication_needed,
)
from .support import collect_support_logs


async def submit_support_report(api: Any, report: SupportReport) -> None:
    from proton.vpn.session.dataclasses import BugReportForm

    with TemporaryDirectory(prefix="proton-vpn-kde-support-") as directory:
        log_paths = (
            await run_in_daemon_thread(
                lambda: collect_support_logs(Path(directory))
            )
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
            except Exception as error:
                if is_proton_authentication_needed(error):
                    raise
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
            # Core writes its local JSON cache synchronously. Keep filesystem
            # work off the D-Bus event loop, but retain task ownership through
            # cancellation so teardown cannot overtake the cache mutation.
            survey_id = survey.survey_id
            await await_owned(
                run_in_daemon_thread(
                    partial(api.set_notification_seen, survey_id)
                )
            )
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
    except Exception as error:
        if is_proton_authentication_needed(error):
            raise
        raise NpsCompletionUnknownError(
            "Survey submission completion could not be confirmed"
        ) from None
