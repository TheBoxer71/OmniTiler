"""Opt-in lifecycle checks with a single disposable terminal and theme restoration."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from live_smoke import ROOT, Hyprland, ipc, wait_for


def run(*args):
    return subprocess.run(args, text=True, capture_output=True, check=True, timeout=60).stdout.strip()


def main():
    if sys.argv[1:] != ["--run"]:
        raise SystemExit("Use --run to exercise the real desktop")
    h = Hyprland()
    original_window = h.query("activewindow")
    original_ws = h.query("activeworkspace")["id"]
    original_theme = run("omarchy", "theme", "current")
    background = os.readlink(Path.home() / ".local/state/omarchy/current/background")
    config_path = Path.home() / ".config/omarchy/shell.json"
    initial_config = json.loads(config_path.read_text())
    used = {w["id"] for w in h.query("workspaces")}
    ws = next(n for n in range(4, 100) if n not in used)
    demo = None
    checks = []
    changed_theme = False
    try:
        assert not ipc("status")["active"]
        h.dispatch('hl.dispatch(hl.dsp.focus({workspace=' + str(ws) + ', on_current_monitor=true}))')
        demo = subprocess.Popen(["foot", "--app-id=omnitiler.lifecycle", "--title=OmniTiler · Lifecycle demo",
                                 "python3", str(ROOT / "tests/demo_window.py"), "1"],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        def client():
            return next((c for c in h.query("clients") if c["class"] == "omnitiler.lifecycle"), None)

        wait_for(client, "Lifecycle demo failed to open")
        ipc("activate")
        wait_for(lambda: client()["floating"], "Activation did not float demo")
        run("omarchy", "plugin", "disable", "fredrick.omnitiler")
        # Disable destroys the QML owner; cleanup must work without a prior IPC deactivate.
        until = time.monotonic() + 8
        while client()["floating"] and time.monotonic() < until:
            time.sleep(0.1)
        assert not client()["floating"], "QML destruction left a managed window floating"
        checks.append("Direct plugin disable restores managed windows")
        run("omarchy", "plugin", "enable", "fredrick.omnitiler", "--section", "center", "--after", "omarchy.clock")
        time.sleep(1)
        ipc("activate")
        wait_for(lambda: client()["floating"], "Re-enable failed")
        pids = run("pgrep", "-f", "^/usr/bin/python3 -u .*/fredrick.omnitiler/engine.py$").splitlines()
        assert len(pids) == 1, pids
        os.kill(int(pids[0]), signal.SIGKILL)
        wait_for(lambda: bool(ipc("status")["error"]), "Helper termination not reflected in status")
        ipc("deactivate")  # starts helper, recovers journal, then remains off
        wait_for(lambda: not client()["floating"] and not ipc("status")["error"], "Journal recovery failed")
        checks.append("Forced helper kill is reported; next start restores journaled windows")

        # Test EOF cleanup independently of Quickshell.
        run("omarchy", "plugin", "disable", "fredrick.omnitiler")
        worker = subprocess.Popen([sys.executable, "-u", str(ROOT / "engine.py")],
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        try:
            assert json.loads(worker.stdout.readline())["active"] is False
            worker.stdin.write('{"command":"activate"}\n')
            worker.stdin.flush()
            assert json.loads(worker.stdout.readline())["active"] is True
            worker.stdin.close()
            worker.wait(timeout=8)
            assert worker.returncode == 0
            assert not client()["floating"]
        finally:
            if worker.poll() is None:
                worker.terminate()
                worker.wait(timeout=8)
        checks.append("Standard input EOF restores tiling and exits cleanly")

        run(sys.executable, str(ROOT / "manage.py"), "remove")
        config = json.loads(config_path.read_text())
        expected = json.loads(json.dumps(initial_config))
        for entries in expected["bar"]["layout"].values():
            entries[:] = [e for e in entries if e["id"] != "fredrick.omnitiler"]
        expected["plugins"] = [e for e in expected.get("plugins", []) if e["id"] != "fredrick.omnitiler"]
        assert config == expected, "Removal changed unrelated shell settings"
        assert not (Path.home() / ".config/omarchy/plugins/fredrick.omnitiler").exists()
        run(sys.executable, str(ROOT / "manage.py"), "install")
        time.sleep(1)
        assert json.loads(config_path.read_text()) == initial_config
        checks.append("Removal/reinstallation preserves unrelated shell configuration and clock anchor")

        # One alternate theme proves live theme bindings; restore exact background too.
        changed_theme = True
        run("omarchy", "theme", "set", "Catppuccin Latte")
        time.sleep(2)
        ipc("activate")
        wait_for(lambda: client()["floating"], "Activation after theme switch failed")
        active_monitor = next(m for m in h.query("monitors") if m["focused"])
        expected_rect = h.dimensions(active_monitor)["center"]
        wait_for(lambda: tuple(client()["at"] + client()["size"]) == expected_rect,
                 "Theme switch did not preserve center geometry")
        time.sleep(1)  # Screenshot after compositor animation and terminal reflow.
        run("grim", "-o", h.query("monitors")[0]["name"], str(ROOT / "docs/preview-light.png"))
        ipc("deactivate")
        wait_for(lambda: not client()["floating"], "Theme test cleanup failed")
        checks.append("Alternate light theme loads; themed widget and placement still work")
        (ROOT / "test-results/lifecycle.json").write_text(json.dumps(checks, indent=2) + "\n")
        print("\n".join(checks))
    finally:
        if changed_theme:
            run("omarchy", "theme", "set", original_theme)
            run("omarchy", "theme", "bg", "set", background)
        # Restore local installation even if a lifecycle assertion failed midway.
        try:
            ipc("deactivate")
        except Exception:
            run(sys.executable, str(ROOT / "manage.py"), "install")
        if demo is not None and demo.poll() is None:
            demo.terminate()
            demo.wait(timeout=5)
        h.dispatch('hl.dispatch(hl.dsp.focus({workspace=' + str(original_ws) + '}))')
        if original_window.get("address"):
            h.focus(original_window)


if __name__ == "__main__":
    main()
