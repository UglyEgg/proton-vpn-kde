# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import asyncio
import threading
import unittest

from proton_vpn_kde_backend.async_utils import run_in_daemon_thread


class DaemonThreadTests(unittest.IsolatedAsyncioTestCase):
    async def test_cancellation_does_not_wait_for_provider_prompt(self):
        started = threading.Event()
        released = threading.Event()

        def blocking_prompt():
            started.set()
            released.wait(timeout=2)
            return True

        task = asyncio.create_task(run_in_daemon_thread(blocking_prompt))
        try:
            for _ in range(100):
                if started.is_set():
                    break
                await asyncio.sleep(0.005)
            self.assertTrue(started.is_set())

            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await asyncio.wait_for(task, timeout=0.1)
        finally:
            released.set()
