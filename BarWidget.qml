import QtQuick
import qs.Ui
import qs.Commons

BarWidget {
    id: root
    moduleName: "fredrick.omnitiler"
    property var service: null
    implicitWidth: button.implicitWidth
    implicitHeight: barSize

    // Service registration can finish after the widget is instantiated.
    function findService() {
        service = bar && bar.shell ? bar.shell.serviceFor(moduleName) : null
    }
    Component.onCompleted: findService()
    onBarChanged: findService()
    Timer { interval: 1000; running: true; repeat: true; onTriggered: root.findService() }

    function tooltip() {
        if (!service) return "OmniTiler · Starting…"
        let s = service.state
        let lines = ["OmniTiler · " + (s.active ? "On · " + s.monitor : "Off"),
            "30% left · 40% center · 30% right"]
        if (s.active) {
            for (let i = 0; i < s.workspaces.length; i++) {
                let w = s.workspaces[i]
                let slots = s.occupancy[String(w)] || {}
                lines.push("Workspace " + w + ": " +
                    ["center", "left", "right"].map(function(k) {
                        return k + (slots[k] ? " ●" : " ○")
                    }).join("  "))
            }
        }
        if (s.error) lines.push(s.error)
        lines.push("Super+Shift+←/→ to move or swap columns")
        lines.push("Click to " + (s.active ? "restore normal tiling" : "tile this workspace"))
        return lines.join("\n")
    }

    BarIconButton {
        id: button
        bar: root.bar
        active: root.service ? root.service.active : false
        activeColor: Color.accent
        dimmed: !active
        tooltipText: root.tooltip()
        onPressed: function(mouseButton) {
            if (mouseButton === Qt.LeftButton && root.service) root.service.toggle()
        }
        iconComponent: Component {
            Item {
                Row {
                    anchors.centerIn: parent
                    spacing: 2
                    Repeater {
                        model: [4, 6, 4]
                        Rectangle {
                            required property int modelData
                            required property int index
                            width: modelData
                            height: 13
                            radius: 1
                            color: button.active && index === 1 ? Color.accent : "transparent"
                            border.width: 1
                            border.color: button.active ? Color.accent : button.foreground
                        }
                    }
                }
            }
        }
    }
}
