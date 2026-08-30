"""Compact, generation-scoped projection for interactive server search."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
import unicodedata

from .controller import LocationSearchInfo


def fold_search_text(value: str) -> str:
    """Case-fold text and remove combining marks for accent-insensitive search."""
    normalized = unicodedata.normalize("NFKD", value.casefold())
    return "".join(
        character for character in normalized if not unicodedata.combining(character)
    )


@dataclass(frozen=True, slots=True)
class _LocationRecord:
    name: str
    folded_name: str
    country_code: str
    server_names: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _ServerRecord:
    name: str
    folded_name: str
    country_code: str
    location: str
    secure_core: bool


class ServerSearchProjection:
    """Searchable immutable scalars derived from one Proton topology generation.

    The projection deliberately retains no Proton server or list objects. Mutable
    load and availability state is resolved from the current official list only
    for records that match a query.
    """

    def __init__(
        self,
        generation: int,
        locations: tuple[_LocationRecord, ...],
        servers: tuple[_ServerRecord, ...],
    ):
        self.generation = generation
        self._locations = locations
        self._servers = servers

    @property
    def location_count(self) -> int:
        return len(self._locations)

    @property
    def server_count(self) -> int:
        return len(self._servers)

    @classmethod
    def build(
        cls,
        server_list: Any,
        generation: int,
        secure_core_feature: Any,
        server_sort_key: Callable[[Any], str],
    ) -> ServerSearchProjection:
        location_servers: dict[tuple[str, str], list[str]] = {}
        ordered_servers: list[tuple[str, _ServerRecord]] = []
        shared_values: dict[str, str] = {}

        def share(value: str) -> str:
            return shared_values.setdefault(value, value)

        for server in server_list.logicals:
            name = server.name or ""
            if not name:
                continue
            country_code = share((server.exit_country or "").upper())
            location = share(server.location or "")
            if location:
                location_servers.setdefault((country_code, location), []).append(name)
            record = _ServerRecord(
                name=name,
                folded_name=fold_search_text(name),
                country_code=country_code,
                location=location,
                secure_core=secure_core_feature in server.features,
            )
            ordered_servers.append((server_sort_key(server), record))

        locations = tuple(
            sorted(
                (
                    _LocationRecord(
                        name=location,
                        folded_name=fold_search_text(location),
                        country_code=country_code,
                        server_names=tuple(server_names),
                    )
                    for (
                        country_code,
                        location,
                    ), server_names in location_servers.items()
                ),
                key=lambda record: (record.folded_name, record.country_code),
            )
        )
        ordered_servers.sort(key=lambda item: item[0])
        return cls(
            generation,
            locations,
            tuple(record for _, record in ordered_servers),
        )

    def search(self, server_list: Any, query: str) -> list[LocationSearchInfo]:
        needle = fold_search_text(query)
        location_results: list[LocationSearchInfo] = []
        for record in self._locations:
            if needle not in record.folded_name:
                continue
            active_servers = []
            for name in record.server_names:
                server = server_list.get_by_name(name)
                if not server.under_maintenance:
                    active_servers.append(server)
            if not active_servers:
                continue
            accessible = (
                next(
                    iter(
                        server_list.get_available_servers(
                            active_servers, server_list.user_tier
                        )
                    ),
                    None,
                )
                is not None
            )
            location_results.append(
                LocationSearchInfo(
                    kind="location",
                    name=record.name,
                    country_code=record.country_code,
                    group_name=record.name,
                    accessible=accessible,
                )
            )
            if len(location_results) == 100:
                break

        server_results: list[LocationSearchInfo] = []
        for record in self._servers:
            if needle not in record.folded_name:
                continue
            server = server_list.get_by_name(record.name)
            available = next(
                iter(
                    server_list.get_available_servers((server,), server_list.user_tier)
                ),
                None,
            )
            if available is None:
                continue
            server_results.append(
                LocationSearchInfo(
                    kind="server",
                    name=record.name,
                    country_code=record.country_code,
                    location=record.location,
                    group_kind=("secure-core" if record.secure_core else "location"),
                    group_name=(
                        "Via Secure Core" if record.secure_core else record.location
                    ),
                    load=available.load or 0,
                )
            )
            if len(server_results) == 100:
                break

        return [*location_results, *server_results]
