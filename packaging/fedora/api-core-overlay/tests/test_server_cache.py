# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

"""Offline cache/string-sharing contracts against an explicitly selected Core."""

import argparse
import importlib
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch


CACHE = LOGICALS = FETCHER = None


class ServerCacheTests(unittest.TestCase):
    def setUp(self):
        if CACHE is None:
            self.skipTest("Explicit extracted Core required; RPM %check supplies --root")
        temporary = self.enterContext(TemporaryDirectory())
        self.path = Path(temporary) / "cache" / "servers.json"
        self.data = {
            "LogicalServers": [
                {"ExitCountry": "CH", "Domain": "fixture.example", "Load": 42,
                 "Servers": [{"Domain": "fixture.example", "EntryIP": "192.0.2.1"}]},
                {"ExitCountry": "CH", "Domain": "fixture.example", "Load": 17,
                 "Servers": [{"Domain": "fixture.example", "EntryIP": "192.0.2.1"}]},
            ],
            "Other": [True, None, 7, "unchanged"],
        }

    def shared_cache(self):
        return CACHE.CacheHandler(
            str(self.path), object_hook_factory=LOGICALS._server_string_object_hook
        )

    def test_plain_json_cache_keeps_vendor_roundtrip_and_removal(self):
        cache = CACHE.CacheHandler(str(self.path))
        self.assertIsNone(cache.load())
        cache.save(self.data)
        self.assertEqual(self.data, cache.load())
        self.assertEqual(json.dumps(self.data, indent=4).encode(), self.path.read_bytes())
        cache.remove()
        cache.remove()
        self.assertFalse(cache.exists)

    def test_json_decode_shares_strings_without_changing_values(self):
        cache = self.shared_cache()
        cache.save(self.data)
        decoded = cache.load()
        self.assertEqual(self.data, decoded)
        first, second = decoded["LogicalServers"]
        for field in ("ExitCountry", "Domain"):
            self.assertIs(first[field], second[field])
        self.assertIs(first["Domain"], first["Servers"][0]["Domain"])

    def test_each_load_has_an_independent_string_pool(self):
        cache = self.shared_cache()
        cache.save(self.data)
        first = cache.load()["LogicalServers"][0]["Domain"]
        second = cache.load()["LogicalServers"][0]["Domain"]
        self.assertEqual(first, second)
        self.assertIsNot(first, second)

    def test_factory_is_created_per_successful_read(self):
        factories = []

        def factory():
            hook = LOGICALS._server_string_object_hook()
            factories.append(hook)
            return hook

        cache = CACHE.CacheHandler(str(self.path), object_hook_factory=factory)
        self.assertIsNone(cache.load())
        self.assertEqual([], factories)
        cache.save(self.data)
        cache.load()
        cache.load()
        self.assertEqual(2, len(factories))
        self.assertIsNot(factories[0], factories[1])

    def test_malformed_json_and_invalid_utf8_preserve_vendor_behavior(self):
        raw = CACHE.BinaryCacheHandler(str(self.path))
        for contents in (b"{invalid", b"\xff\xfe"):
            with self.subTest(contents=contents):
                raw.save(contents)
                with patch.object(CACHE.logger, "warning") as warning:
                    self.assertIsNone(CACHE.CacheHandler(str(self.path)).load())
                    self.assertIsNone(self.shared_cache().load())
                self.assertEqual(2, warning.call_count)

    def test_binary_cache_is_not_json_decoded(self):
        raw = CACHE.BinaryCacheHandler(str(self.path))
        self.assertIsNone(raw.load())
        contents = b"\x00\xff\x01binary-status"
        raw.save(contents)
        self.assertEqual(contents, raw.load())
        raw.remove()
        self.assertFalse(raw.exists)

    def test_fetcher_keeps_injected_json_and_binary_caches(self):
        json_cache = self.shared_cache()
        raw = CACHE.BinaryCacheHandler(str(self.path.with_name("binary_status")))
        fetcher = FETCHER.ServerListFetcher(
            session=object(), cache_file=json_cache, binary_status_cache_file=raw
        )
        self.assertIs(json_cache, fetcher._cache_file)
        self.assertIs(raw, fetcher._binary_status_cache_file)
        json_cache.save(self.data)
        raw.save(b"fixture")
        fetcher.clear_cache()
        self.assertFalse(json_cache.exists)
        self.assertFalse(raw.exists)

    def test_fresh_list_handles_absent_and_non_string_fields(self):
        data = [{"City": None, "State": 42, "Servers": [{"Domain": None}]}, {}]
        LOGICALS._deduplicate_server_strings(data)
        self.assertEqual(
            [{"City": None, "State": 42, "Servers": [{"Domain": None}]}, {}], data
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    options, remaining = parser.parse_known_args()
    site_packages = options.root.resolve() / "usr/lib64/python3.14/site-packages"
    sys.path.insert(0, str(site_packages))
    with TemporaryDirectory(prefix="plasma-core-cache-test.") as directory:
        environment = {}
        for name in ("XDG_CACHE_HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_RUNTIME_DIR"):
            path = Path(directory) / name.lower()
            path.mkdir(mode=0o700)
            environment[name] = str(path)
        with patch.dict(os.environ, environment):
            CACHE = importlib.import_module("proton.vpn.core.cache_handler")
            LOGICALS = importlib.import_module("proton.vpn.session.servers.logicals")
            FETCHER = importlib.import_module("proton.vpn.session.servers.server_list_fetcher")
            for module in (CACHE, LOGICALS, FETCHER):
                if not Path(module.__file__).resolve().is_relative_to(site_packages):
                    raise RuntimeError("Imported Core differs from the selected fixture")
            unittest.main(argv=[str(Path(__file__)), *remaining])
