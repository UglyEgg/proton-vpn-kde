# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from pathlib import Path
import unittest
from unittest.mock import Mock
import xml.etree.ElementTree as ET

from proton_vpn_kde_backend.dbus_contract import (
    ALL_SIGNALS,
    BUS_NAME,
    CLASSIFIED_METHODS,
    INTERFACE_NAME,
    OBJECT_PATH,
)
from proton_vpn_kde_backend.dbus_service import VpnDbusService


CONTRACT_PATH = (
    Path(__file__).parents[2]
    / "data"
    / "dbus"
    / "quest.entropy.PlasmaVPN.Backend1.xml"
)
BUS_ANNOTATION = "quest.entropy.PlasmaVPN.BusName"


def signature(element: ET.Element, direction: str) -> str:
    return "".join(
        argument.attrib["type"]
        for argument in element.findall("arg")
        if argument.attrib.get("direction", "in") == direction
    )


class DbusContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.node = ET.parse(CONTRACT_PATH).getroot()
        interfaces = self.node.findall("interface")
        self.assertEqual(1, len(interfaces))
        self.interface = interfaces[0]

    def test_generated_identity_and_policy_cover_the_xml_contract(self):
        bus_annotation = self.interface.find(
            f"annotation[@name='{BUS_ANNOTATION}']"
        )
        self.assertIsNotNone(bus_annotation)
        assert bus_annotation is not None
        self.assertEqual(BUS_NAME, bus_annotation.attrib["value"])
        self.assertEqual(OBJECT_PATH, self.node.attrib["name"])
        self.assertEqual(INTERFACE_NAME, self.interface.attrib["name"])
        self.assertEqual(
            CLASSIFIED_METHODS,
            {method.attrib["name"] for method in self.interface.findall("method")},
        )
        self.assertEqual(
            ALL_SIGNALS,
            {signal.attrib["name"] for signal in self.interface.findall("signal")},
        )

    def test_python_service_signatures_match_the_xml_contract(self):
        service_interface = VpnDbusService(Mock()).introspect()
        xml_methods = {
            method.attrib["name"]: (
                signature(method, "in"),
                signature(method, "out"),
            )
            for method in self.interface.findall("method")
        }
        runtime_methods = {
            method.name: (method.in_signature, method.out_signature)
            for method in service_interface.methods
        }
        xml_signals = {
            signal_element.attrib["name"]: "".join(
                argument.attrib["type"]
                for argument in signal_element.findall("arg")
            )
            for signal_element in self.interface.findall("signal")
        }
        runtime_signals = {
            signal_definition.name: signal_definition.signature
            for signal_definition in service_interface.signals
        }

        self.assertEqual(INTERFACE_NAME, service_interface.name)
        self.assertEqual(xml_methods, runtime_methods)
        self.assertEqual(xml_signals, runtime_signals)


if __name__ == "__main__":
    unittest.main()
