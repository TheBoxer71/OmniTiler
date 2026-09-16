import QtQuick
import Quickshell.Io

Item {
    id: root
    property var shell: null
    property var manifest: null
    property bool ready: false
    property bool stopping: false
    property string pendingCommand: ""
    property var state: ({ active: false, workspaces: [], occupancy: {}, error: "" })
    readonly property bool active: !!state.active

    function send(command) {
        if (!ready) {
            pendingCommand = command
            if (!worker.running) worker.running = true
            return "starting"
        }
        worker.write(JSON.stringify({ command: command }) + "\n")
        return "ok"
    }
    function activate() { return send("activate") }
    function deactivate() { return send("deactivate") }
    function toggle() { return send("toggle") }
    function status() { return JSON.stringify(state) }

    Process {
        id: worker
        command: ["python3", "-u", decodeURIComponent(Qt.resolvedUrl("engine.py").toString().replace(/^file:\/\//, ""))]
        stdinEnabled: true
        stdout: SplitParser {
            onRead: function(data) {
                try {
                    root.state = JSON.parse(data)
                    root.ready = true
                    if (root.pendingCommand) {
                        let next = root.pendingCommand
                        root.pendingCommand = ""
                        root.send(next)
                    }
                } catch (e) { console.warn("OmniTiler: invalid helper response", e) }
            }
        }
        stderr: SplitParser {
            onRead: function(data) { console.warn("OmniTiler:", data) }
        }
        onExited: function(exitCode) {
            root.ready = false
            if (!root.stopping) {
                root.state = { active: false, workspaces: [], occupancy: {},
                    error: "Helper stopped (" + exitCode + "). Click to recover and retry." }
            }
        }
    }
    Component.onCompleted: worker.running = true
    Component.onDestruction: {
        stopping = true
        if (worker.running) worker.write('{"command":"shutdown"}\n')
    }

    IpcHandler {
        target: "omnitiler"
        function activate(): string { return root.activate() }
        function deactivate(): string { return root.deactivate() }
        function toggle(): string { return root.toggle() }
        function status(): string { return root.status() }
    }
}
