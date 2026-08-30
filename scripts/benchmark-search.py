#!/usr/bin/python3
# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Benchmark KDE server search against Proton's existing local cache."""

from __future__ import annotations

import argparse
import asyncio
from collections import Counter
import json
from pathlib import Path
from statistics import median
from time import perf_counter
from types import SimpleNamespace
import tracemalloc

from proton.vpn.core.cache_handler import CacheHandler
from proton.vpn.session.servers.logicals import (
    ServerList,
    _server_string_object_hook,
)
from proton.vpn.session.servers.server_list_fetcher import ServerListFetcher

from proton_vpn_kde_backend.adapters import ProtonCoreAdapter


class _CachedRefresher:
    def __init__(self, server_list: ServerList):
        self._server_list = server_list

    async def get_up_to_date_server_list(self) -> ServerList:
        return self._server_list


async def benchmark(cache_path: Path, iterations: int, queries: list[str]) -> dict:
    load_started = perf_counter()
    payload = CacheHandler(
        cache_path, object_hook_factory=_server_string_object_hook
    ).load()
    if not payload:
        raise RuntimeError(f"No valid Proton server cache found at {cache_path}")
    server_list = ServerList.from_dict(payload)
    load_milliseconds = (perf_counter() - load_started) * 1000
    adapter = ProtonCoreAdapter(
        SimpleNamespace(refresher=_CachedRefresher(server_list))
    )

    projection_started = perf_counter()
    await adapter.search_locations(queries[0])
    projection_milliseconds = (perf_counter() - projection_started) * 1000

    results = []
    for query in queries:
        samples = []
        for _ in range(iterations):
            started = perf_counter()
            matches = await adapter.search_locations(query)
            samples.append((perf_counter() - started) * 1000)
        ordered = sorted(samples)
        results.append(
            {
                "query": query,
                "medianMilliseconds": round(median(samples), 3),
                "p95Milliseconds": round(
                    ordered[max(0, int(len(ordered) * 0.95) - 1)], 3
                ),
                "maximumMilliseconds": round(max(samples), 3),
                "resultCounts": dict(Counter(item.kind for item in matches)),
            }
        )

    projection = adapter._search_projection  # pylint: disable=protected-access

    memory_adapter = ProtonCoreAdapter(
        SimpleNamespace(refresher=_CachedRefresher(server_list))
    )
    tracemalloc.start()
    await memory_adapter.search_locations(queries[0])
    projection_current_bytes, projection_peak_bytes = (
        tracemalloc.get_traced_memory()
    )
    tracemalloc.stop()
    return {
        "cacheBytes": cache_path.stat().st_size,
        "cacheLoadMilliseconds": round(load_milliseconds, 3),
        "logicalServerCount": len(server_list.logicals),
        "projectionBuildAndFirstQueryMilliseconds": round(
            projection_milliseconds, 3
        ),
        "projectedLocationCount": projection.location_count,
        "projectedServerCount": projection.server_count,
        "projectionCurrentBytes": projection_current_bytes,
        "projectionPeakBuildBytes": projection_peak_bytes,
        "iterations": iterations,
        "queries": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cache",
        type=Path,
        default=ServerListFetcher.CACHE_PATH,
        help="existing Proton serverlist.json path",
    )
    parser.add_argument("--iterations", type=int, default=30)
    parser.add_argument(
        "queries",
        nargs="*",
        default=["ch", "zur", "us-", "#1", "a", "zzzznotfound"],
    )
    arguments = parser.parse_args()
    if not 1 <= arguments.iterations <= 1000:
        parser.error("--iterations must be from 1 through 1000")
    try:
        report = asyncio.run(
            benchmark(arguments.cache, arguments.iterations, arguments.queries)
        )
    except (OSError, RuntimeError, ValueError) as error:
        parser.exit(1, f"error: {error}\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
