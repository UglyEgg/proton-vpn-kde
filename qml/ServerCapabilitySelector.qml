import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Flow {
    id: root

    property var selectedFeatures: []
    signal selectionChanged(var features)

    Layout.fillWidth: true
    Layout.preferredHeight: childrenRect.height
    spacing: Kirigami.Units.largeSpacing

    function updateFeature(feature, checked) {
        const supported = ["p2p", "streaming", "tor", "secure-core"]
        const requested = []
        for (const candidate of supported) {
            if ((candidate === feature && checked)
                    || (candidate !== feature
                        && root.selectedFeatures.indexOf(candidate) >= 0)) {
                requested.push(candidate)
            }
        }
        root.selectionChanged(requested)
    }

    Controls.CheckBox {
        text: qsTr("P2P")
        checked: root.selectedFeatures.indexOf("p2p") >= 0
        onToggled: root.updateFeature("p2p", checked)
    }

    Controls.CheckBox {
        text: qsTr("Streaming")
        checked: root.selectedFeatures.indexOf("streaming") >= 0
        onToggled: root.updateFeature("streaming", checked)
    }

    Controls.CheckBox {
        text: qsTr("Tor")
        checked: root.selectedFeatures.indexOf("tor") >= 0
        onToggled: root.updateFeature("tor", checked)
    }

    Controls.CheckBox {
        text: qsTr("Secure Core")
        checked: root.selectedFeatures.indexOf("secure-core") >= 0
        onToggled: root.updateFeature("secure-core", checked)
    }
}
