import QtQuick
import org.kde.kirigami as Kirigami

Kirigami.AboutPage {
    aboutData: {
        "displayName": qsTr("Proton VPN for Plasma"),
        "productName": "proton-vpn-kde/client",
        "componentName": "proton-vpn-kde",
        "desktopFileName": "proton-vpn-kde",
        "programLogo": "proton-vpn-kde",
        "shortDescription": qsTr("A native KDE Plasma client using Proton's official VPN core"),
        "homepage": "https://protonvpn.com/",
        "bugAddress": "https://protonvpn.com/support-form",
        "version": appVersion,
        "otherText": qsTr("The Qt and Kirigami frontend is independent community work. Networking, VPN protocols, account sessions, kill switch, and split tunneling remain provided by Proton's official open-source Linux core."),
        "authors": [
            {
                "name": "uglyegg",
                "task": qsTr("Plasma client development"),
                "emailAddress": "uglyegg@entropy.quest",
                "webAddress": "",
                "ocsUsername": ""
            }
        ],
        "credits": [],
        "translators": [],
        "licenses": [
            {
                "name": "GNU GPL v3 or later",
                "text": qsTr("This program is free software under the GNU General Public License, version 3 or any later version. The complete license is included with the source and installed package documentation."),
                "spdx": "GPL-3.0-or-later"
            }
        ],
        "copyrightStatement": "© 2026 uglyegg and contributors"
    }
    getInvolvedUrl: ""
    donateUrl: ""
}
