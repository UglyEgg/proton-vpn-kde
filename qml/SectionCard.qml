import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.AbstractCard {
    id: root

    default property alias bodyData: body.data
    property string title
    property string description
    property string iconName
    property color iconColor: Kirigami.Theme.textColor

    Layout.fillWidth: true
    Accessible.name: title

    contentItem: ColumnLayout {
        spacing: Kirigami.Units.largeSpacing

        RowLayout {
            Layout.fillWidth: true
            visible: root.title.length > 0 || root.description.length > 0
            spacing: Kirigami.Units.largeSpacing

            Kirigami.Icon {
                visible: root.iconName.length > 0
                source: root.iconName
                color: root.iconColor
                implicitWidth: Kirigami.Units.iconSizes.medium
                implicitHeight: implicitWidth
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: Kirigami.Units.smallSpacing

                Kirigami.Heading {
                    Layout.fillWidth: true
                    visible: root.title.length > 0
                    level: 2
                    text: root.title
                    wrapMode: Text.WordWrap
                }

                Controls.Label {
                    Layout.fillWidth: true
                    visible: root.description.length > 0
                    text: root.description
                    color: Kirigami.Theme.disabledTextColor
                    wrapMode: Text.WordWrap
                }
            }
        }

        ColumnLayout {
            id: body
            Layout.fillWidth: true
            spacing: Kirigami.Units.smallSpacing
        }
    }
}
